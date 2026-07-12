import json
import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills" / "transcribing-audio"
MARKETPLACE_PATH = PLUGIN_ROOT.parents[1] / ".agents" / "plugins" / "marketplace.json"


def test_plugin_has_required_top_level_artifacts() -> None:
    required = {
        ".codex-plugin",
        ".gitignore",
        "skills",
        "pyproject.toml",
        "scripts",
        "tests",
        "uv.lock",
    }
    assert required <= {path.name for path in PLUGIN_ROOT.iterdir()}
    assert not (PLUGIN_ROOT / "README.md").exists()


def test_plugin_contains_discoverable_skill() -> None:
    assert (SKILL_ROOT / "SKILL.md").is_file()
    assert (SKILL_ROOT / "agents" / "openai.yaml").is_file()


def test_manifest_and_marketplace_use_canonical_name() -> None:
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["name"] == PLUGIN_ROOT.name == "transcribing-audio"
    assert manifest["skills"] == "./skills/"
    assert "apps" not in manifest and "mcpServers" not in manifest and "hooks" not in manifest

    marketplace = json.loads(MARKETPLACE_PATH.read_text())
    entry = next(item for item in marketplace["plugins"] if item["name"] == "transcribing-audio")
    assert entry["source"] == {"source": "local", "path": "./plugins/transcribing-audio"}
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    assert entry["category"]


def test_plugin_local_venv_is_ignored() -> None:
    assert "/.venv/" in (PLUGIN_ROOT / ".gitignore").read_text().splitlines()


def test_launcher_imports_only_stdlib_before_bootstrap() -> None:
    launcher = PLUGIN_ROOT / "scripts" / "transcribe_audio.py"
    source = launcher.read_text()
    forbidden = ("openai", "dotenv", "pyannote", "torch", "faster_whisper", "mlx_whisper")
    assert all(name not in source for name in forbidden)
    assert os.access(launcher, os.X_OK)


def test_configured_pythonpath_imports_the_runtime_package() -> None:
    import audio_transcriber

    assert audio_transcriber.__name__ == "audio_transcriber"
