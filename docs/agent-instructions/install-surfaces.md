# Install surfaces

Use this before changing install commands, plugin manifests, marketplace metadata,
website grouping or README install sections. The complete user command reference
is [README.md](../../README.md#installation), mirrored in Russian in
[README.ru.md](../../README.ru.md#установка). Check current CLI help before edits.

## Source and metadata

Root `plugin.json` is the canonical umbrella identity and Agent Plugins 1.0.0
manifest, discovering `skills/` portably. `.codex-plugin/plugin.json` supplies
host compatibility; `.claude-plugin/plugin.json` supplies Claude metadata.
The two marketplace indexes expose the same umbrella identity. Keep shared
name/version/description/author/homepage/repository/license/keywords aligned.
Privacy URLs point to this package's PRIVACY.md. Icons must be bundled assets.

The umbrella entry uses source `./` and explicit skills/command arrays.
Concrete groups use source `./skills`, skill paths relative to that root and
`commands: []`: native skills preserve the same namespaced slash invocations,
without inheriting root command shims or the umbrella manifest name.
Set `strict: true` explicitly for the umbrella and concrete groups. The
audio entry uses Claude Code's default strict mode and its own manifest.
See the [marketplace field reference](https://code.claude.com/docs/en/plugins/marketplace-reference).
Keep the umbrella first, followed by concrete groups, so Skills CLI shows
each skill under its concrete group. A root skill belongs to exactly one
concrete group and the umbrella. Website `skills.sh.json` mirrors concrete groups.
Codex indexes the umbrella and independent runtime plugins, not artificial groups.

## Runtime boundary

`plugins/transcribing-audio/` is independently versioned and installs as a full
plugin in Claude Code/Codex. Its paired manifests and marketplace sources point
at its own root. Never put its skill in umbrella/group skills arrays or website
root-skill grouping. Its skill has `metadata.internal: true` so default recursive
Skills CLI discovery does not install it without its Python runtime.

Root skills must carry required references, templates and agent metadata inside
their own directory. `kb-build/templates/` owns build template sources; root
`templates/README.md` links there for manual users. Optional rationale links use
public documentation URLs. Refer to companion skills by name, not a sibling
file path. A skill-only install never installs slash-command shims. The umbrella keeps
legacy shims for compatibility; concrete groups expose native skill commands.

## Verification

```bash
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .claude-plugin/marketplace.json --strict
bunx skills@latest add ./ --list
```

In disposable workspaces and host configuration directories, install a complete
skill with Skills CLI, install both concrete Claude groups, and install both
Codex marketplace entries. Compare skill directories and group membership
with the source. Check that Skills CLI lists all public root skills, with
the audio skill available only through its plugin. Validate the nested audio
manifests without running ASR.
See [releasing](../releasing.md) for strict extracted-package validation,
reproducibility, archive boundaries and checksums. Remote/pinned commands require
the corresponding remote contents/tag; do not claim unpublished local edits are
already available remotely. Never mutate a maintainer's real agent config during
verification.
