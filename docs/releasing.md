# Release preparation

The release tools use Python 3.10+ standard library and Git. Root skills have no
build-time runtime dependency; the independent audio runtime keeps its own
`pyproject.toml` and `uv.lock`.

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
```

The validator checks metadata parity, concrete-group ownership, marketplace
ordering, website grouping, skill frontmatter, references and a reviewed file
inventory in `scripts/release_inventory.py`. Root skill references must resolve
inside each skill; optional rationale links point to the public documentation.
The audio skill stays inside its runtime plugin and is internal to default
Skills CLI discovery. Its Codex build metadata is retained independently.

New files in public component trees fail until explicitly reviewed. Symlinks
fail; the checkout-only `CLAUDE.md` symlink is not a release input. Runtime ZIPs
exclude tests, developer plans, Python caches, `.venv`, `.env`, `.git`, generated
KBs, recordings, transcripts and private state. Unknown checkout-root files never
enter archives. The audio launcher retains executable permissions.

## Local preview

Choose a fresh directory outside, not containing or overlapping either checkout.
Existing output directories and symlinked output paths are rejected. Both modes
validate and assemble everything before atomically creating the output directory.

```bash
python3 scripts/build_release.py --preview --output /tmp/olegvg-skills-preview-1
python3 scripts/generate_changelog.py --preview
```

A prepared tree can use a separate, read-only history checkout for previews:

```bash
python3 scripts/build_release.py --root /path/to/staged-source --history-repo /path/to/history-checkout --preview --output /path/to/fresh-preview
```

Preview notes distinguish curated Unreleased changes from committed history;
they are not a published release. Identical source/history produces identical
bytes. Dates come from the selected commit. ZIP paths are sorted, timestamps are
1980-01-01, regular files are 0644 (the audio launcher is 0755), and entries use
ZIP_STORED to avoid compressor-version variation.

## Tagged builds

Only numeric `X.Y.Z` versions and existing `vX.Y.Z` tags without leading zeros
are accepted. The tag must match all umbrella versions, resolve to HEAD, and
match every public input byte. Tagged builds require a clean checkout and the
same source/history root. An altered assume-unchanged input is still rejected.
Full history is required; shallow history fails instead of truncating notes.

After an explicitly authorized release commit and tag exist:

```bash
python3 scripts/build_release.py --tag vX.Y.Z --output /path/to/fresh-release
```

The nearest reachable numeric release tag is the default history base. The first
release includes all reachable commits. An explicit `--base vA.B.C` must exist
and be a strict ancestor; missing or unrelated bases fail. The scripts never
create tags/commits, push, install, change configuration or publish.

## Artifacts

Each build creates fourteen files, using the current umbrella version:

- `olegvg-skills-plugin-<version>.zip`: one `olegvg-skills-plugin/` root with
  portable/Codex/Claude manifests, marketplace indexes, ten root skills,
  commands, canonical templates, public docs, security/privacy policies, icon,
  LICENSE and the complete independent audio runtime. The audio plugin remains
  a separate marketplace target. `AGENTS.md` is human maintainer documentation;
  checkout-only `CLAUDE.md` is omitted for strict native package validation.
- Ten `<skill>-<version>.zip` archives: each contains one complete root skill
  directory with all its references, local templates/metadata and MIT LICENSE.
  The five desktop-compatible skills retain their previous asset names.
  `kb-record-decision` and `kb-maintain` are for capable coding-agent hosts;
  orchestration still requires the companion KB skills. Neither archive includes
  a sibling skill or installs Claude Code command shims. `mobile-test-environments`
  requires a host with local device and mobile-tool access.
- Generated `CHANGELOG.md`, `release-notes.md` and `SHA256SUMS`. The curated source
  changelog is preserved unchanged in the full plugin archive. Every other
  output file is covered by SHA256SUMS.

The runtime-dependent audio skill is never shipped as a misleading skill-only
ZIP. Use its full plugin marketplace entry (or the nested `--plugin-dir` path).

From the output directory:

```bash
sha256sum -c SHA256SUMS        # Linux
shasum -a 256 -c SHA256SUMS    # macOS
```

## Native installation checks

Use disposable projects and configuration directories, never real host config.
See [install-surfaces.md](agent-instructions/install-surfaces.md) for every
supported installation route, pin and update command.

```bash
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .claude-plugin/marketplace.json --strict
bunx skills@latest install ./ --list
```

The source plugin can warn that root CLAUDE.md is not loaded as plugin context;
strict source validation can fail on that warning. Validate the extracted runtime
archive strictly too: it omits that maintainer pointer. Validate nested audio
manifests and exercise each concrete Claude group to verify its installed skills.

## CI and publication

CI validates pull requests and master pushes, runs temporary Git boundary tests,
builds a preview and verifies checksums. Release jobs use full Git history and
40-character pinned action revisions with persisted checkout credentials disabled.
Tag syntax is validated before checkout; shell input is passed through environment
variables. The build job has `contents: read`; a separate publish job alone has
`contents: write`. Manual dispatch defaults to build-only (`publish: false`).

Publication rechecks the selected tag commit and artifact checksums, then creates
or updates release notes and all ZIP, changelog and checksum assets. Publishing
requires a tag push or an explicit manual publish request. A prepared manifest
version is not evidence that a release has shipped. Never retarget a published
tag without explicit release-repair authorization.
