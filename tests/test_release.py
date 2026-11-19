"""Release boundary tests; all Git mutations happen in disposable fixtures."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
PACKAGE_TAG = f"v{PACKAGE_VERSION}"
sys.path.insert(0, str(ROOT / "scripts"))


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        for name in ("validate_plugin", "generate_changelog", "build_release"):
            if not (ROOT / "scripts" / (name + ".py")).exists():
                self.fail(f"Missing release behavior: scripts/{name}.py")
        self.validator = importlib.import_module("validate_plugin")
        self.notes = importlib.import_module("generate_changelog")
        self.temp = tempfile.TemporaryDirectory(prefix="olegvg-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "source"
        # Disposable fixtures must never inherit real Git directories, signing
        # configuration, credential helpers, or hooks from the user's session.
        self.git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.git_env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                            GIT_AUTHOR_DATE="2026-09-30T12:00:00+00:00",
                            GIT_COMMITTER_DATE="2026-09-30T12:00:00+00:00")
        # Never copy unrelated private files or runtime caches into Git fixtures.
        for relative in (*self.validator.public_paths(), ".gitignore"):
            source, destination = ROOT / relative, self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        self.git("init", "-b", "master")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "release-test@example.invalid")
        self.commit("Initial public package")

    def git(self, *args, check=True):
        return subprocess.run(["git", "-C", str(self.root), *args], check=check,
                              capture_output=True, text=True, env=self.git_env).stdout.strip()

    def commit(self, subject):
        self.git("add", "--all")
        self.git("commit", "-m", subject)

    def edit_json(self, path, edit):
        target = self.root / path
        data = json.loads(target.read_text())
        edit(data)
        target.write_text(json.dumps(data, indent=2) + "\n")

    def invalid(self, text):
        errors = self.validator.validate_plugin(self.root)
        self.assertTrue(errors)
        self.assertIn(text.lower(), "\n".join(errors).lower())

    def build(self, *args, output=None):
        output = output or self.home / "output"
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_release.py"),
                                 "--root", str(self.root), "--output", str(output), *args],
                                capture_output=True, text=True)
        return result, output

    def test_valid_package(self):
        self.assertEqual([], self.validator.validate_plugin(self.root))

    def test_preview_includes_security_policy_and_icon(self):
        for name, content in (("SECURITY.md", "# Security\n"),
                              ("assets/icon.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        result, output = self.build("--preview")
        self.assertEqual(0, result.returncode, result.stderr)
        with zipfile.ZipFile(output / f"olegvg-skills-plugin-{PACKAGE_VERSION}.zip") as archive:
            for name in ("SECURITY.md", "assets/icon.svg"):
                self.assertIn("olegvg-skills-plugin/" + name, archive.namelist())
                self.assertEqual((self.root / name).read_bytes(),
                                 archive.read("olegvg-skills-plugin/" + name))

    def test_unexpected_file_inside_assets_is_rejected(self):
        assets = self.root / "assets"
        assets.mkdir(exist_ok=True)
        (assets / "candidate-record.md").write_text("synthetic private record")
        self.invalid("Unexpected public file: assets/candidate-record.md")

    def test_icon_must_resolve_to_a_bundled_asset(self):
        for icon in (None, "./assets/missing.svg", "../outside.svg", "./PRIVACY.md"):
            with self.subTest(icon=icon):
                self.edit_json(".codex-plugin/plugin.json",
                               lambda data: data["interface"].update(composerIcon=icon))
                self.invalid("composerIcon")

    def test_missing_required_reference(self):
        (self.root / "skills/kb-build/references/semantic-grouping.md").unlink()
        self.invalid("semantic-grouping.md")

    def test_linked_missing_reference(self):
        path = self.root / "skills/kb-build/SKILL.md"
        path.write_text(path.read_text() + "\n[More](references/missing.md)\n")
        self.invalid("missing.md")

    def test_malformed_marketplace_metadata_is_actionable(self):
        self.edit_json(".claude-plugin/marketplace.json", lambda data: data.update(metadata=[]))
        self.invalid("metadata")

    def test_non_object_manifest_is_actionable(self):
        (self.root / ".codex-plugin/plugin.json").write_text("[]\n")
        self.invalid("JSON")

    def test_each_empty_manifest_object_is_rejected(self):
        declarations = (
            "plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
            ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json",
        )
        for relative in declarations:
            with self.subTest(manifest=relative):
                path = self.root / relative
                original = path.read_bytes()
                try:
                    path.write_text("{}\n")
                    self.invalid(relative)
                finally:
                    path.write_bytes(original)

    def test_builder_rejects_each_empty_manifest_before_output(self):
        declarations = (
            "plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
            ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json",
        )
        for index, relative in enumerate(declarations):
            with self.subTest(manifest=relative):
                path = self.root / relative
                original = path.read_bytes()
                try:
                    path.write_text("{}\n")
                    result, output = self.build("--preview", output=self.home / f"empty-object-output-{index}")
                    self.assertNotEqual(0, result.returncode, result.stdout)
                    self.assertIn("Plugin validation failed", result.stderr)
                    self.assertIn(relative, result.stderr)
                    self.assertFalse(output.exists(), "Invalid declarations must not produce release output")
                finally:
                    path.write_bytes(original)

    def test_manifest_version_mismatch(self):
        self.edit_json(".codex-plugin/plugin.json", lambda data: data.update(version="1.2.0"))
        self.invalid("version")

    def test_bad_semver(self):
        for version in ("00.7.0", "v0.7.0", "1.1", "0.7.0\n", "0.7.0-01"):
            with self.subTest(version=version):
                self.edit_json("plugin.json", lambda data: data.update(version=version))
                self.invalid("version")

    def test_skill_path_traversal(self):
        self.edit_json(".claude-plugin/plugin.json", lambda data: data.update(skills=["../outside"]))
        self.invalid("skills")

    def test_cross_skill_reference(self):
        path = self.root / "skills/kb-build/SKILL.md"
        path.write_text(path.read_text() + "\n[Other](../kb-query/SKILL.md)\n")
        self.invalid("outside")

    def test_unexpected_file_inside_public_tree(self):
        (self.root / "skills/kb-build/session.txt").write_text("unsupported file fixture\n")
        self.invalid("session.txt")

    def test_unexpected_metadata_file(self):
        (self.root / ".codex-plugin/session.json").write_text("{}\n")
        self.invalid("session.json")

    def test_symlink_public_file(self):
        target = self.root / "skills/kb-build/templates/summary.template.md"
        target.unlink()
        target.symlink_to(self.root / "skills/kb-build/templates/index.template.md")
        self.invalid("symlink")

    def test_symlink_public_directory(self):
        target = self.root / "skills/kb-build/references"
        shutil.rmtree(target)
        target.symlink_to(self.root / "skills/resume-tailor/references", target_is_directory=True)
        self.invalid("symlink")

    def test_output_symlink_is_rejected_without_writes(self):
        destination = self.home / "destination"
        destination.mkdir()
        alias = self.home / "output-link"
        alias.symlink_to(destination, target_is_directory=True)
        result, _ = self.build("--preview", output=alias / "new-output")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], list(destination.iterdir()))

    def test_release_notes_ignore_local_git_abbreviation_preferences(self):
        self.git("config", "core.abbrev", "7")
        one = self.notes.generate_notes(self.root, self.root, None, None, True)
        self.git("config", "core.abbrev", "12")
        two = self.notes.generate_notes(self.root, self.root, None, None, True)
        self.assertEqual(one, two)

    def test_first_release_notes_include_entire_history_and_commit_date(self):
        self.git("tag", PACKAGE_TAG)
        notes = self.notes.generate_notes(self.root, self.root, PACKAGE_TAG, None, False)
        self.assertIn("First release", notes)
        self.assertIn("Initial public package", notes)
        self.assertIn("2026-09-30", notes)

    def test_subsequent_release_excludes_previous_release(self):
        self.git("tag", "v0.6.0")
        (self.root / "README.md").write_text((self.root / "README.md").read_text() + "\nPublic improvement\n")
        self.commit("Add portable release improvement")
        self.git("tag", PACKAGE_TAG)
        notes = self.notes.generate_notes(self.root, self.root, PACKAGE_TAG, None, False)
        self.assertIn("Add portable release improvement", notes)
        self.assertNotIn("Initial public package", notes)
        self.assertIn("v0.6.0", notes)

    def test_preview_labels_pending_edits_separately(self):
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n- Pending fixture change.\n"
        )
        notes = self.notes.generate_notes(self.root, self.root, None, None, True)
        self.assertIn("Preview", notes)
        self.assertIn("Curated unreleased changes", notes)
        self.assertIn("Committed history", notes)
        self.assertIn("Pending fixture change.", notes)
        self.assertIn("Initial public package", notes)

    def test_bad_tags_bases_and_missing_refs(self):
        self.git("tag", PACKAGE_TAG)
        for tag in ("0.7.0", "v00.7.0", "--all", "v9.9.9", "v0.6.0"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.notes.generate_notes(self.root, self.root, tag, None, False)
        for base in ("--all", "master", "v9.9.9", PACKAGE_TAG, "v00.7.0"):
            with self.subTest(base=base), self.assertRaises(ValueError):
                self.notes.generate_notes(self.root, self.root, PACKAGE_TAG, base, False)

    def test_unrelated_base_is_rejected(self):
        self.git("tag", PACKAGE_TAG)
        self.git("checkout", "--orphan", "unrelated")
        self.git("rm", "-rf", ".")
        (self.root / "unrelated.txt").write_text("Independent public fixture\n")
        self.commit("Unrelated branch")
        self.git("tag", "v0.6.0")
        self.git("checkout", "master")
        with self.assertRaises(ValueError):
            self.notes.generate_notes(self.root, self.root, PACKAGE_TAG, "v0.6.0", False)

    def test_non_ancestor_tag_is_not_automatic_base(self):
        self.git("branch", "side")
        (self.root / "README.md").write_text("public branch change\n")
        self.commit("Current branch feature")
        self.git("tag", PACKAGE_TAG)
        self.git("checkout", "side")
        (self.root / "README.md").write_text("other public branch\n")
        self.commit("Other branch feature")
        self.git("tag", "v0.6.0")
        self.git("checkout", "master")
        notes = self.notes.generate_notes(self.root, self.root, PACKAGE_TAG, None, False)
        self.assertIn("First release", notes)
        self.assertIn("Current branch feature", notes)
        self.assertNotIn("Other branch feature", notes)

    def test_source_dirty_public_file_rejected_for_tag(self):
        self.git("tag", PACKAGE_TAG)
        (self.root / "README.md").write_text("Uncommitted public change\n")
        result, output = self.build("--tag", PACKAGE_TAG)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(output.exists(), result.stderr)

    def test_assume_unchanged_public_bytes_still_rejected(self):
        self.git("tag", PACKAGE_TAG)
        self.git("update-index", "--assume-unchanged", "README.md")
        (self.root / "README.md").write_text("Changed public bytes\n")
        self.assertEqual("", self.git("status", "--porcelain"))
        result, output = self.build("--tag", PACKAGE_TAG)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(output.exists())

    def test_annotated_release_tag(self):
        self.git("tag", "-a", PACKAGE_TAG, "-m", "Public release fixture")
        notes = self.notes.generate_notes(self.root, self.root, PACKAGE_TAG, None, False)
        self.assertIn("Initial public package", notes)

    def test_shallow_history_is_rejected(self):
        shallow = self.home / "shallow"
        subprocess.run(["git", "clone", "--depth=1", self.root.resolve().as_uri(), str(shallow)],
                       check=True, capture_output=True, env=self.git_env)
        with self.assertRaisesRegex(ValueError, "Full Git history"):
            self.notes.generate_notes(shallow, shallow, None, None, True)

    def test_tag_not_at_selected_head_rejected(self):
        self.git("tag", PACKAGE_TAG)
        (self.root / "README.md").write_text("Later public change\n")
        self.commit("Post release public update")
        result, output = self.build("--tag", PACKAGE_TAG)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(output.exists())

    def test_tagged_detached_stage_cannot_impersonate_history(self):
        self.git("tag", PACKAGE_TAG)
        separate = self.home / "detached-stage"
        shutil.copytree(self.root, separate, ignore=shutil.ignore_patterns(".git"))
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_release.py"),
                                 "--root", str(separate), "--history-repo", str(self.root),
                                 "--output", str(self.home / "output"), "--tag", PACKAGE_TAG],
                                capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.home / "output").exists())

    def test_invalid_build_preserves_existing_output(self):
        output = self.home / "output"
        output.mkdir()
        marker = output / "existing.txt"
        marker.write_text("Keep this public fixture\n")
        result, _ = self.build("--tag", "v9.9.9", output=output)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("Keep this public fixture\n", marker.read_text())
        self.assertEqual(["existing.txt"], sorted(p.name for p in output.iterdir()))

    def test_output_overlaps_source_rejected(self):
        for output in (self.root, self.root / "skills", self.root / "dist", self.home):
            with self.subTest(output=output):
                result, _ = self.build("--preview", output=output)
                self.assertNotEqual(0, result.returncode)

    def test_preview_separate_history_repo(self):
        stage = self.home / "stage"
        shutil.copytree(self.root, stage, ignore=shutil.ignore_patterns(".git"))
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build_release.py"),
                                 "--root", str(stage), "--history-repo", str(self.root),
                                 "--output", str(self.home / "preview"), "--preview"],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Preview", (self.home / "preview/release-notes.md").read_text())

    def test_deterministic_complete_archives_and_all_checksums(self):
        self.git("tag", PACKAGE_TAG)
        one, first = self.build("--tag", PACKAGE_TAG, output=self.home / "first")
        two, second = self.build("--tag", PACKAGE_TAG, output=self.home / "second")
        self.assertEqual(0, one.returncode, one.stderr)
        self.assertEqual(0, two.returncode, two.stderr)
        expected = {
            f"{package}-{PACKAGE_VERSION}.zip"
            for package in (
                "olegvg-skills-plugin", "kb-build", "kb-query", "kb-refresh",
                "kb-check-drift", "simplify-code", "kb-record-decision",
                "kb-maintain", "mobile-test-environments", "deep-code-review",
            )
        }
        expected.update(("CHANGELOG.md", "release-notes.md", "SHA256SUMS"))
        self.assertEqual(expected, {p.name for p in first.iterdir()})
        for name in expected:
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)
        sums = {}
        for line in (first / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split("  ")
            sums[name] = digest
            self.assertEqual(digest, hashlib.sha256((first / name).read_bytes()).hexdigest())
        self.assertEqual(expected - {"SHA256SUMS"}, set(sums))
        for skill in self.validator.SKILLS:
            with zipfile.ZipFile(first / f"{skill}-{PACKAGE_VERSION}.zip") as archive:
                names = archive.namelist()
                self.assertEqual(sorted(names), names)
                self.assertIn(skill + "/SKILL.md", names)
                self.assertEqual((self.root / "LICENSE").read_bytes(), archive.read(skill + "/LICENSE"))
                for path in (self.root / "skills" / skill).rglob("*"):
                    if path.is_file():
                        self.assertEqual(path.read_bytes(), archive.read(skill + "/" + path.relative_to(self.root / "skills" / skill).as_posix()))
                for info in archive.infolist():
                    self.assertEqual((1980, 1, 1, 0, 0, 0), info.date_time)
                    self.assertEqual(0o100644, info.external_attr >> 16)
        with zipfile.ZipFile(first / f"olegvg-skills-plugin-{PACKAGE_VERSION}.zip") as archive:
            names = archive.namelist()
            self.assertIn("olegvg-skills-plugin/.codex-plugin/plugin.json", names)
            self.assertIn("olegvg-skills-plugin/skills/kb-build/SKILL.md", names)
            self.assertNotIn("olegvg-skills-plugin/skills/audit-state-machines/SKILL.md", names)
            self.assertIn("olegvg-skills-plugin/AGENTS.md", names)
            self.assertIn("olegvg-skills-plugin/docs/releasing.md", names)
            self.assertNotIn("olegvg-skills-plugin/docs/audit-state-machines.md", names)
            self.assertEqual((self.root / "docs/deep-code-review.md").read_bytes(),
                             archive.read("olegvg-skills-plugin/docs/deep-code-review.md"))
            self.assertFalse(any("__pycache__" in name or name.endswith("CLAUDE.md") for name in names))
            self.assertTrue(all(name.startswith("olegvg-skills-plugin/") for name in names))


    def test_root_templates_are_present_in_standalone_build_skill(self):
        result, output = self.build("--preview")
        self.assertEqual(0, result.returncode, result.stderr)
        with zipfile.ZipFile(output / f"kb-build-{PACKAGE_VERSION}.zip") as archive:
            for name in ("_root.template.md", "index.template.md", "summary.template.md", ".kb-state.template.json"):
                self.assertIn("kb-build/templates/" + name, archive.namelist())
            self.assertIn("kb-build/references/subagent-prompt.md", archive.namelist())

    def test_claude_conflicting_strict_false_group_is_rejected(self):
        self.edit_json(".claude-plugin/marketplace.json", lambda data: data["plugins"][2].update(strict=False))
        self.invalid("strict")

    def test_concrete_group_ownership_is_unique(self):
        self.edit_json(".claude-plugin/marketplace.json", lambda data: data["plugins"][2]["skills"].append("./kb-build"))
        self.invalid("group")

    def test_marketplace_cannot_expose_runtime_skill_as_standalone(self):
        self.edit_json(".claude-plugin/marketplace.json", lambda data: data["plugins"][0]["skills"].append("./plugins/transcribing-audio/skills/transcribing-audio"))
        self.invalid("skills")

    def test_nested_runtime_private_file_is_rejected(self):
        (self.root / "plugins/transcribing-audio/scripts/recording.wav").write_bytes(b"synthetic private fixture")
        self.invalid("recording.wav")

    def test_unrelated_private_files_and_caches_never_ship(self):
        (self.root / ".env").write_text("SYNTHETIC_KEY=do-not-ship")
        cache = self.root / "plugins/transcribing-audio/.venv"
        cache.mkdir()
        (cache / "secret.txt").write_text("private fixture")
        result, output = self.build("--preview")
        self.assertEqual(0, result.returncode, result.stderr)
        with zipfile.ZipFile(output / f"olegvg-skills-plugin-{PACKAGE_VERSION}.zip") as archive:
            self.assertFalse(any(".venv" in name or "/.env" in name or "/tests/" in name or "/plans/" in name for name in archive.namelist()))
            self.assertIn("olegvg-skills-plugin/plugins/transcribing-audio/uv.lock", archive.namelist())
            launcher = archive.getinfo("olegvg-skills-plugin/plugins/transcribing-audio/scripts/transcribe_audio.py")
            self.assertEqual(0o100755, launcher.external_attr >> 16)

if __name__ == "__main__":
    unittest.main()
