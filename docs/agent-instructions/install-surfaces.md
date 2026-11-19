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
All entries use `strict: true`; current Claude rejects strict:false with a
manifest plus marketplace component declarations. See the
[official precedence rules](https://code.claude.com/docs/en/plugins/marketplace-reference). Keep the umbrella first, then concrete groups: Skills CLI assigns each
skill to the last entry mentioning it. A root skill belongs to exactly one
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
bunx skills@latest install ./ --list
```

Then test an actual project-scoped Skills CLI install and concrete Claude group
installs in disposable workspaces/config directories. Confirm all nine root
skills, complete references/templates, expected groups and no audio skill in
Skills CLI discovery. Validate the nested audio manifests without running ASR.
See [releasing](../releasing.md) for strict extracted-package validation,
reproducibility, archive boundaries and checksums. Remote/pinned commands require
the corresponding remote contents/tag; do not claim unpublished local edits are
already available remotely. Never mutate a maintainer's real agent config during
verification.
