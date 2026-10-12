# External geology format fixtures

This directory is a **test corpus**, not field data for geological interpretation.
All files originate from public upstream projects at **pinned commit IDs**; the
original upstream paths, exact Git blob SHA-1, expected file size, and intended
scenario are recorded in [manifest.json](manifest.json). Git blob SHA-1 is
computed on the **original bytes**, including binary bytes and CRLF. The
download script also prints SHA-256 of every fixture.

| Folder | Formats / intended use | Source |
| --- | --- | --- |
| `las/1.2` | Original LAS 1.2 and wrapped records | [lasio](https://github.com/kinverarity1/lasio) (MIT) |
| `las/2.0` | Normal, wrapped, and TAB-delimited LAS 2.0 | [lasio](https://github.com/kinverarity1/lasio) (MIT) |
| `las/3.0` | Single section, vendor-like, multi-section edge cases | [lasio](https://github.com/kinverarity1/lasio) (MIT) |
| `dlis`, `lis79` | DLIS & LIS79 structural records (including incomplete DLIS) | [dlisio](https://github.com/equinor/dlisio) (LGPL-3.0) |
| `segy`, `su` | Small SEG-Y, little endian, broken SEG-Y, Seismic Unix | [segyio](https://github.com/equinor/segyio) (LGPL-3.0) |

See the upstream repository licenses and provenance documents. Retain the
upstream attribution when redistributing these fixtures. dlisio's
`python/data/README.rst` says the examples are *mostly synthetic*; selected
files in this corpus are specifically structural test records, not claims
about an actual producing well. Segyio says its small example data are
generated and physically nonsensical.

## Download and integrity verification

From the repository root, on any machine with internet:

```powershell
python tools/fetch_external_format_fixtures.py
python tools/fetch_external_format_fixtures.py --check
python tools/fetch_external_format_fixtures.py --group las --check
```

A file's source URL is fixed to the upstream Git commit, never to a mutable
branch. **Both exact size and Git blob identity must match** before the file
is accepted or installed. A corrupt/missing file causes offline `--check`
to fail; failed verification never silently skips data. Files are never
executed. Downloads are capped at 5 MiB per fixture and are atomically
replaced. Source repositories are explicitly allowlisted.

## What this does *not* prove

The presence of a test file does not mean its format is implemented in
DIGITAL GEOLOG GASRATIO&PIXLER. LAS 3.x parsing and DLIS/LIS79/SEG-Y/SU
preview, conversion, editing and lossless writer capabilities require
independent implementation and acceptance tests. Invalid samples are
**negative** cases, not valid parser fixtures. These examples are not a
substitute for operator-approved field logs, real vendor dialects,
cross-tool round-trip tests, or physical printing.
