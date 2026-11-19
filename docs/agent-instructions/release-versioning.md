# Release versioning

Read [the release guide](../releasing.md) before changing packaging or preparing a
release. Tools use Python 3.10+ standard library; runtime skills do not depend on
the build tools.

## Version surfaces

Root `plugin.json` is canonical. Keep numeric X.Y.Z synchronized in both umbrella
host manifests, the umbrella/concrete-group Claude marketplace entries, Codex
umbrella marketplace metadata and Claude marketplace metadata.version.

The audio plugin versions independently. Its Claude manifest and marketplace
entry share the base version; its Codex manifest can retain Codex build metadata.
Do not change its version as part of an umbrella release.

## Release boundary

A prepared version is not a published release. Version bumps, commits, tags,
pushes and publication are separate operations requiring explicit user release
authorization. Never retarget an existing tag without explicit repair approval.
After an authorized release commit, create and push the matching annotated
`vX.Y.Z` tag; the release workflow validates that exact state. No AI coauthor
trailers should be added.

`.github/workflows/release.yml` replaces the old desktop-only shell packager.
It builds the full runtime ZIP, all ten portable root skill ZIPs, notes and
checksums. The five desktop-compatible skill asset names are preserved;
`kb-record-decision` and `kb-maintain` require capable agent hosts and companion
skills. `mobile-test-environments` requires a host with access to local devices and
installed mobile tools. Audio is never a standalone skill ZIP.

## Checklist

1. Review CHANGELOG.md Unreleased and the explicit scripts/release_inventory.py.
2. Update all umbrella metadata versions together when preparing a new release.
3. Run validator, release tests, native checks, installer smoke and preview build.
4. Check complete archive contents, deterministic bytes and every checksum.
5. Only with explicit release authorization: commit, create/push the annotated
   matching tag, and confirm the release workflow/publication outcome.
