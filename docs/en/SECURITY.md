# Using the application securely

This guide is for GEOLOG GASRATIO@Pixler users and administrators. The application is a
decision-support tool, not a well-control or emergency-shutdown system. Apply your organization's
access, backup, and geological-data handling policies in addition to the guidance below.

As of 28 July 2026, a **P0 repository incident** remains open: `project.geolog.json` and five
LAS-related sidecars have been removed from the current Git index and protected by `.gitignore`,
but previously published history may still contain approximately 31.8 MB of material resembling
real well data and local absolute paths. Do not clone, mirror, or redistribute these artifacts
until the data owner decides their classification and the history is cleaned.

## Before opening or importing data

Treat LAS, GS2/Paradox, WITSML XML/ZIP/EPC, projects, forms, SVG, and images as untrusted until
their source has been confirmed.

1. Work on a copy and retain the fingerprint/SHA-256 when the sender supplies one.
2. Accept a file only from a known counterparty and confirm its expected type and size.
3. Use Import Review to verify the well, index, mnemonics, UOM, NULL rules, warnings, and row
   count before committing.
4. Cancel when an archive is unexpectedly large, contains unknown paths, requests network access,
   reports DTD/entity/external-reference content, or would change more objects than expected.
5. Never enable macros/scripts or follow external links from imported content.

A successful parser does not prove that the data is correct. Compare critical channels and
intervals with the source report. Export creates a separate file and does not replace **Ctrl+S**
for the project.

## WITS0: local or isolated networks only

WITS Level 0 provides no built-in encryption or authentication.

- Keep the TCP server address at its `127.0.0.1` default when GSWITS runs on the same computer.
- For a separate computer, bind a specific trusted interface address.
- Use `0.0.0.0` only after explicit approval on a physically or logically isolated trusted
  network with a firewall allowlist.
- Never expose the WITS0 port to the internet or configure a public-cloud listener or router
  port-forward.
- Before field capture, confirm the IP/port, source owner, raw directory, available disk space,
  and stop/recovery plan.

If an unknown peer connects, stop capture, preserve the journal and raw segments, isolate the
interface, and notify the administrator. Do not delete evidence before triage.

## Remote WITSML and ETP

- Remote WITSML SOAP is allowed only over **HTTPS** and ETP only over **WSS**, with certificate
  and hostname verification enabled.
- A certificate error, expiry, or unexpected hostname is a reason to stop, not to disable
  verification.
- HTTP/WS or disabled verification is acceptable only for loopback (`127.0.0.1`/`localhost`) and
  controlled test fixtures.
- Redirects are not followed. Confirm the final endpoint with the administrator; never move
  credentials to a different URL manually.
- Use a least-privilege read-only account scoped to the expected Well/Wellbore. Bound time,
  response size, and retry count.

Do not connect to an endpoint obtained from an unknown project, email, or diagnostic bundle until
the server owner confirms it through a separate trusted channel.

## Credentials and secrets

Store passwords and tokens through the operating-system credential store. Windows uses Windows
Credential Manager.

- never put a password in a URL, profile name, project file, comment, screenshot, or ticket;
- do not reuse one credential across test and production;
- remove unused entries from the credential store and revoke server-side access;
- if leakage is suspected, stop the remote connection, rotate the secret, and notify the
  administrator;
- before sharing a project, ensure the recipient receives only the required rights through a
  separate process.

Deleting a connection profile does not necessarily delete its operating-system credential; check
the credential store separately.

## Diagnostics and privacy

Logs and diagnostic bundles can contain local paths, user names, server addresses, well
identifiers, mnemonics, and measurement samples even when passwords are excluded.

1. Collect the shortest useful interval and reproduce with an anonymized copy when possible.
2. Inspect every file before sending it; remove credentials, tokens, personal data, commercial
   names, and raw values unrelated to the problem.
3. Do not edit original evidence in place. Keep a protected original and make a separate sanitized
   copy that records what was changed.
4. Transfer the bundle only through an approved protected channel and only to named recipients.
5. Delete temporary copies under the applicable retention policy after the case closes.

Share raw WITS0, GS2, or complete projects only with the data owner's authorization. A normal
report should prefer the version, UTC time, minimal steps, sanitized log, and artifact hashes.

## Reporting a vulnerability or incident

Use the private security channel published by the build distributor or your organization's
administrator. If a dedicated address has not been published, contact the responsible maintainer
privately; do not guess an email address or place an exploit, credentials, real raw data, or an
unfixed vulnerability report in a public issue.

Include:

- package version, operating system, and installation method;
- concise impact and the affected boundary: import, project, WITS0, WITSML/ETP, export, or update;
- minimal reproduction steps and a safe synthetic fixture;
- sanitized diagnostics, UTC time, and artifact hashes;
- whether credentials may be compromised, without including the secret values.

For an active incident, first stop external connections and preserve read-only evidence. Do not
continue testing against a production server without the owner's authorization.

For the known repository incident, the maintainer and data owner must:

1. classify the data, exposure window, affected commits/clones/releases, and notification duties;
2. immediately restrict access or make the remote private during triage;
3. only after explicit authorization, remove the current artifacts, add precise `.gitignore`
   rules, and rewrite all affected Git history;
4. request purging remote caches, forks, mirrors, CI artifacts, and release archives and verify
   the reachable copies;
5. replace real material with minimal synthetic fixtures carrying explicit provenance.

Deleting files only from HEAD is insufficient: earlier commits and external copies continue to
expose the content. Do not rewrite history or delete evidence without coordination with the data
owner and incident-response lead.

## Pre-field checklist

- the known repository incident has been classified, the remote is restricted, and real fixtures
  cannot enter new commits;
- file sources and network peers are confirmed;
- WITS0 remains on loopback or an isolated allowlisted network;
- remote WITSML/ETP uses verified HTTPS/WSS with no redirects;
- credentials exist only in the system store and have minimum rights;
- raw/project directories are protected and free space and backup have been checked;
- diagnostic-sharing rules and incident contacts are agreed;
- test capture, controlled close, **Ctrl+S**, and reopen pass after configuration.
