# Application diagnostics

GEOLOG GASRATIO@Pixler writes a persistent rotating log from version 0.7.51.

Use **Help → Open log folder** to open the directory. The current file is `geolog.log`; older
files are kept as numbered rotations. `geolog-crash.log` is reserved for Python faulthandler/native
crash information.

Use **Help → Build diagnostics bundle…** when reporting a problem. The generated ZIP contains:

- current and recent application logs;
- Python, operating-system and application-version information;
- safe runtime state such as current dataset identifier, track count and pencil/form transaction
  state.

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
