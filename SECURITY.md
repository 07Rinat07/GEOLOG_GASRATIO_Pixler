# Security policy

## Supported version

Security fixes are developed for the current `0.7.93` line. Older development snapshots and
historical project schemas must first be reproduced on the current version. This application is
a decision-support workbench; it is not a certified well-control or emergency-protection system.

## Report a vulnerability privately

Do not open a public issue containing an exploit, credentials, well data, personal data, local
paths or proprietary vendor material. Send a minimal report to `ura07srr@gmail.com` with the
subject `GEOLOG security report`.

Include:

- affected version and operating system;
- input type or network adapter involved;
- safe reproduction steps and expected/actual result;
- impact and whether data may already have been exposed;
- a small synthetic reproducer where possible.

Do not send live credentials or customer datasets. Replace sensitive values and share any
necessary artifact through a separately agreed private channel. The maintainer should acknowledge
the report, classify impact, preserve evidence, prepare a regression test and coordinate
disclosure after a fixed build is available.

## Data handling

- Projects, LAS files, WITS/WITSML captures, exports, diagnostic bundles and raw sidecars are user
  data, not source code. They must not be committed unless they are explicitly approved,
  synthetic and documented test fixtures.
- Credentials remain outside project files. Remote WITSML uses HTTPS with verified TLS; WITS0
  listens on loopback by default and remote bind requires an isolated trusted network.
- The application does not execute scripts embedded in a project. Importers reject unsupported
  active content and enforce resource limits before proportional allocation where implemented.
- ETP profiles bound each WebSocket message and each multipart response by encoded bytes, part
  count, and assembly time. Exceeding a multipart limit fails pending requests and closes the
  session instead of retaining or dispatching late parts.
- Logs and support bundles must not traverse project asset directories or include secrets.

If confidential data is suspected in Git history, stop further distribution, classify the data,
restrict remote access, rotate any exposed secret, preserve an incident record, remove the data
from the current tree and history, purge accessible caches/releases where possible, and replace it
with synthetic fixtures. Deleting only the latest copy is not sufficient.

## Release security gate

Before a stable release:

1. create a clean Windows x86-64/Python 3.11 environment from the reviewed, fully
   pinned and hashed runtime `requirements/release.lock`;
2. run Ruff, mypy, the full pytest suite, documentation audit and compileall;
3. run dependency, secret and static scans and produce an SBOM;
4. run resource-bound/fuzz regressions for project, Paradox, XML/WITSML, ZIP/EPC, spreadsheet,
   WITS0 and ETP inputs;
5. verify that the source/package contains no user projects, raw captures, credentials or local
   absolute paths;
6. preserve the commands and machine-readable results with the release manifest.

The reproducible gate is:

```text
uv pip sync requirements/release.lock --python .venv --require-hashes
uv pip install --python .venv --no-deps --no-build-isolation --editable .
python tools/release_security_gate.py
```

The security command emits dependency-audit JSON, a CycloneDX JSON SBOM, detect-secrets output,
Bandit JSON and a manifest containing the lock SHA-256 and every exit status. Reports belong only
under the ignored `build/ci-artifacts` directory and in the corresponding CI artifact; do not
commit generated scan output or place it in `docs`.

User-facing summaries are available in
[Russian](docs/ru/SECURITY.md), [Kazakh](docs/kk/SECURITY.md) and
[English](docs/en/SECURITY.md).
