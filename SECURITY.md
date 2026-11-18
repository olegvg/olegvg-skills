# Security policy

## Supported code

Security fixes target the current default branch. Older versions should be updated; backports are not guaranteed.

## Reporting a vulnerability

Contact [Oleg Gaidukov](https://www.linkedin.com/in/ahaidukof/) privately before disclosing sensitive details. Include the affected version or commit, synthetic reproduction steps, expected and actual behavior, and impact. Never send credentials, private corpus files, recordings, transcripts or generated knowledge bases.

Use [GitHub issues](https://github.com/olegvg/olegvg-skills/issues) for ordinary bugs that can be described publicly. Do not attach sensitive evidence.

## Scope

Reports can cover instructions, corpus handling, local mobile-environment helpers, the audio runtime, plugin installation and release tooling. Release ZIPs use an explicit file inventory and reject symlink inputs; local environments, caches, recordings and private workspaces are excluded. Checksums detect asset corruption; they do not authenticate the publisher.

Agent hosts, model services, optional backends and downloaded model code have their own security policies. See [PRIVACY.md](PRIVACY.md) for data boundaries. The audio plugin requires explicit consent for OpenAI uploads.
