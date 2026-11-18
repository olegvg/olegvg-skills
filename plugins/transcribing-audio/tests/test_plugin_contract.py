from __future__ import annotations

import json
import re
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills" / "transcribing-audio"
MARKETPLACE_PATH = PLUGIN_ROOT.parents[1] / ".agents" / "plugins" / "marketplace.json"


def _yaml_interface() -> dict[str, str]:
    lines = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8").splitlines()
    result: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r'  ([a-z_]+): "([^"]+)"', line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def test_plugin_manifest_has_only_implemented_components_and_coherent_metadata() -> None:
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())

    assert manifest["name"] == PLUGIN_ROOT.name == "transcribing-audio"
    assert re.fullmatch(
        r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", manifest["version"]
    )
    assert manifest["version"].split("+", maxsplit=1)[0] == "0.1.0"
    assert manifest["version"].count("+codex.") == 1
    assert manifest["author"]["name"].strip()
    assert manifest["skills"] == "./skills/"
    assert all(
        not Path(value).is_absolute() and value.startswith("./") for value in [manifest["skills"]]
    )
    assert not {"apps", "mcpServers", "hooks", "icon", "logo", "screenshots", "assets"} & set(
        manifest
    )
    assert "TODO" not in json.dumps(manifest).upper()

    interface = manifest["interface"]
    assert interface["displayName"] == "Audio Transcription"
    assert "OpenAI ASR" in manifest["description"]
    assert (
        interface["shortDescription"].rstrip(".") == "Transcribe and diarize speaker-labelled audio"
    )
    assert "word timestamps" in interface["longDescription"]
    assert "local diarization" in interface["longDescription"]
    assert interface["defaultPrompt"] == (
        "Use $transcribing-audio:transcribing-audio to transcribe this recording with speaker labels."
    )
    assert interface["capabilities"] == []


def test_embedded_metadata_is_quoted_and_matches_the_plugin_interface() -> None:
    metadata = _yaml_interface()
    raw_metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())

    assert set(metadata) == {"display_name", "short_description", "default_prompt"}
    assert all(f'{key}: "' in raw_metadata for key in metadata)
    assert metadata["display_name"] == manifest["interface"]["displayName"]
    assert metadata["short_description"] == manifest["interface"]["shortDescription"].rstrip(".")
    assert 25 <= len(metadata["short_description"]) <= 64
    assert "$transcribing-audio" in metadata["default_prompt"]
    assert metadata["default_prompt"] == manifest["interface"]["defaultPrompt"]


def test_marketplace_entry_is_local_available_and_preserves_normalized_names() -> None:
    marketplace = json.loads(MARKETPLACE_PATH.read_text())
    matching_entries = [
        item for item in marketplace["plugins"] if item["name"] == "transcribing-audio"
    ]

    assert len(matching_entries) == 1
    assert marketplace["name"].strip()
    assert marketplace["interface"]["displayName"].strip()
    assert matching_entries[0] == {
        "name": "transcribing-audio",
        "source": {"source": "local", "path": "./plugins/transcribing-audio"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": matching_entries[0]["category"],
    }
    assert matching_entries[0]["category"].strip()
