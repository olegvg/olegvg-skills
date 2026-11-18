#!/usr/bin/env python3
"""Validate release boundaries, grouped manifests and portable skill references."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from release_inventory import DESKTOP_SKILLS, EXECUTABLE_PATHS, PUBLIC_PATHS, SKILLS

VERSION_RE = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
MANIFESTS = ("plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json")
MARKETPLACES = (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json")
METADATA = ("name", "version", "description", "author", "homepage", "repository", "license", "keywords")
AUDIO = "plugins/transcribing-audio"
PUBLIC_TREES = ("skills", "commands", "assets", ".codex-plugin", ".claude-plugin", ".agents/plugins",
                *(f"{AUDIO}/{name}" for name in ("skills", "scripts", ".codex-plugin", ".claude-plugin")))


def public_paths() -> tuple[str, ...]:
    return PUBLIC_PATHS


def validate_plugin(root: Path) -> list[str]:
    root = Path(root).resolve()
    errors = []
    allowed = set(public_paths())

    def safe_file(relative):
        path = root / relative
        return (path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)
                                          if p != root and p.is_relative_to(root)))

    for relative in sorted(allowed):
        path = root / relative
        if any(p.is_symlink() for p in (path, *path.parents) if p != root and p.is_relative_to(root)):
            errors.append(f"{relative}: symlink inputs are not allowed")
        elif not path.is_file():
            errors.append(f"Missing required public file: {relative}")

    def walk(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append(f"{relative}: symlink inputs are not allowed")
            elif path.is_dir():
                if relative.startswith(AUDIO + "/scripts/") and path.name == "__pycache__":
                    continue  # Development cache; never a release input.
                if not any(name.startswith(relative + "/") for name in allowed):
                    errors.append(f"Unexpected public directory: {relative}")
                else:
                    walk(path)
            elif relative not in allowed:
                errors.append(f"Unexpected public file: {relative}")
            elif not path.is_file():
                errors.append(f"{relative}: only regular files are allowed")

    for directory in PUBLIC_TREES:
        top = root / directory
        if top.is_symlink():
            errors.append(f"{directory}: symlink directory is not allowed")
        elif top.is_dir():
            walk(top)
        else:
            errors.append(f"Missing component directory: {directory}")

    def read_json(relative):
        if not safe_file(relative):
            return None
        try:
            data = json.loads((root / relative).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            return data
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{relative}: invalid JSON ({exc})")
            return None

    manifests = {relative: read_json(relative) for relative in MANIFESTS}
    canonical = manifests["plugin.json"]
    if canonical is not None:
        if canonical.get("name") != "olegvg-skills":
            errors.append("plugin.json: name must be olegvg-skills")
        version = canonical.get("version")
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            errors.append("plugin.json: version must be numeric X.Y.Z without leading zeros")
        if canonical.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
            errors.append("plugin.json: expected the Agent Plugins 1.0.0 schema")
        if canonical.get("license") != "MIT":
            errors.append("plugin.json: license must be MIT")
        for key in ("description", "homepage", "repository"):
            if not isinstance(canonical.get(key), str) or not canonical[key].strip():
                errors.append(f"plugin.json: nonempty {key} is required")
        if not isinstance(canonical.get("author"), dict) or not canonical["author"].get("name"):
            errors.append("plugin.json: author name is required")

    def check_metadata(data, relative):
        if data is None or canonical is None:
            return
        for key in METADATA:
            if key not in canonical or data.get(key) != canonical.get(key):
                errors.append(f"{relative}: {key} must match plugin.json")

    expected_skills = {f"./skills/{name}" for name in SKILLS}
    expected_commands = {f"./commands/{name}.md" for name in SKILLS if name.startswith("kb-")}
    for relative in MANIFESTS[1:]:
        data = manifests[relative]
        check_metadata(data, relative)
        if data is not None and "skills" in data and data["skills"] != "./skills/":
            if not isinstance(data["skills"], list) or set(data["skills"]) != expected_skills:
                errors.append(f"{relative}: skills must refer to the portable root skill directories")
        if relative.startswith(".codex") and data is not None:
            interface = data.get("interface")
            icon = interface.get("composerIcon") if isinstance(interface, dict) else None
            if not isinstance(icon, str) or not icon.startswith("./assets/") or icon[2:] not in allowed or not safe_file(icon[2:]):
                errors.append(f"{relative}: composerIcon must refer to a bundled local asset")
            if not isinstance(interface, dict) or interface.get("privacyPolicyURL") != "https://github.com/olegvg/olegvg-skills/blob/master/PRIVACY.md":
                errors.append(f"{relative}: privacyPolicyURL must point to the package privacy policy")

    marketplaces = {}
    for relative in MARKETPLACES:
        data = read_json(relative)
        if data is None:
            continue
        plugins = data.get("plugins")
        names = ("olegvg-skills", "transcribing-audio") if relative.startswith(".agents") else ("olegvg-skills", "kb-for-agents", "core-dev", "transcribing-audio")
        if not isinstance(plugins, list) or any(not isinstance(p, dict) for p in plugins) or [p.get("name") for p in plugins] != list(names):
            errors.append(f"{relative}: expected ordered unique plugin entries {names}")
            continue
        marketplaces[relative] = data
        check_metadata(plugins[0], relative)
        for entry in plugins:
            name = entry["name"]
            path = "./" + AUDIO if name == "transcribing-audio" else ("./skills" if relative.startswith(".claude") and name != "olegvg-skills" else "./")
            source = {"source": "local", "path": path} if relative.startswith(".agents") else path
            if entry.get("source") != source:
                errors.append(f"{relative}: {name} source must refer to its local plugin root")
        if relative.startswith(".claude"):
            metadata = data.get("metadata")
            if not isinstance(metadata, dict) or canonical is None or metadata.get("version") != canonical.get("version"):
                errors.append(f"{relative}: metadata version must match plugin.json")
            owners = []
            for entry in plugins[:-1]:
                skills, commands = entry.get("skills"), entry.get("commands")
                if isinstance(skills, list) and entry["name"] != "olegvg-skills":
                    skills = ["./skills/" + s[2:] if isinstance(s, str) and s.startswith("./") else s for s in skills]
                if not isinstance(skills, list) or any(not isinstance(s, str) for s in skills) or not set(skills) <= expected_skills:
                    errors.append(f"{relative}: {entry['name']} skills must list only portable root skills")
                    continue
                if len(skills) != len(set(skills)) or not skills:
                    errors.append(f"{relative}: {entry['name']} skills must be nonempty and unique")
                if entry.get("strict") is not True:
                    errors.append(f"{relative}: root groups require strict: true to avoid conflicting manifests")
                if canonical is not None and entry.get("version") != canonical.get("version"):
                    errors.append(f"{relative}: group version must match plugin.json")
                if not isinstance(commands, list) or set(commands) != (expected_commands if entry["name"] == "olegvg-skills" else set()):
                    errors.append(f"{relative}: group commands must match its KB skills")
                if entry["name"] == "olegvg-skills":
                    if set(skills) != expected_skills or set(commands or []) != expected_commands:
                        errors.append(f"{relative}: umbrella skills/commands must include every portable root skill")
                else:
                    owners.extend(skills)
            if sorted(owners) != sorted(expected_skills):
                errors.append(f"{relative}: every root skill must belong to exactly one concrete group")
            if "skills" in plugins[-1] or "commands" in plugins[-1]:
                errors.append(f"{relative}: standalone audio plugin cannot expose skill-only arrays")

    website = read_json("skills.sh.json")
    claude_market = marketplaces.get(".claude-plugin/marketplace.json")
    if website is not None and claude_market is not None:
        groups = website.get("groupings")
        if not isinstance(groups, list) or any(not isinstance(g, dict) or not isinstance(g.get("skills"), list) or any(not isinstance(s, str) for s in g["skills"]) for g in groups):
            errors.append("skills.sh.json: invalid groupings")
        elif sorted(tuple(sorted(g["skills"])) for g in groups) != sorted(tuple(sorted(Path(s).name for s in g["skills"])) for g in claude_market["plugins"][1:-1] if isinstance(g.get("skills"), list)):
            errors.append("skills.sh.json: groups must match the concrete marketplace groups")

    audio_claude = read_json(f"{AUDIO}/.claude-plugin/plugin.json")
    audio_codex = read_json(f"{AUDIO}/.codex-plugin/plugin.json")
    if audio_claude is not None and audio_codex is not None:
        for key in ("name", "description", "author", "homepage", "repository", "license"):
            if key not in audio_claude or audio_claude[key] != audio_codex.get(key):
                errors.append(f"{AUDIO}: {key} must match across manifests")
        version = audio_claude.get("version")
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or audio_codex.get("version", "").split("+", 1)[0] != version:
            errors.append(f"{AUDIO}: independent base versions must agree")
        if audio_codex.get("skills") != "./skills/":
            errors.append(f"{AUDIO}: skills must resolve inside the standalone plugin")
        if claude_market and claude_market["plugins"][-1].get("version") != version:
            errors.append(f"{AUDIO}: marketplace version must match its independent version")

    def validate_links(skill_root, boundary):
        for document in sorted(skill_root.rglob("*.md")):
            if not safe_file(document.relative_to(root)):
                continue
            text = document.read_text(encoding="utf-8")
            for link in re.findall(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", text):
                if link.startswith("<") or "<" in link:  # Documentation placeholders.
                    continue
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                target = document.parent / unquote(parsed.path)
                if not target.resolve().is_relative_to(boundary.resolve()):
                    errors.append(f"{document.relative_to(root)}: reference outside standalone skill: {link}")
                elif not target.exists():
                    errors.append(f"{document.relative_to(root)}: missing reference: {link}")

    for name in (*SKILLS, "transcribing-audio"):
        relative = f"skills/{name}" if name in SKILLS else f"{AUDIO}/skills/{name}"
        skill_root = root / relative
        if not safe_file(f"{relative}/SKILL.md"):
            continue
        try:
            content = (skill_root / "SKILL.md").read_text(encoding="utf-8")
            frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.S)
            if not frontmatter:
                errors.append(f"{relative}/SKILL.md: missing frontmatter")
            else:
                values = dict(re.findall(r"^([a-z-]+):\s*(.+)$", frontmatter[1], re.M))
                if values.get("name") != name or not values.get("description", "").strip():
                    errors.append(f"{relative}/SKILL.md: invalid name/description frontmatter")
                if name == "transcribing-audio" and not re.search(r"^metadata:\s*\n  internal: true\s*$", frontmatter[1], re.M):
                    errors.append(f"{relative}: runtime-dependent skill must be internal to generic skills CLI discovery")
            validate_links(skill_root, skill_root if name in SKILLS else root / AUDIO)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{relative}: unable to validate text ({exc})")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    errors = validate_plugin(parser.parse_args().root)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Plugin validation passed ({len(SKILLS)} portable root skills; grouped installs and independent audio runtime)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
