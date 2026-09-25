# Application diagnostics

GEOLOG GASRATIO@Pixler writes a persistent rotating log from version 0.7.51.

Use **Help → Open log folder** to open the directory. The current file is `geolog.log`; older
files are kept as numbered rotations. `geolog-crash.log` is reserved for Python faulthandler/native
crash information.

Use **Help → Build diagnostics bundle…** when reporting a problem. The generated ZIP contains:

- current and recent application logs;
- application version, build identity and commit SHA; when the SHA cannot be established
  deterministically, the value is explicitly `unknown`;
- the unique session ID for the current startup, plus Python and operating-system information;
- safe runtime state such as current dataset identifier, track count and pencil/form transaction
  state.

`geolog.log` timestamps are emitted in UTC with a `Z` suffix. Each application run is separated
inside `geolog-crash.log` by `GEOLOG SESSION START/STOP` boundaries containing the session ID,
build identity and commit. This distinguishes new runs from legacy crash entries and distinguishes
two builds with the same package version but different SHAs.

Release wheels carry an immutable commit stamp inside the installed package. Build identity resolution
uses explicit build environment first, then the stamped package identity, package VCS metadata, a
local Git checkout, and finally explicit `unknown`. The Windows release gate builds and installs
the wheel in an isolated environment outside the source checkout and verifies the generated
diagnostics bundle without relying on `.git`.

When the WITS0 window is open, `system-report.json` also receives an allowlisted diagnostic snapshot only: profile ID/version and SHA-256, encoding, selected mode, discovery fingerprint, aggregate capture/acquisition counters, the stable code of the last rejected frame, and the latest aggregate count of points actually submitted to the live plot. Host/port/peer identity, raw paths/files, source name, WITS measurement values, acquisition session ID, and free-form last-error text are not included in this snapshot.

The bundle does not include LAS samples, project assets, saved forms or project files. File paths
and project/dataset names may still appear in normal log messages, so review the ZIP before sharing
it outside the support workflow.

For a reproducible report, perform the failing action, create the diagnostics bundle immediately,
and attach the ZIP together with a brief description of the clicks that caused the problem.

## Clearing accumulated data

Use **Help → Clear diagnostics data…** to remove only service-owned data accumulated in the
application profile:

- the current log, rotated logs, and the crash log;
- saved text reports produced by import diagnostics;
- empty diagnostics subdirectories owned by the application.

The application asks for confirmation and then reports the number of deleted files and the space
freed. Logging resumes automatically without restarting the program. Projects, LAS files, user
forms, settings, and diagnostics ZIP bundles previously exported by the user are not removed.

To prevent unbounded growth, the application automatically retains no more than the 30 newest
import-diagnostics reports of each type.
