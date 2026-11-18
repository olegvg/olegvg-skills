from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from audio_transcriber.cli import build_parser
from audio_transcriber.constants import (
    DEFAULT_DIARIZATION_MODEL,
    DEFAULT_DIARIZATION_REVISION,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_MAX_CHUNK_DURATION_S,
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OVERLAP_S,
    OUTPUT_JSON_SUFFIX,
    OUTPUT_SRT_SUFFIX,
    OUTPUT_TEXT_SUFFIX,
    OUTPUT_VTT_SUFFIX,
    OUTPUT_SCHEMA_VERSION,
    RUNTIME_ROOT_NAME,
    STATE_SCHEMA_VERSION,
)
from audio_transcriber.quality import QualityPolicy


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills" / "transcribing-audio"
SKILL_PATH = SKILL_ROOT / "SKILL.md"
REFERENCES = {
    "runtime-and-backends.md",
    "local-asr.md",
    "openai-asr.md",
    "diarization-and-alignment.md",
    "quality-and-recovery.md",
    "output-schema.md",
}


def _skill_parts() -> tuple[dict[str, str], str]:
    content = SKILL_PATH.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)", content, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    frontmatter = {
        key: value
        for key, separator, value in (
            line.partition(": ") for line in match.group("frontmatter").splitlines()
        )
        if separator
    }
    return frontmatter, match.group("body")


def _documented_launcher(skill_directory: Path) -> Path:
    return (skill_directory / "../../scripts/transcribe_audio.py").resolve()


def test_skill_metadata_and_core_workflow_are_triggerable_and_concise() -> None:
    frontmatter, body = _skill_parts()

    assert {"name", "description"} <= set(frontmatter)
    assert frontmatter["name"] == "transcribing-audio"
    description = frontmatter["description"].casefold()
    for phrase in (
        "transcrib",
        "diarization",
        "speaker",
        "voice memos",
        "meetings",
        "interviews",
        "local",
        "openai",
        "timestamp",
    ):
        assert phrase in description
    assert len(body.splitlines()) < 500
    for section in (
        "# Transcribing Audio",
        "## Safety and privacy",
        "## Choose the mode",
        "## Run the pipeline",
        "## Stop conditions",
        "## Common commands",
        "## Read references only when needed",
    ):
        assert section in body
    for instruction in (
        "OpenAI",
        "explicit consent",
        "--resume",
        "quality retry",
        "canonical JSON",
        "never print dotenv values",
    ):
        assert instruction.casefold() in body.casefold()


def test_skill_links_one_level_references_and_documents_every_cli_flag() -> None:
    _, body = _skill_parts()

    linked = set(re.findall(r"references/([a-z0-9-]+\.md)", body))
    assert linked == REFERENCES
    assert {path.name for path in (SKILL_ROOT / "references").iterdir()} == REFERENCES
    assert all((SKILL_ROOT / "references" / reference).is_file() for reference in REFERENCES)
    for reference in REFERENCES:
        content = (SKILL_ROOT / "references" / reference).read_text(encoding="utf-8")
        assert not re.search(r"references/[a-z0-9-]+\.md", content)

    parser = build_parser()
    flags = {
        option
        for action in parser._actions  # pyright: ignore[reportPrivateUsage]
        for option in action.option_strings
        if option.startswith("--")
    }
    assert flags <= set(re.findall(r"--[a-z-]+", body))


def test_documented_launcher_resolution_is_checkout_and_install_location_portable(
    tmp_path: Path,
) -> None:
    checkout_skill = tmp_path / "checkout" / "skills" / "transcribing-audio"
    installed_skill = tmp_path / "installed" / "bundle" / "skills" / "transcribing-audio"
    for skill_directory in (checkout_skill, installed_skill):
        launcher = skill_directory.parent.parent / "scripts" / "transcribe_audio.py"
        launcher.parent.mkdir(parents=True)
        launcher.touch()
        assert _documented_launcher(skill_directory) == launcher

    _, body = _skill_parts()
    assert 'SKILL_DIR="<absolute path to this skill directory>"' in body
    assert '"$SKILL_DIR/../../scripts/transcribe_audio.py"' in body
    assert "psy_bot" not in body


def test_skill_body_contains_no_setup_secrets_or_detailed_reference_material() -> None:
    _, body = _skill_parts()

    forbidden = (
        "pip install",
        "uv sync",
        "OPENAI_API_KEY=",
        "HF_TOKEN=",
        "sk-",
        "| Threshold |",
        '"schema_version"',
        "create transcription",
    )
    assert not any(value.casefold() in body.casefold() for value in forbidden)


def test_references_agree_with_machine_readable_runtime_contract() -> None:
    reference_text = {
        reference: (SKILL_ROOT / "references" / reference).read_text(encoding="utf-8")
        for reference in REFERENCES
    }
    combined = "\n".join(reference_text.values())
    for value in (
        DEFAULT_LOCAL_MODEL,
        DEFAULT_OPENAI_MODEL,
        DEFAULT_DIARIZATION_MODEL,
        DEFAULT_DIARIZATION_REVISION,
        str(DEFAULT_MAX_UPLOAD_BYTES),
        str(DEFAULT_MAX_CHUNK_DURATION_S),
        str(DEFAULT_OVERLAP_S),
        str(OUTPUT_SCHEMA_VERSION),
        str(STATE_SCHEMA_VERSION),
        RUNTIME_ROOT_NAME,
        OUTPUT_JSON_SUFFIX,
        OUTPUT_TEXT_SUFFIX,
        OUTPUT_SRT_SUFFIX,
        OUTPUT_VTT_SUFFIX,
    ):
        assert value in combined

    policy_text = reference_text["quality-and-recovery.md"]
    for name, value in asdict(QualityPolicy()).items():
        assert name in policy_text
        assert str(value) in policy_text
