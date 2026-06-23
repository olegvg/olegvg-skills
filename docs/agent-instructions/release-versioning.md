# Release Versioning

Use this before bumping versions, tagging releases, or changing release packaging.

## Version Surfaces

Manifest versions use plain semver without a `v` prefix. Update these together:

- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`
- every `plugins[].version` entry in `.claude-plugin/marketplace.json`

GitHub releases use tags with a `v` prefix, such as `v0.6.0`. The Claude Desktop release workflow derives zip artifact versions from the tag name:

```bash
VERSION="${TAG#v}"
```

Every version bump is incomplete until a matching git tag exists and is pushed. For manifest version `X.Y.Z`, create tag `vX.Y.Z` on the commit that contains the bump and push that tag. The release workflow is wired to tag pushes:

```yaml
on:
  push:
    tags: ['v*']
```

Use annotated tags for releases:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Do not create the tag before committing the version bump. Do not move or replace an existing release tag unless the user explicitly asks for release repair.

`.agents/plugins/marketplace.json` and `skills.sh.json` currently do not carry release version fields. If version fields are added there later, include them in the same bump.

## Release Packaging

`.github/workflows/release-desktop-skills.yml` packages standalone Claude Desktop skills. Keep its `SKILLS=(...)` list aligned with README promises.

Current desktop-packaged skills:

- `kb-build`
- `kb-query`
- `kb-refresh`
- `kb-check-drift`
- `simplify-code`

`kb-record-decision` and `kb-maintain` are intentionally excluded because they depend on plan-document layout or orchestration.

## Bump Checklist

1. Update all manifest version fields together.
2. Check release workflow package list if any skill compatibility changed.
3. Search for old and new versions:

```bash
rg --hidden -n --glob '!.git/**' '<old-version>|<new-version>'
```

4. Validate JSON manifests.
5. Run `git diff --check`.
6. If installer-facing metadata changed, run `npx skills add ./ --list`.
7. Commit the version bump.
8. Create and push the matching annotated git tag, e.g. `git tag -a vX.Y.Z -m "vX.Y.Z"` then `git push origin vX.Y.Z`.
9. Confirm the GitHub release workflow ran for the pushed tag.
