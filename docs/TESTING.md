## Qt #544 — atomic partial native replay artifacts

The manual `tools/replay_windows_qt_native.py` process now writes every
partial `results.json` snapshot to a sibling temporary file, flushes and
fsyncs that file, then atomically replaces the destination. If serialization
or Windows replacement fails, the previous complete JSON remains intact and
the diagnostic fails rather than implying success. Temporary files are
removed on both successful and failed replacements. Regression tests
verify replacement and a simulated Windows replace failure. No required
Windows Release Gate job or production application code changes.

## Qt #544 — partial replay result integrity

`results.json` is updated after each child so a killed Windows replay
can still upload partial evidence. `all_passed` MUST remain `false`
until `completed == expected` and every child passed. Successful
early children must not create a false success summary if a subsequent
child fails or the run is interrupted. `tests/test_replay_windows_qt_native.py`
exercises interim snapshots, a complete success, and an interruption
after the first successful child. The mandatory Release Gate is unchanged.

## Qt #544 — bounded manual replay wall-time budget

With five repetitions and mode=both, the manual diagnostic runs at most
15 child processes. Each child has a strict 360-second timeout, so cumulative
child-process time is bounded to 90 minutes, leaving 30 minutes for Windows
environment setup and artifact upload under the workflow's 120-minute
job timeout. A timeout fails the diagnostic, remains in `results.json`,
and does not prevent subsequent test executions. The workflow contract
cross-checks these limits so changes cannot silently exceed the job budget.
The original Release Gate remains unchanged.

## Qt #544 — manual Windows native test replay

Use Actions → Windows Qt native replay (manual) → Run workflow when a
native PlotItem/ViewBoxMenu 0xC0000005 recurs. Only workflow_dispatch is
supported; this workflow does not run on push or pull_request and does not
substitute for the three mandatory Windows Release Gate jobs.

The selector list in tools/replay_windows_qt_native.py is fixed to the
dataset-merge undo test and the repeated-tablet-rebuild test. Select 1–5
repetitions and one of: isolated (each selector in a fresh child),
sequence (both selectors together in one child) or both. Results are
stored in qt-native-replay-<run_id>-<attempt> for seven days, with
per-execution logs and results.json (selector, iteration, exit code,
hex Windows exception and timeouts), plus pinned native-runtime.json.
A failed child or timeout fails the workflow, never marked as pass merely
because another iteration succeeded.

The runner-only WER minidumps, if present, are stored separately as
qt-native-dumps-<run_id>-<attempt> for three days, DumpType=1,
DumpCount=2. Handle dumps as process memory evidence, do not collect
production geology data. Version and stack correlation, including actual
minidump availability, must be established before a root-cause claim.
The original Release Gate, including native subprocess exit propagation,
remains unchanged.

## Qt #544 — complete rollback for partially created tablet tracks

If creation of one rendered track fails, `TrackLifecycleCoordinator.create_entries`
now uses the existing `dispose_entries` safety path to release all previously
created tracks in reverse order. A failed rollback or failed DeferredDelete
settlement is reported through the optional `on_rollback_error` callback;
neither suppresses the original render failure or prevents subsequent
cleanup. The production tablet logs cleanup exceptions under
`tablet.track.rollback.failed`.

Two independent `tests/test_track_lifecycle.py` regressions cover rollback
and settlement failures, original exception propagation, reverse order, and
the per-track report hook. Existing Windows Release Gate criteria stay
unchanged. This mitigates an additional unhandled cleanup path but does not
prove the native Qt/pyqtgraph #544 root cause.

## Qt #544 — disposal settlement on failed track cleanup

`TrackLifecycleCoordinator.dispose_entries()` attempts its per-entry
DeferredDelete settlement even when the preceding `dispose(entry)`
raises after scheduling Qt deletion. Each settlement runs before the
next entry's disposal, in reverse track order. Disposal and settlement
errors are passed to the existing `on_error` callback; other tracks
must still be cleaned up. `tests/test_track_lifecycle.py` exercises
both failure paths with injectable settle callbacks, independent of Qt.
This does not prove that all native access violations are fixed.
Exact-head Windows Quality, GUI/HiDPI/PDF and Security remain required.

## Qt #544 — native Windows runtime identity for crash correlation

The Windows Quality job calls `tools/capture_windows_native_runtime.py`
from a separate venv Python process before pytest, saving
`build/ci-artifacts/quality/native-runtime.json` to the existing 30-day
quality artifact. It reports the source PR HEAD SHA (or push SHA), Python,
OS release/architecture, Qt runtime, PySide6, shiboken6, pyqtgraph and NumPy
versions. The report contains no absolute paths, operator data or environment
variables. Missing pinned packages or an invalid commit cause a failed step.
`tests/test_capture_windows_native_runtime.py` uses injected version sources
and verifies exact content, SHA rejection and JSON file output; the workflow
contract pins ordering, output path, source SHA and exit propagation.
This metadata does not establish the root cause of Qt #544 and does not prove
a WER dump was collected; leave the original jobs and failure codes intact.

## Qt #544 — Windows native crash evidence

The Windows quality job configures per-application WER LocalDumps for
`python.exe` on the disposable Actions runner only. DumpType=1 requests
minidumps; DumpCount=2 bounds retained files. The separate
`release-native-<run_id>-<run_attempt>` artifact retains available dumps for
three days. No dump is expected on a successful run. A missing dump does not
turn a failed test into a success; original test commands and exit codes remain.
The configuration follows [Microsoft WER documentation](https://learn.microsoft.com/en-us/windows/win32/wer/collecting-user-mode-dumps).

After a native failure, inspect the artifact with WinDbg and correlate its
exception stack and module versions with `release-quality-<run_id>/pytest.txt`.
WER capture is not guaranteed for applications with custom crash reporting or
automatic debugging; confirm an actual dump before claiming capture works.
Do not apply the runner registry snippet to a developer or field workstation.
Minidumps can contain process stack data; these artifacts are diagnostics for
synthetic CI tests, not a mechanism for collecting user project data.
Successful retries and local replays do not close Qt #544.

## PRINT-STYLE-01 — manual Masterlog caption override after type changes

The same suite also opens the orientation popup and presses Enter on its
current item in RU/KK/EN. Both horizontal and bottom-up selections must survive
a later type change even though the combo-box index did not change. This
regression failed before connecting the user activation signal.

`tests/test_masterlog_columns_dialog.py` covers RU/KK/EN new-column type
changes before a user override (automatic bottom-up geology/horizontal text),
then top-to-bottom and horizontal explicit selections surviving subsequent
type changes. The title vertical position remains independently editable.
Existing saved columns and templates are unchanged. This does not establish
physical header-template dimensions or solve intermittent native Qt #544.
All three Windows Release Gate jobs must pass on the exact PR HEAD and
current main before merging.

## PRINT-STYLE-01 — Masterlog captions, empty-header merging and editor scroll

User-provided 150-page Maksat M-1 PDF, first page: vertical rock captions are
on the upper part of a large unused synchronized curve-header band. Regression
covers combined header height for a no-curve geology track versus a curve track,
unchanged plot-alignment sum across rerenders, factory/compact bottom-to-top
captions, explicit form title direction surviving application, RU column editor
scroll widgets, and per-column manual direction selection. The visible controls
support top-to-bottom, bottom-to-top and horizontal orientations. Application
source import of PyMuPDF uses its supported `pymupdf` name; existing PDF API
calls are aliased internally without changing document output.

Latest main e41129c2207d had failed native Windows Quality with Qt/pyqtgraph
0xC0000005 in `test_tabular_export_output_language.py` while GUI/PDF and
Security were successful. This is NOT a passing main gate: do not merge a
feature PR until the latest main and PR exact SHA both have three successful
Windows jobs. Reproduce actual page/header match with the original source
Masterlog template separately; the 150-page PDF alone is insufficient for
physical printer/row-template sign-off.

## PRINT-STYLE-01 — Masterlog automatic page-density default

New print settings and factory Masterlog A4 default to Auto, including
when only legacy global fixed-50-m settings exist; an explicit per-form
manual choice remains unchanged. Qt regression in
`tests/test_print_center.py` covers RU/KK/EN Full-range A4 Fit hiding the
inactive fixed interval, manual-toggle restoration, and roll-media gating.
`tests/test_user_profiles.py` covers default, legacy-global and saved
per-form precedence. Exact-head three Windows Gate and post-merge main CI
are required; 200-page guard, source LAS and physical printer acceptance
are unchanged.

## INTERP-GEO-01 — source ID provenance integrity

Measured gas/geology interval evidence requires non-empty text IDs for
lithology intervals, cuttings samples and stratigraphy records before
permissive report-snapshot conversion. The regression matrix in
`tests/test_interpretation_geology_interval_evidence.py` covers 54 bad
representations (3 source types × in/out MD × 9 values) and a valid Cyrillic
ID/coverage case. Malformed source IDs are rejected without modifying well,
MD or gas curves. Full Windows Quality, GUI/HiDPI/PDF and Security gates
on the exact PR HEAD and post-merge main remain mandatory.

## INTERP-GEO-01 — lithotype identifier type validation

`tests/test_interpretation_geology_interval_evidence.py` checks 28 source
malformations (lithology or cuttings, within/outside MD selection, seven
invalid identifier types), plus a valid-evidence provenance and coverage
regression. Unlike the permissive report snapshot, interval evidence must
reject non-text lithotype IDs before converting them to strings. The tests
assert that original well, MD and C1 samples are not modified. The full
module and all three exact-HEAD Windows Release Gates remain required.

## INTERP-GEO-01 — source description integrity

`tests/test_interpretation_geology_interval_evidence.py` rejects non-text
lithology/cuttings descriptions before snapshot coercion, inside and outside
the selected interval. Regressions preserve source well, MD and curve arrays.
None/blank descriptions do not create cuttings coverage without components;
valid multiline text and independent lithotype evidence retain their coverage.
The new cases reproduced 20 failures before the fix, with eight valid-input
cases passing. Run the full module and all three exact-HEAD Windows gates.

## PRINT-STYLE-01 — Word text line breaks and tabs

`tests/test_docx_text_whitespace.py` validates explicit `<w:br/>` for LF,
CRLF and CR, `<w:tab/>` for tab, and `<w:t xml:space="preserve">`
for ordinary text after XML 1.0 filtering. Covers ordinary paragraph,
tables and polished paragraphs, plus actual ZIP/XML DOCX export in
RU/KK/EN and portrait/landscape. Checks source strings/identity unchanged.
Require three exact-HEAD Windows Release Gate jobs and green post-merge main.

The ordinary export includes the localized project label in the same run as
the project name. Its package regression checks that prefix plus the complete
ordered text/break/tab sequence; the polished title checks the unprefixed text.
This corrects the six ordinary-export expectations from PR #745 CI 40275751613
without relaxing whitespace or source-immutability checks.

## PRINT-STYLE-01 — isolate all Word UI orientation scenarios

PR #742 run 40246626008: native 0xC0000005 occurred in the sixth
parametrized Word UI handoff variant. The Windows runner isolates functions,
not parameters. Split the same six RU/KK/EN x portrait/landscape checks
into separate top-level tests, preserving assertions and creating one
Qt process for each under the existing runner. New runner contract tests
the six exact function selectors and one-function-per-process batches.
This is CI isolation, not proof of root cause repair (Qt #544).
Merge only after three exact-HEAD Windows Release Gates succeed.

## PRINT-STYLE-01 — Word XML 1.0 character integrity

New shared Word XML text sanitizer filters only characters outside the XML 1.0
Char production before XML escaping. Apply to ordinary body and custom
classification-audit XML, polished cover/identity and common footer text.
Regressions live in the already Windows-isolated Word orientation test module:
control characters, surrogates and U+FFFE/U+FFFF, valid Unicode boundaries,
RU/KK/EN × standard/OPUS × portrait/landscape × ordinary/polished actual
DOCX package parsing, escaped XML syntax and unchanged source objects.
Run the exact-HEAD three-job Windows Release Gate and post-merge main CI.
Do not disable native tests or treat this as resolution of Qt #544.

## PRINT-STYLE-01 — Windows isolation of Word-orientation regression

PR #741 showed 0xC0000005 in the Windows quality gate on the mixed
Qt/Office shard (first while loading an Excel workbook, then during
construction of a gas-ratio workspace). The current Windows runner
already isolates known native-sensitive tests by function. Apply that
existing mandatory isolation to `test_gas_ratio_word_page_orientation.py`
and `test_generic_report_control.py`; each selected test function,
including every parameter variation, still executes under pytest.
Native failures remain failures with their selector and exit code logged.
Validate runner batching contract and all three Release Gate jobs on the
exact new PR head; this does not establish the root cause of Qt issue #544.

## PRINT-STYLE-01 — Word table width apportionment

## PRINT-STYLE-01 — gas Word A4 page orientation

Default Word export of gas ratios and interpretation reports is A4 portrait.
Users may select landscape in the report workspace; the polished cover and
report body must use the same selected orientation. RU/KK/EN standard and
OPUS actual DOCX exports must validate page sizes of every sectPr and
matching tblW/tblGrid/tcW and footer widths, bounded to 9600 twips in
portrait, with the old landscape option intact. Test language-choice
persistence, invalid-orientation refusal, report source immutability and
no change to PDF/system print. Exact HEAD Windows CI (all three jobs)
and post-merge main CI are required; physical print acceptance separately.


Regression `tests/test_docx_table_print_bounds.py`: very skewed positive
integer weights (including large integers), more than 14 000 one-twip columns,
positive cell widths, exact max 14 000 twips and equality of tblW/tblGrid/tcW
in actual XML for header and body rows. Valid non-overflow layouts remain
unchanged. Run the module and all three exact-head Windows Release gates
before merge, then require a green main. Physical printer acceptance is
independent.

## INTERP-GEO-01 — optional stratigraphy name/rank validation

For explicit measured gas/geology evidence, the optional source
`StratigraphyInterval.name` and `rank` must be text or `None`.
Previously non-text values could raise an unrelated `AttributeError`
on `.strip()`; malformed metadata was not checked in records with a
blank code. Fail closed before snapshot/export, without changing the
source well, measured MD axis or curves.

Data-only regressions in `tests/test_interpretation_geology_interval_evidence.py`
cover both fields, five invalid types, source intervals inside/outside
selection, blank codes, and allowed empty/ordinary/missing text. Signed
export regressions in
`tests/test_interpretation_geology_evidence_signed_pdf.py` cover
RU/KK/EN × new/existing PDF/passport × both fields with byte-identical
existing files after rejection. Run both modules and all three Windows
Release gates on exact PR HEAD, then verify the new main gate. Field
geology and Qt #544 remain independent.

## INTERP-GEO-01 — reject corrupt cuttings component percentages

Measured gas/geology correlation now fails closed if any raw cuttings
component percentage is not a finite numeric scalar between 0 and 100,
including the exact endpoints 0 and 100. NaN/Inf, negative/out-of-range,
text, boolean, vector or missing values must never disappear into a report
snapshot and leave misleading partial source coverage. Source components
are not normalized to sum to 100: incomplete measured records stay incomplete.

`tests/test_interpretation_geology_interval_evidence.py` tests malformed
components both within and outside the gas interval, valid scalar values,
source/curve immutability and unchanged interval coverage. Signed-PDF
regressions in `tests/test_interpretation_geology_evidence_signed_pdf.py`
exercise RU/KK/EN x new/existing PDF and passport, requiring no new or
replaced artifacts on rejection. Require the full three Windows Release
jobs on the exact PR SHA and post-merge main. These are software-input
integrity tests, not field or petrophysical acceptance.

## INTERP-GEO-01 — request MD interval scalar validation

The measured-gas/geology interval API now refuses numeric-looking text,
booleans, object scalars, non-scalar arrays and missing requested MD
boundaries **before** applying float conversion. Both top and bottom are
checked individually; explicit Python/NumPy numeric scalars still work.
The test matrix verifies the same finite, increasing metre-MD interval
coverage and unchanged well, source axis and curve values. These are
application-level request validity checks, not physical depth tie acceptance.
No original LAS/GIS/GTI/LBA is rewritten and there is no implicit unit
conversion. Test file: `tests/test_interpretation_geology_interval_evidence.py`.
Full Windows Quality, GUI/HiDPI/PDF and Security gates are required on the
exact PR HEAD, followed by the post-merge main gates.

## INTERP-GEO-01 — invalid source geology MD bounds fail closed

`tests/test_interpretation_geology_interval_evidence.py` verifies that
NaN/positive and negative infinity, numeric-looking text and boolean source
interval bounds in lithology, cuttings and stratigraphy cannot silently
disappear from measured gas/geology correlation. Valid out-of-range source
records still do not inflate measured coverage; original source records,
MD samples and curves remain unchanged. Zero-length records retain the
existing no-overlap behavior.

`tests/test_interpretation_geology_evidence_signed_pdf.py` additionally
checks RU/KK/EN × new/existing PDF/passport for non-finite geology record
bounds introduced after explicit selection. The signed export must reject
before creating/replacing either artifact, preserving every existing byte.
Run both files with `python scripts/run_tests.py -p no:cacheprovider
tests/test_interpretation_geology_interval_evidence.py
tests/test_interpretation_geology_evidence_signed_pdf.py -q`, then require
the three Windows Release jobs on exact PR HEAD and post-merge main.
This is software source-integrity QA, not field or physical acceptance;
native Qt issue #544 remains open.

## INTERP-GEO-01 — reject incomplete MD axes before measured geology correlation

The data-only geology interval evidence service requires a one-dimensional
numeric metre-MD axis with at least two samples and **all** source coordinates
finite. It no longer discards NaN/Inf rows to derive min/max from a partial
axis or silently converts numeric-looking text/object arrays to measured MD.
The same guard runs when previously selected evidence is reverified for a
signed report. Regression tests cover NaN/positive and negative infinity,
coercible strings, object dtype, a 2-D axis, and preserved descending/stationary
MD acquisition order. No source samples, LAS/GTI or geological observations
are rewritten; a green test is not field alignment acceptance.

## GIS reference calibration: MD axis evidence revision

Session-local GIS calibration now binds the saved MD axis mnemonic, index
type/role, metre-unit spelling, confidence and evidence tuple, in addition to
the complete depth/curve array fingerprints and existing source review.
Changing any axis provenance after operator review invalidates that
calibration, even if the arrays, IDs, curve version and source-review summary
are unchanged and both unit spellings are eligible. GR/RHOB regressions
cover the evidence, confidence, equivalent unit spelling and mnemonic.
The existing modal-inventory regression covers an axis-evidence change
in RU/KK/EN: the old result clears, while operator inputs and source edits
remain intact. This is a source-integrity guard, not a depth conversion or
confirmation of physical MD alignment.

## GIS reference calibration: dtype and shape integrity

The calibration binds the NumPy dtype and shape as well as the complete MD
and curve sample bytes to its session-local source fingerprint. Raw-byte-only
SHA-256 could not detect changing a float64 curve's dtype to int64 in place:
identical bytes, identity, version, sample count and source review would be
accepted while numerical meaning changed. The GR and RHOB regressions ensure
such unchanged-byte reinterpretation invalidates the original calibration.
No source array is modified by the fingerprint; this is not an instrument
calibration or petrophysical method change.

## GIS preview integrity on return from inventory (INTERP-GIS-01)

`tests/test_gis_reference_dialog.py` checks the source-only (no calibration)
preview after returning from the modal inventory. In RU/KK/EN it preserves
entered operator evidence/parameters but re-reads the exact selected source
row: unchanged data stays visible, in-place sample/MD edits refresh, a
new NULL becomes unavailable, and a stale or removed channel clears its
preview and shows the existing QC reason. No calculation, implicit channel
switch, data rollback or LAS/project write occurs.

## Windows Qt native isolation — well numerical save gate

After main Release gate 40089829503 (after PR #723, attempt 1) reported an access violation
(0xC0000005) in pyqtgraph ViewBoxMenu while running the fifth parameter of
`test_main_window_numerical_save_gate`, the five existing outcomes (save,
no selection, disk full, external change and cancel) are run as separate
pytest functions. The Windows native-heavy runner already grants one child
process per test function for this file. A runner contract test verifies that
all five cases remain mandatory and get distinct processes; test assertions
and the application save workflow are unchanged. A green CI gate is necessary,
but not evidence that the underlying native Qt issue #544 is resolved.

## GIS calibration source integrity — in-place sample changes

A session-local GIS reference calibration now fingerprints the complete selected
curve as well as the MD axis. The four regression cases in
`tests/test_gis_reference_calibration.py` cover GR and RHOB with in-place edits
to the selected and unselected finite sample rows without a version increment.
An existing calibration must fail closed, while array identity and the original
version remain unchanged; creating a new calibration requires explicit review.
These checks do not establish instrument calibration or field interpretation.

## GIS source inventory operator view — INTERP-GIS-01

Returning from the inventory must revalidate an existing sample against its
original calibration. Unchanged sources preserve the result; stale/removed
curves and in-place edits to MD or another curve row invalidate it without
recalibration or reverting source edits. RU/KK/EN dialog tests exercise changes
inside the modal loop and verify that all entered evidence/parameters survive.

`tests/test_gis_reference_las_reopen.py` exercises the external wrapped LAS 2.0
fixture through real import, ProjectController save/open and the GIS dialog in
RU/KK/EN for JSON and package projects. It checks the actual descending GR row
and an independently specified IGR result with synthetic calibration, unchanged
arrays/metadata/source bytes/project bytes, clean state and fresh empty dialog
calibration. The fixture's unknown density unit must remain blocked after reopen.
This software acceptance does not certify field calibration or interpretation.

Selected-source review also previews exactly the requested original row before
calibration. Tests cover RU/KK/EN, ascending/descending MD, NULL/Inf, arrays
shortened after opening, stale/removed curves and unverified axes. Selection
changes clear the preview; rechecking must never retain an earlier value or
substitute a neighbor. Preview leaves calibration fields and arrays unchanged.

The one-sample dialog's selected-source review must work before calibration
fields are filled. RU/KK/EN regressions cover incompatible family/unit scale,
removed curves, missing identity, unverified MD and stale curves. Rechecking
reads live data and clears previous results without clearing entered evidence;
method/channel changes clear the review. A successful prior review must not
authorize calculation after a source becomes stale. Existing calibration tests
remain authoritative for parameter and sample constraints.

Missing or whitespace-only curve IDs must produce an explicit inventory QC
warning in RU/KK/EN before reference calculation. Service and dialog tests
verify consistency with the existing reference-input rejection, preservation
of the original ID and source arrays, and acceptance of imported provenance
whose source dataset ID differs from the current dataset.

Axis-details regressions cover the separate Depth axis tab in RU/KK/EN,
including an empty curve catalog and no selection. Saved evidence is literal
text, missing evidence stays explicit, and an unverified ft axis retains its
unit and QC warning. Clearing curve selection must preserve axis details.
Live evidence/unit changes must not mix with the opening QC snapshot;
reopening refreshes both. No alignment or geological approval is inferred.

The selected-curve details regressions also cover RU/KK/EN source IDs,
saved mnemonic/family bindings, provenance, version and literal recognition
evidence. Switching or clearing selection must replace or clear all details;
missing bindings and empty datasets must not invent evidence. Details and QC
must use the same opening snapshot even if the live source changes, while
reopening must reflect the new source. Imported HTML-like strings remain
plain table text, and arrays and metadata are not mutated.

`tests/test_gis_reference_dialog.py` checks the read-only GIS inventory
opened from the existing single-sample reference dialog. RU/KK/EN must
display actual finite paired sample counts and MD bounds, the original
bottom-up descending axis, explicit QC for duplicate/nonmonotone MD
and stale curves, and no invented bounds on invalid axes. Opening the
inventory again must refresh source evidence without changing the
calibration form, sample result, project or source arrays. This is not
a petrophysical acceptance test or a claim of continuous coverage.
Run the complete three exact-HEAD Windows Release jobs before merge;
verify all three on new main after merge. Qt native #544 remains open.


## Bottom-up GIS LAS acquisition and descending target LAS

`tests/test_external_las_insert.py` checks all four source/receiver
direction combinations, preserving the original physical depth/value pairs;
a descending receiver keeps its row order even for EXACT matching and
LINEAR_OVERLAP. The 4-case NULL/gap/coverage test prevents interpolation
across missing values or outside GIS measurements. Repeated/non-finite/
mixed depth indexes reject cleanly, and a changed receiver direction
requires re-analysis. `tests/test_external_las_insert_controller.py`
exports a generated combined bottom-up LAS and reimports it, verifying
both original GTI and GIS channels at their corresponding depths.
`tests/test_external_las_insert_dialog.py` confirms explicit descending
receiver guidance in RU/KK/EN. The four-way matrix also checks that
`target_original_direction` and boolean `target_descending` agree in the
manifest. Additional regressions cover a large unsampled gap in a descending
receiver and rejection of corrupted receiver depth axes after analysis.
No original LAS is rewritten, and
the derived LAS retains the receiver depth direction.

The user-supplied diagnostic ZIP alone cannot prove the values in their
specific output LAS. Full field data acceptance still requires original
GIS LAS, receiver LAS, and output LAS with sample-depth comparisons.
Do not merge until all three Windows exact-head gates pass and the
post-merge main release gate is green.

## GIS-to-LAS created-copy tablet state and curve picker scrolling

User diagnostic bundle for build 0.7.96+fc51016d5b8b shows repeated
`MainWindow._show_visible_depth` RuntimeError when a new derived LAS
has no saved tablet layout. GUI regression in
`tests/test_main_window_visible_depth_refresh.py` exercises notifications
without a layout; the handler should still update status but neither
crash nor change session dirtiness/title. The same test module opens
the track-curve modal with 40/120 additional GIS curves and checks
always-visible vertical scrolling, horizontal long-caption scrolling,
and editable scrollbar ranges without changing selected curves.

`tests/test_external_las_insert_controller.py` verifies a GIS LAS copy
inherits an **independent**, deep-copied tablet layout from its receiver,
leaving the receiver layout untouched. Exported values are not proved
against the user's sample in the supplied diagnostic archive; a future
data-specific reproduction requires original/produced LAS and exact
export error. Windows Release Quality, GUI/HiDPI/PDF, Security exact-head
checks and post-merge main are required. Native Qt issue #544 remains open.

## Archived revision proposal baseline/candidate column labels

Regression coverage in `tests/test_lithology_mapping_dialog.py` asserts that
both read-only tables (diff and full provenance) label columns by explicit
operator roles, **baseline** and **candidate**, in RU/KK/EN. The diff order
must match the chosen baseline both for forward and reversed archival record
order, independent of UTC. Editing the baseline invalidates the detached
preview; preparing and clearing it must leave project/LAS unchanged and must
not imply geological approval. Merge only after the three exact-head Windows
Release checks pass and recheck the new main gate. Native Qt issue #544 is
not considered resolved by this UI change.

## Archival proposal source recheck fail-closed boundary — INTERP-FUSION-01

The operator's RU/KK/EN source recheck must never display a partial
matching result if the second live lookup raises an unexpected exception
or returns a malformed status. The UI clears the entire status, shows the
localized unknown-state warning, and logs a diagnostic traceback; the
proposal, read-only comparison, archived provenance, project and LAS remain
unchanged. A later successful recheck restores the live status without
repreparing the proposal. Regression:
`tests/test_lithology_mapping_dialog.py::test_proposal_recheck_fails_closed_on_partial_or_malformed_source_results`.
The result is not author authentication or geological approval; Qt #544
remains unresolved.

## Manual archival proposal source recheck — INTERP-FUSION-01

The read-only archival revision-proposal UI lets an operator recheck
both saved source identities against the current project session without
recreating a non-authoritative proposal. RU/KK/EN GUI regressions in
`tests/test_lithology_mapping_dialog.py` cover disabled recheck before
preparation, matching identities, altered source fingerprint after project
data changes, unavailable source after removal, restored source, and
strict reset on editing proposal inputs or changing the baseline.
A controlled lookup failure must clear any previously matching status and
display a localized unknown-status warning. The archived proposal,
provenance and diff remain unchanged during a successful recheck or failed
source lookup. This does not approve a geological revision, authenticate
the author, or modify project/LAS. Require exact-head Windows quality,
GUI/HiDPI/PDF, security gates and post-merge main validation. Native Qt
#544 remains unresolved.

## Archival proposal provenance tab (INTERP-FUSION-01)

Run `.\\.venv\\Scripts\\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_mapping_dialog.py -q`.
The RU/KK/EN tests check a detached revision proposal from two strict-reader
records, both hash values even if unchanged, all project/well/dataset/axis/
interval/lithotype/depth identities, reverse baseline ordering, literal
untrusted markup in table cells, and invalidation of both tabs on any input
change. The original difference table and source-status warning are retained,
and no project/LAS write, automatic revision activation, author authentication,
or geological approval occurs. SHA-256 is an archival assertion, not proof
that an external source or geological interpretation is valid. Require all
three exact-head Windows quality, GUI/HiDPI/PDF and security gates plus
post-merge main green. Qt native lifecycle issue #544 remains unresolved.

## Non-authoritative archival source warning — INTERP-FUSION-01

Run `.\\.venv\\Scripts\\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_mapping_dialog.py -q`.
The RU/KK/EN GUI regressions exercise explicit baseline choice, matching
source identities (no warning), one fingerprint mismatch, both fingerprints
mismatched after a source edit, unavailable sources, records from another
project, and invalidation after field/baseline changes. The warning and status
are plain text, re-evaluated at each Prepare click, and do not authenticate
the operator, certify source validity, approve a revision, or write to project
or LAS. Proposals remain detached even with a source mismatch. Do not bypass
the exact-HEAD Windows quality, GUI/HiDPI/PDF, and security gates or post-merge
main gate; Qt native #544 is not resolved by test isolation.

## Windows native WITS0 capture-dialog isolation — PR #709

Quality run `39924194284` aborted on Windows with `0xC0000005` in
`pyqtgraph.graphicsItems.ViewBox.ViewBoxMenu.__init__` while constructing
the WITS0 live-view plot from `tests/test_wits0_capture_dialog.py` after
other Qt cases in a shared offscreen process. No pytest assertion failure
was reported. The crash site does not establish the underlying native cause,
and issue #544 remains open.

The existing mandatory Windows native-child mechanism now executes **each**
capture-dialog test function in its own subprocess, retaining all original
assertions and parameterizations. The runner still fails on any nonzero child
exit, including native access violations. Test contracts confirm complete
node coverage and exclusion from regular shared shards. No production WITS0
behavior, dependency versions, skipped tests, pass thresholds or benchmarks
were changed. Require three exact-head Windows PR gates and green post-merge
main; this isolation does not claim to resolve #544.

## Qt grid renderer isolation after PR #708 native abort

PR #708 quality run 39908137560 aborted with Windows exit `0xC0000005`
while creating `pyqtgraph.PlotWidget` in
`test_grid_renderer.py::test_depth_overlay_aligns_horizontal_lines_to_five_metre_values`.
The stack ended inside `PlotItem.__init__`, after the preceding Qt/graphics
tests in the same shared offscreen process had passed. Security and GUI/HiDPI/PDF
gates passed on that head. This trace establishes the crash site, **not** the
root cause of native Qt issue #544 or a link to the proposal-preview UI.

The complete `tests/test_grid_renderer.py` file now uses the existing mandatory
one-test-per-native-child batching in Windows full CI. No tests, assertions,
shard failure propagation, memory/benchmark limits, or gates were removed or
weakened. `tests/test_windows_qt_test_isolation.py` verifies coverage of every
grid renderer node and its exclusion from mixed-process shards. A native crash
in any child still fails quality. The exact-head PR and post-merge Windows
gates remain required; the native Qt #544 root cause is not considered fixed.

## Archival lithology revision proposal preview (GUI)

Run `.\\.venv\\Scripts\\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_mapping_dialog.py tests/test_lithology_revision_proposal.py -q`.
RU/KK/EN GUI tests cover exactly-two-row selection in the archival history
viewer, no default baseline, explicit reversed source/candidate assignment,
bounded operator fields, time-only equality, rejection of an oversized reason,
read-only plain-text diff cells, invalidation after edits, and no project or
LAS mutations. The data-only service maintains the fixed
`proposal_not_geological_approval` status. Manual: open history, select exactly
two records, choose Prepare revision proposal, choose baseline explicitly,
enter ID/operator/justification and preview the comparison. Nothing is saved,
activated, authenticated, source-verified or geologically approved; archived UTC
time is not a revision sequence. Exact-head Windows quality, GUI/PDF and
security gates and post-merge main are required.

## Archival lithology revision proposals (data-only)

Run `.\\.venv\\Scripts\\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_revision_proposal.py tests/test_lithology_review_comparison.py -q`.
The revision-proposal API requires two explicit validated archival review objects,
one project/well/dataset/axis/interval, a changed recorded assertion, a bounded
proposal ID, proposed-by text and justification. Tests reject timestamp-only
changes, missing identity, invalid types and mixed source scopes. Assertions
remain immutable; untrusted strings are retained as text. Source-fingerprint
differences may be proposed but do not prove current source validity. Reversing
selection is allowed and does not imply time-based lineage. The status is fixed
to `proposal_not_geological_approval`; no project, LAS, file or UI mutation
occurs. This API does not authenticate the proposer, establish a verified
revision chain or confer geological approval; there is no persisted workflow.
Windows exact-head quality, GUI/PDF and security gates remain mandatory.

## Сравнение архивных литологических записей

Run `.\\.venv\\Scripts\\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_review_comparison.py tests/test_lithology_mapping_dialog.py -q`.
Contract: explicitly selected two records, same source scope, immutable differences
for reviewer/evidence/rock family/quality/lithotype/MD bounds/source fingerprints;
recording timestamps are displayed separately and do not certify revision order.
RU/KK/EN GUI shows exact untrusted text as table items (no HTML interpretation),
enables comparison for exactly two rows, keeps single-record details for one row,
and selects no active/default record. Identical recorded assertions do not confer
approval. No project mutations or new LAS writes. Manual: in View record history
Ctrl-select two rows and choose Compare two records. Windows exact-head quality,
GUI/PDF and security gates are mandatory before merge.


## Archival history selection

Run `.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_review_history.py tests/test_lithology_mapping_dialog.py -q`.
Acceptance covers bounded selection, UTC ordering/ties, duplicate paths/content
including equivalent UTC forms, mixed scopes, changed snapshots, atomic rejection
of malformed/missing files, immutable output and no project mutations. UI tests
cover RU/KK/EN, no edit/default selection, error/cancel and fresh source status
when opening details. Real export fixtures require ordinary filesystem rights.
Manual: choose View record history, select files for one source, inspect the
chronological table, select a row and open details. This does not activate or
approve a record and does not create a signed revision history.


## Archival lithology JSON reader

Run `.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_review_reader.py tests/test_lithology_mapping_dialog.py -q`.
Acceptance covers export/read round trip, immutable archive, all source states,
strict root/mapping/source contracts, duplicate keys, NaN/Infinity, invalid UTF-8,
deep JSON and the 1 MiB bound. UI checks RU/KK/EN, plain-text untrusted content,
no activation/field changes, cancellation and localized read errors. Tests that
create real exports need ordinary filesystem permissions for atomic publication.
Manual: choose View JSON record in the mapping dialog; inspect recorded reviewer,
evidence and source status, then close. Active fields and project remain unchanged.


## Detached lithology review JSON

Run `.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_review_export.py tests/test_lithology_mapping_dialog.py -q`.
Coverage includes UTF-8/provenance/schema/status, explicit overwrite, concurrent
name creation, stale source before/during write, failed atomic publication,
stage cleanup, cancellation, source edits during file selection and localized
I/O errors. AppContainer may deny link/replace in its private temp directory;
use ordinary filesystem permissions to test publication, without changing assertions.
Manual: review a source, choose Save review as JSON, inspect the detached record;
no project dirty flag or persisted mapping is created. JSON records are not
geological approval and cannot be imported/reactivated by this increment.


## Qt isolation after lithology/localization shared-shard abort

Main run 39734481784 (e08c1f8d, after #701) aborted with 0xC0000005 at
pyqtgraph ViewBoxMenu.py:32 during
`test_localization.py::test_main_window_uses_selected_language_for_shell`.
The child shared 46 files, including lithology mapping and earlier Qt dialogs;
there was no assertion failure. The selector passed three fresh-process
diagnostics. An exact local shard replay timed out after 180 seconds in an
earlier XLSX export test, so it did not reproduce or disprove the CI crash.

Both `tests/test_lithology_mapping_dialog.py` and `tests/test_localization.py`
now use the existing mandatory single-function native batches. Every parametrized
case remains executed, and nonzero/native child exits still fail the gate.
Contract tests assert exclusion from regular shards and complete node coverage.
No skips, automatic retries, GC changes or production runtime changes were added.
This contains shared-process Qt state; it does not establish/fix the general
native root cause #544. Full exact-head PR and post-merge main gates are required.


## Operator lithology mapping dialog

Run `.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_mapping_dialog.py tests/test_lithology_source_mapping.py -q`.
Check RU/KK/EN, explicit enum choices, source snapshot freshness, reset/reload,
quality preservation, menu wiring, Close and no source/project mutations.
Manual check: select an in-range saved lithology interval on a verified metre
MD axis, explicitly choose family/quality, enter mapping ID/reviewer/evidence,
then review. The result is temporary and is not saved or a productivity claim.


## Explicit lithology source review

Run `.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_lithology_source_mapping.py tests/test_gis_gti_lithology_coverage.py -q`.
Synthetic acceptance covers explicit family selection independent of rock names,
source/catalog/axis freshness, ambiguous IDs, invalid bounds, suspect/rejected
quality, and no project mutation. It does not validate regional geology.

## INTERP-FUSION-01 lithology coverage

`tests/test_gis_gti_lithology_coverage.py` checks actual changing rock coverage,
missing versus recorded unknown, matching/competing overlaps, local suspect/
rejected QC, touching boundaries, source order, frozen output, off-window
validation and preserved independent formation-test authority. Existing single
and homogeneous-window suites cover the extracted shared sweep.

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_gis_gti_lithology_coverage.py tests/test_gis_gti_md_partitions.py tests/test_gis_gti_lithology_screening.py tests/test_documentation_sync_0762.py -q
```

## INTERP-FUSION-01 MD partitions

`tests/test_gis_gti_md_partitions.py` checks separated/shared evidence, touching
and overlapping formation tests, local suspect QC, unknown gaps, clipping,
source order, immutable output, all-input validation including off-window
records, representable positive widths, sparse coverage and length conservation.
This is geometric/software acceptance using existing screening rules, not field
validation or a new fluid/pay model.

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_gis_gti_md_partitions.py tests/test_gis_gti_lithology_screening.py tests/test_documentation_sync_0762.py -q
```

## INTERP-PETRO-01 operator dialog

`tests/test_gis_reference_dialog.py` exercises RU/KK/EN × IGR/density actual
controls, mandatory selections/evidence, NaN/scope/stale/unit/scalar-axis guards,
parameter/result invalidation, Close and the real MainWindow menu/language
action. Source arrays and clean project state are retained. Visual review uses
synthetic data; it is not field calibration acceptance.

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_gis_reference_dialog.py tests/test_gis_reference_calibration.py tests/test_gis_reference_input_review.py tests/test_gis_input_inventory.py tests/test_petrophysical_reference_models.py tests/test_documentation_sync_0762.py -q
```

## INTERP-PETRO-01 calibrated scalar sample

`tests/test_gis_reference_calibration.py` verifies explicit parameters/evidence,
actual row and immutable context, raw out-of-range quality, source revisions,
array replacement/reopen, in-place MD changes, NaN, strict indices, MD scope,
descending source order and unchanged source arrays. Evidence is a caller
attestation, not automatic tool applicability certification.

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_gis_reference_calibration.py tests/test_gis_reference_input_review.py tests/test_gis_input_inventory.py tests/test_petrophysical_reference_models.py tests/test_documentation_sync_0762.py -q
```

## INTERP-GIS-01 reference source review

`tests/test_gis_reference_input_review.py` checks explicit channel selection,
equivalent unit spellings versus incompatible scales, inherited MD/source/QC
blockers, revision snapshots, unsupported methods, and unchanged real LAS
1.2/2.0 bytes and arrays. A positive result only permits calibration review;
it does not authorize physical interpretation or a later calculation.

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_gis_reference_input_review.py tests/test_gis_input_inventory.py tests/test_petrophysical_reference_models.py -q
```

## PR #682 CI39321437752: tabular-language MainWindow isolation

The Windows gate aborted with `0xC0000005` in pyqtgraph
`ViewBoxMenu.__init__` while reopening MainWindow in
`test_all_six_outputs_share_language_without_relocalizing_operator_ui[en-ru]`.
The preceding RU/KK case passed in a shared 58-file tablet/dialog shard.
No assertion failure preceded the native abort. The whole tabular-language
module passed all eight cases when run in a fresh process. The exact 58-file
CI shard was replayed locally and reproduced `0xC0000005` at the same EN/RU
selector. Six fresh-process runs of the end-to-end function then passed all
18 language cases with native statuses checked.

The runner now schedules `test_tabular_export_output_language.py` through the
existing single-function native batches. The end-to-end function still tests
all three UI/output-language pairs and both initial open and reopen; all six
real output checks and persistence assertions remain unchanged. The runner
contract verifies complete scheduling and exclusion from regular shards.
Native nonzero statuses remain failures; no retries, skips, GC disabling or
production lifecycle changes are introduced. This bounds shared test context,
but does not establish or close the general production-native root cause #544.

Reproduce the original selector with UTF-8 and the project runner:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_tabular_export_output_language.py -q
.\.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_test_runner_contract_0790.py -q
```

## Main CI39180284242: Qt root ownership during pytest final GC

At main `64c8fcbd` the Word stale-input selector completed all four cases,
then its process exited `0xC0000005`. A bounded local stress reproduced
`0xC0000374` on attempt 5; faulthandler located it in
`pytest_unconfigure -> unraisableexception.gc_collect_harder`. Replacing
geology signal closures with weak references did not fix it; that experiment
was discarded.

The session fixture retained QApplication but only hid top-level windows,
without retaining their Python wrappers. The unchanged fixture demonstrably
lost a hidden root on `del window; gc.collect()`. The session-finish hook now retains valid remaining root wrappers only after
the last test, until the existing isolated-process exit. Per-test cleanup remains
hide-only: no root is retained across tests by this change.
This keeps Python cyclic GC from dismantling a still-live Qt root graph during
pytest unconfigure. No production lifecycle change, GC disabling, skipped tests,
weakened assertions or native exit-code suppression is introduced. Memory
retention is bounded by the existing subprocess shards.

The new regression checks that per-test cleanup does not retain roots, then
that session-finish retention keeps a hidden QWidget valid after dropping
the caller reference and explicit GC. The originally failing selector passed
12 fresh stress processes (48 cases) with session-finish-only retention. The local generic-report UTF-8 read checks require the same `PYTHONUTF8=1`
that the Windows workflow sets; all 22 passed after matching that environment.
Full Windows gates on the
new HEAD remain required; these results do not close every native Qt issue #544.

PR #620 CI38570984430: native 0xC0000005 at pyqtgraph PlotItem QWidgetAction creation during dataset-merge Undo. This selector already uses a fresh subprocess; production disposal calls PlotWidget.close before parent deletion. Standalone selector passed in 12.52s, then three faulthandler-enabled fresh-process diagnostics passed with exits [0,0,0], 27.31s total. Native cause remains unproven. The prior dialog work-area assertion is fixed and its nine related tests pass. A single new exact-head gate run follows these diagnostics; recurrence requires investigation rather than repeated retries. No assertions/skips/thresholds changed.

PR #619 CI38529184973: native 0xC0000005 in pyqtgraph PlotItem QWidgetAction construction during LAS3 entrypoint language refresh. The failing function already runs in a fresh process. PlotWidget.close precedes parent deletion; no proven production defect yet. Standalone acceptance passed (15.72s), then three fresh faulthandler-enabled diagnostic processes passed with exit codes [0,0,0] (31.39s total). One controlled failed-job rerun follows this diagnostic; recurrence requires further lifecycle investigation. No skips, weakened assertions or speculative runtime changes.

## Repeated-MD time flag save/open and print capture

`test_value_flag_time_anchor.py` exercises RU/KK/EN × JSON/package production
save/open, retained sample TIME/TG, actual TabletView, and selected annotation
capture. Both samples share MD; print selection must not collapse their anchors.
After capture, both screen flags, source MD/TIME/TG and project records are intact.
This is not physical printer or click-anywhere acceptance.

## Windows geodata tablet native construction isolation

Run 38433521074 on 1fd9aac7 aborted with 0xC0000005 inside pyqtgraph
ViewBoxMenu.__init__ before the geodata tablet assertions. The runner retains
all geodata workspace tests in separate processes, using its existing native
batch mechanism. No tests or assertions are skipped; nonzero child status
still fails the gate. The underlying native heap cause is not established.
A fresh Windows run on the new head is required; Linux results cannot prove it.

## Masterlog repair: authored header typography contract

The old source assertions requiring 1.60 font enlargement are replaced by
behavior checks: header font/cell geometry is preserved, nested print-copy
properties cannot modify the source, and the page painter receives that copy.
Use `scripts/run_tests.py` for native Qt batches; keep all assertions enabled.

## Field masterlog 100% regression

`test_real_tablet_pdf_regressions.py` checks RU/KK/EN and both A4 orientations
at ACTUAL_SIZE with a dense legend and short screen viewport. Inspect every
PDF page's embedded raster height and graph density, not only its last legend
page. `test_hydrocarbon_interpretation_pdf_text.py` checks the complete table
frame lies inside the printable width, including its border and spacing.
Repeat M-1 export from its original project; an already clipped 8-pixel PDF
cannot prove source curves. Physical printer acceptance is separate.

# Проверка качества и release gate

Main CI38508677789 and exact local 314-case replay reproduced 0xC0000374 in
close_qt_windows_after_test/topLevelWidgets after VALUE cases. Native-sensitive
test_value_flag_print_selection is mandatory in four fresh function processes.
Runner contract checks every selector exactly once, absence from shared shards,
and native failure propagation. All six cases passed in real isolated children;
standalone selection/preferences/persistence24 also passed. The remaining original shared shard passed all 309 cases in 197.55 seconds. Root cause remains
uncertain; production lifecycle is unchanged, no CI blind rerun or skips.

PR #615 CI38504859984: sparse MD VALUE acceptance incorrectly expected null
axis_id from an optional layout setting. It now requires the actual Dataset
active primary index ID (or explicit TIME) and independently verifies the view
axis. Missing-channel/source-exact assertions remain enabled; no runtime patch.

Report author batch print selection: `python scripts/run_tests.py -p no:cacheprovider tests/test_report_author_batch_print.py tests/test_report_annotations.py tests/test_report_annotation_apply.py -q`.
Checks real RU/KK/EN buttons, one-step CompoundCommand Undo/Redo, Apply/Cancel,
text/SYMBOL JSON/package reopen, strict all-ID validation, no-op dirty behavior,
preserved visible/source arrays. Physical output acceptance remains separate.

PR #613 CI38493460486: masterlog footer tests still required the removed control
metadata row. The renderer no longer draws/measures an empty metadata string;
tests require exactly brand/page text and retain RU/KK/EN Unicode font selection,
72/96/144/300/600 DPI bounds, painter restoration and package source integrity.
Run test_masterlog_control_unicode and test_masterlog_footer_typography before
new exact-head Windows gates. Metadata remains in the document passport/header.

Time VALUE anchors at repeated MD: `python scripts/run_tests.py -p no:cacheprovider tests/test_value_flag_time_anchor.py tests/test_value_flag_sample_anchor.py -q`.
The real Dataset/TabletView/controller path checks the saved time sample and
distinct TG marker X, screen/print modes, legacy depth-only fallback and source
array integrity. This does not establish XY/WITS or physical printer acceptance.

CI38429624093 reached the later native tablet_view batch and exposed one final
legacy 30 px runtime expectation. It now requires exactly 34 px in print,
retaining the 28 px screen restoration, hidden action-strip and scrollbar
assertions. Targeted ruler/header batch: 10 passed; no blind rerun or skips.

PR #606 CI38426057865: two exact source contracts retained the old 30 px print
ruler height. The caption-clearance change uses 34 px in print and preserves
28 px on screen; both assertions now require that exact contract, without skips
or weakened bounds. Run compact_parameter_rulers, curve_header_readability and
real_tablet_pdf_regressions before new exact-head Windows gates.

CI38427000217 also exposed two old header-font x1.60 assertions in a later shard.
The replacement runtime regression requires exact authored font size and cell
geometry plus independent print-copy properties; the page-painter regression
checks the actual prepared header. Uniform density and print_header_layout: 25 passed.

Confirmed VALUE selection: `python scripts/run_tests.py -p no:cacheprovider tests/test_value_flag_persist_selection.py tests/test_value_flag_print_selection.py tests/test_depth_annotations.py -q`.
Проверяются atomic validation, one-step Undo/Redo, unchanged screen visibility,
JSON/package reopen, RU/KK/EN individual selection under temporary global switch,
preview reselection without model mutation. Global-switch persistence and physical
printer acceptance remain separate.

Ограниченный read-only LAS3 Log_Data pilot: `python -m pytest -q tests/test_las3_scalar_log_preview.py`.
На сохранённом LAS 3.0 проверяются DEPT/DT/YME, явные исключения CDES/NMR,
оригинальные SHA-256 и bytes, NULL, несовместимые версии и диалекты,
ошибочные строки/ширина/WRAP/DLM, лимиты size/rows. Это не означает
production dataset, WITS, source writer или подтверждённый LAS3 export.

Сверка legacy LAS3 Dataset bridge c production adapter:
`python -m pytest -q tests/test_las3_dataset_adapter.py`.
На pinned исходном LAS3 проверяется DatasetSourceRevision с точными
SHA-256/размером/MD, исходное происхождение восьми кривых без отдельного
DEPT, тип GIS и JSON/package reopen. Дополнительно проверяются запрет
FT вместо M и отказ от index-only LAS3 без выдуманных кривых.
Реальный Qt-планшет LAS 3.0 после JSON/package reopen:
`python -m pytest -q tests/test_las3_tablet_render_acceptance.py`.
Шесть RU/KK/EN × JSON/package кейсов проверяют реальные PlotDataItem
DT/ILD, MD, UOM, экранный/print-mode geometry contract и неизменность
оригинального LAS source. Здесь не заявлена приёмка PDF/принтера,
прочих секций LAS3 и write-back.

PLOT-FLAG-01 выбор для конкретной печати:
`python -m pytest -q tests/test_value_flag_print_selection.py`.
Qt tests RU/KK/EN проверяют реальные элементы Print Center, all/none
и флажки по одному; QGraphicsItem/sprite проверяются в print-mode
без изменения свойств VALUE, COMМENT и без скрытия иных аннотаций.
Общий PrintJobSettings/page-renderer контракт применяется к
preview/PDF/print; physical printer и persistent selection отдельно.

Metadata-only инвентаризация LAS 3.0: `python -m pytest -q tests/test_las3_section_inventory.py`.
Проверяются исходные секции, версии, ссылки Data/Definition, ограничение
размера и побайтовая неизменность всех трёх LAS 3.x fixtures. Эти проверки
**не** являются приёмкой sample read, канальных значений или экспорта LAS3.

Приёмка производственного LAS-импортёра на реально сохранённых LAS 1.2/2.0:
`python -m pytest -q tests/test_real_external_las_import.py`. Тесты не используют
mock `lasio.read`: проверяются глубины, DT, обёрнутые строки, TAB, исходные
байты, provenance и отсутствие ложного импорта DLIS/LIS79/SEG-Y/SU.
LAS 3.x проходит пока только структурную проверку без обещания полной загрузки.

Корпус DATA-PETRO внешних форматов: `python tools/fetch_external_format_fixtures.py --check`
проверяет оригинальный blob SHA-1 каждого файла без сети. Также запустите
`python -m pytest -q tests/test_external_format_fixture_corpus.py`.
Клиентские LAS 3.0/DLIS/LIS79/SEG-Y импортеры ещё не утверждены этим тестом;
он проверяет только точность и происхождение 16 fixture artifacts.




DATA-PETRO-01 stage-0 capability audit: `python -m pytest -q tests/test_format_capabilities.py tests/test_las_adapter.py`.
Матрица проверяет supported/limited/unverified LAS versions, отказ от записи raw,
CSV/Excel import/export границы и предупреждение для неопробованных LAS headers.
Полный Windows Release gate обязателен до интеграции; LAS 3.x fixtures/UI и
полевой round-trip отдельно.


`tests/test_print_center_output_language.py` covers 18 real tablet/curve export scenarios after project and preference reopen: all UI/output language pairs, PDF, QPrinter preview/print, PNG, SVG and Passport. Actual page counts and localized footers, UI/source invariants and six detached-copy scenarios are checked. `tests/test_print_output_language_preferences.py` covers 26 cases: engineer/form persistence, legacy and malformed language fallback, typed job/preferences validation and strict Unicode checks for selected printed columns with print-mode restoration. QPrinter uses PDF output; physical printer acceptance remains separate.


`tests/test_interpretation_workspace_output_language.py` covers 18 production workspace cases after project save/reopen: standard/OPUS and all UI/output-language pairs. Actual PDF plus Passport, DOCX, XLSX, prepared system-print PDF and printer PDF exercise selected language, saved header/narrative fields and profile guards. All three language headers, source arrays/metadata and immutable reports are checked. Existing 18 ramp workspace cases use the same selector; dialogs retain UI language.

`tests/test_gas_mixture_output_language.py` covers 144 actual PDF/QPrinter cases: RU/KK/EN, 72/300/600 DPI, chart/text and numeric/datetime/missing/vendor time axes, plus three known/unknown message cases. `tests/test_gas_mixture_workspace_language.py` covers 18 production workspace cases after project save/reopen: all UI/output language pairs and both ramp modes, real preview/PDF/system-print outputs, UI-language changes and mode switches. Complete translated warnings/headers, numeric values, footer, bounds and immutable source/audit are checked.

`tests/test_gas_mixture_document_control.py` covers 108 actual multi-page PDF/QPrinter cases: RU/KK/EN, 72/300/600 DPI, chart/text and default/full/long identity. Full document-control values, escaped text, complete numeric rows, repeated localized footer, physical typography/bounds and source immutability are checked. Six raster cases retain component paths/keys while verifying shared frame/grid rules. Existing palette/typography and atomic failure checks remain.

`tests/test_masterlog_rule_profile.py` covers 495 actual RU/KK/EN PDFs across five DPI, three palette/rule profiles and eleven painter paths; 27 A4/A3/roll exports after project reopen; and nine saved-swatch override cases. Thin/strong physical widths, critical/page/text callout roles and alpha, geometry, semantic geology fills/lines, complete text and immutable source data are checked. Fixtures establish the same physical heading font that production columns inherit.

`tests/test_office_shared_visual_profile.py` covers 54 production exports after project save/reopen: RU/KK/EN, default/custom/large typography, colour/grayscale palettes and generic DOCX/geological DOCX/XLSX. OOXML table sizes, caption style and border hierarchy, Excel summary/footer sizes and round-tripped colours are checked. Baseline comparison retains complete cell text, values/types, column widths, print scale, repeat rows and source arrays.

`tests/test_masterlog_shared_typography.py` covers 360 real RU/KK/EN PDFs across five DPI, default/custom/large profiles and eight Masterlog paths, plus 18 A4/A3/roll production exports after project reopen. Exact table/caption/body role requests, complete searchable text, physical bounds and the 72-DPI baseline are checked. Existing Unicode and explicit-size tests retain source, orientation and saved-style contracts. Curve-legend recording fixtures wrap a real QPainter so bounded fitting receives actual Qt measurements; all key geometry, styles and missing-curve assertions are retained.

`tests/test_interpretation_pdf_fitted_typography.py` covers 216 cases: 180 actual
RU/KK/EN PDFs at 72/96/144/300/600 DPI with default/custom/large title/subtitle/body/code
roles, 18 production standard/OPUS PDFs after project reopen, and 18 empty-panel/code
adapter cases. Full searchable text, bounds, 72-DPI size/bounds baseline, painter state,
exact requested profile roles and immutable source values are checked. Existing
physical-DPI tests now assert the intentional profile mapping instead of fixed legacy sizes.

The unified preview profile package is covered by
`tests/test_interpretation_preview_ratio_typography.py` (27 RU/KK/EN Haworth/Pixler
and production-reopen cases) and `tests/test_interpretation_preview_visual_profile.py`
(36 panel, empty-geology, badge and whole-preview cases). Default/custom/large profiles
check full fitted text, actual font roles, neutral palette, tick/frame geometry,
unchanged scale values and source arrays. Existing chrome tests retain exact title,
footer, depth and fluid-legend assertions and also check the additional profile roles.

`tests/test_interpretation_preview_fluid_legend_profile.py` checks 18 actual
RU/KK/EN raster cases with two widths and default/custom/large typography. All five
phase keys, full localized labels, measured bounds, actual-text font requests,
caption role, palette and marker positions/sizes remain checked. Three empty cases
draw nothing; nine production previews after reopen preserve candidates/source arrays.

`tests/test_interpretation_preview_depth_profile.py` checks 54 real raster axis
cases: RU/KK/EN, left/right, default/custom/large profiles and negative/ordinary/long
depth values. Complete fitted text, font roles, palette, eleven major and forty
minor tick coordinates and frame/fill geometry are checked. Nine production
previews after save/reopen preserve signed labels, source arrays and candidates.

`tests/test_interpretation_preview_chrome_profile.py` checks 18 RU/KK/EN
title/footer raster cases with default/custom/large profiles and nine production
previews after project save/reopen. Complete text, measured bounds, requested font
roles, palette colours, bold title and restored painter state are checked; source
arrays, candidates and gas-context events remain unchanged.

`tests/test_gas_context_track_typography.py` checks 30 real RU/KK/EN PDFs
at 72/96/144/300/600 DPI and 12 raster DPI/profile cases. Default/custom table
typography, complete wrapped headings, reserved bounds, physical size baselines,
painter state and immutable events are checked. Existing production standard/OPUS
export after reopen and preview tests cover the shared heading-height integration.

`tests/test_gas_context_legend_typography.py` checks 45 actual RU/KK/EN PDFs
at 72/96/144/300/600 DPI with default/custom/large typography, nine PNG legends
and nine dense multi-page PDFs. Section/caption role requests, measured header
reservation, full localized event rows/IDs/depths, painter state and 72-DPI
size/bounds baselines are checked. Existing registry priority, grayscale styles,
source arrays and production export after reopen remain covered separately.

`tests/test_masterlog_footer_typography.py` checks 60 actual RU/KK/EN PDFs:
simple/controlled footer paths at 72/96/144/300/600 DPI with default/custom typography.
Exact footer/table role requests, searchable text, reserved bounds and painter state
are checked independently of existing Qt pre-transform font quantization. Extracted
sizes/bounds match the 72-DPI baseline. Eighteen controlled/legacy A4/A3/roll exports
after package reopen preserve form metadata, source arrays and footer font size.

`tests/test_masterlog_control_unicode.py` checks 30 actual RU/KK/EN PDF cases:
document-control header/footer at 72/96/144/300/600 DPI. Font resolution receives
full text before measurement/elision, including bounded compact footer metadata.
Bold hierarchy, searchable text, painter state and the 72-DPI size/bounds baseline
are checked. Nine A4/A3/roll exports after package reopen preserve form metadata,
the selected output interval and source arrays. Existing control/default-font tests remain.

`tests/test_ratio_reference_depth_keys.py` checks six actual RU/KK/EN monochrome
PNG charts with colour/grayscale neutral profiles and nine vector PDFs at
72/300/600 DPI. All six depth keys remain distinct; scatter and profile coordinates
match source measurements. Filled glyphs, six vector dash patterns and unfilled
plot areas are checked. Existing palette, typography and DPI matrices remain.

`tests/test_ratio_reference_typography.py` checks 18 RU/KK/EN PNG charts with
default/custom/maximum-size profiles and complete/partial data. Shared typography
roles, full labels, measured bounds and empty states are checked. Another 27 actual
PDF cases at 72/300/600 DPI preserve full text and physical sizes/bounds against the
72-DPI baseline. Existing neutral-palette, QPrinter and source regressions remain.

`tests/test_ratio_reference_visual_profile.py` checks nine actual RU/KK/EN PNG
charts with default/grayscale/custom palettes and 18 vector PDFs at 72/300/600 DPI.
Pixel colours, extracted text colours and vector fills/strokes use the shared neutral
palette while depth colours remain intact. Existing physical-DPI and source tests remain.

`tests/test_ratio_reference_physical_dpi.py` checks 30 actual QPdfWriter/QPrinter
Haworth/Pixler summary PDFs: RU/KK/EN at 72/96/144/300/600 DPI. Complete extracted
text, font sizes and bounds match the 72-DPI baseline; painter state and source
arrays remain unchanged. Existing ratio-reference PNG and paired-row tests remain.

`tests/test_gas_mixture_raster_typography.py` checks nine actual RU/KK/EN PNG charts
with default, custom and maximum-size typography. Captured text uses shared roles
and actual-label Unicode fonts, remains complete and fits measured device bounds.
Changing the UI font does not change the resolved print families; oversized profile
sizes shrink within the fixed geometry. Existing PDF and monochrome-line tests remain.

`tests/test_gas_mixture_line_patterns.py` checks six RU/KK/EN raster charts with
colour/grayscale profiles. Actual grayscale PNG legend signatures distinguish all
five component line patterns; captured paths retain every time/log-response coordinate.
Curve and legend pens match exactly, and the immutable report remains unchanged.
Run alongside `test_gas_mixture_report_visual_profile.py` and `test_gas_mixture_ramp_report.py`.

`tests/test_geology_pdf_typography.py` checks six actual geology PDF exports:
RU/KK/EN with default/custom profiles. Extracted spans verify physical title,
section, body and table sizes, full wrapped titles and manual conclusions;
source arrays remain unchanged. Disabling the shared rich-text adapter makes
all six regressions fail on Qt heading-relative font enlargement.

`tests/test_tablet_header_footer_spacing.py` adds 180 real QPdfWriter/QPrinter PDF
cases across RU/KK/EN, five DPI, three widths and two padding profiles. Extracted
text/bounds verify non-overlap, physical gaps, Unicode page labels, bounded title/brand
ellipsis and the 72-DPI baseline. Three empty-range/hidden-number cases plus existing
pixel-preview/layout/executor tests check compatibility and restored painter state.

`tests/test_masterlog_default_typography.py` adds 129 cases: 90 header text/placeholder/
swatch PDF cases (RU/KK/EN, five DPI, default/explicit sizes), ten signed/large depth
cases, 15 searchable simple-footer cases, five explicit annotation-font cases and nine
A4/A3/roll package reopen exports. Saved mm requests are checked exactly; actual PDF
font/bounds are compared with the 72-DPI baseline, preserving native Qt quantization.

`tests/test_masterlog_callout_unicode.py` covers 60 real PDF cases for inspection
callouts and SVG symbol labels: RU/KK/EN × five DPI × depth/interval × two paths.
It checks actual-text font resolution, 5.5/6.0 pt requests, extracted PDF text/font/bounds
and vector geometry against the 72-DPI baseline after changing the UI font. Six cases
keep template/column/depth filtering; nine A4/A3/roll exports after package reopen
preserve canvas objects, SVG assets and source values. Stored callout language remains unchanged.

`tests/test_masterlog_geology_label_unicode.py` covers 90 real PDF cases for
stratigraphy and LBA labels: RU/KK/EN × five DPI × three orientations × two paths.
It checks actual-text font resolution, 5.5/5.0 pt requests, extracted text/font/bounds
and LBA glyph geometry against the 72-DPI baseline after changing the UI font.
Nine A4/A3/roll exports after package reopen preserve forms, geology and source values.

`tests/test_masterlog_heading_unicode.py` adds 90 actual PDF cases for column titles
and bound curve labels: RU/KK/EN × 72/96/144/300/600 DPI × horizontal/two vertical
orientations × legend on/off. Font stack, 6.5/4.6 pt requests and extracted 72-DPI
font/geometry baseline remain checked after a UI font change. Nine package reopen
exports cover A4/A3/roll, unchanged forms/metadata/values and literal Unicode UOM.
Existing `tests/test_masterlog_curve_legend.py` verifies line/point keys, dash/width,
source identifiers, missing channels and narrow cells without invented units.

`tests/test_masterlog_description_unicode.py` covers 45 actual-text font/PDF regressions
(three geology text paths × RU/KK/EN × 72/96/144/300/600 DPI) and three production
exports after package reopen. It verifies localized text without legacy/HTML leakage,
resolved font families after UI font changes, unchanged requested 6.5/6.0 pt sizes,
72-DPI extracted font/geometry baseline and preserved geology/source arrays. Existing
`tests/test_masterlog_renderer.py` guards rich-text alignment and bounded interval clipping.

Masterlog Unicode legends: `tests/test_masterlog_legend_unicode.py` checks 45 real
PDF cases (RU/KK/EN × 72/96/144/300/600 DPI × populated/empty lithology/LBA).
It changes the UI font, verifies actual text/font stack, a 3 mm body size and painter
restoration. Three production exports after package save/reopen verify localized legends
and unchanged forms/source arrays. Fractional pre-transform sizes retain existing Qt
rounding; these tests do not assert that native font quantization has been eliminated.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_masterlog_legend_unicode.py tests/test_masterlog_header_visual_profile.py tests/test_masterlog_control_layout.py tests/test_masterlog_renderer.py
```

Документ актуален для **DIGITAL GEOLOG GASRATIO&PIXLER 0.7.93** на 9 сентября 2026 года. Краткая история
находится только в `CHANGELOG.md`; результаты конкретных CI/сборок хранятся как artifacts и не
заменяют текущие команды проверки.

Тест является контрактом продукта. Его нельзя ослаблять или пропускать только ради зелёного CI.
При осознанном изменении поведения одновременно обновляются production code, regression test,
единый план, архитектура, документация и changelog.

## 1. Подготовка окружения

Для повседневной разработки из корня проекта в Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Для release gate используется хешированный `requirements/release.lock`. Он содержит полный
runtime-граф распространяемого приложения для CPython 3.11 на Windows x86-64. Quality- и
security-инструменты не входят в состав приложения: workflow устанавливает их отдельно и только
в точно закреплённых версиях. Воспроизводимая установка runtime:

```powershell
uv venv .venv --python 3.11
uv pip sync requirements/release.lock --python .venv --require-hashes
uv pip install --python .venv --no-deps --no-build-isolation --editable .
```

Lock обновляется осознанным отдельным изменением после проверки diff:

```powershell
uv pip compile pyproject.toml `
  --python-version 3.11 `
  --python-platform windows `
  --generate-hashes `
  --output-file requirements/release.lock
```

Нельзя вручную удалять transitive requirements или hashes из готового lock-файла. После
обновления проверяются целевая платформа в заголовке, полный runtime-граф и diff каждого hash.
Локальное виртуальное окружение и кэш `uv` не входят в архив проекта.

Канонический запуск приложения:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m geoworkbench.app.main
```

Запуск через модуль является основным документированным сценарием. Консольные entry points из
`pyproject.toml` сохраняются для совместимости, но не заменяют эту команду в README и проверках.

## 2. Быстрый обязательный gate

### Диагностика завершения GUI-процесса

Ненулевой код запуска сам по себе не устанавливает причину. Штатный runner при сбое
дочернего процесса выводит `Test subprocess failed`, точные pytest selectors и код
завершения в десятичном/шестнадцатеричном виде. Исходный код возврата сохраняется;
проверки не пропускаются и автоматического повтора, скрывающего падение, нет.
Для диагностики сохраняйте весь журнал, а не только строки с `FAILED`:

```powershell
python scripts/run_tests.py -p no:cacheprovider *> pytest-diagnostic.log
$testExit = $LASTEXITCODE
Get-Content pytest-diagnostic.log -Tail 60
Write-Host "Test exit code: $testExit"
```

Успешный отдельный повтор не доказывает устранение причины предыдущего сбоя:
нужно также проверить полный штатный прогон.

Перед передачей архива или публикацией hotfix выполняются:

```powershell
python tools/check_documentation.py
python -m compileall -q src tests tools scripts
python -m pytest -q `
  tests/test_module_entrypoint_contract_0790.py `
  tests/test_test_runner_contract_0790.py `
  tests/test_documentation_sync_0762.py `
  tests/test_root_readme_scope.py `
  tests/test_release_security_contract.py `
  tests/test_windows_release_matrix_contract.py `
  tests/test_gs2_form_axis_hotfix_0789.py `
  tests/test_index_detection.py `
  tests/test_compact_geology_columns.py `
  tests/test_form_engine_models.py `
  tests/test_masterlog_presets.py
```

Этот набор проверяет:

- единый способ запуска `python -m geoworkbench.app.main`;
- соответствие версии пакета runtime-контракту документации;
- синхронность RU/KK/EN-документации и корректность внутренних ссылок;
- безопасное согласование TIME/DEPTH после импорта GeoScape2/GS2;
- сохранение линейной шкалы по умолчанию в формах и Masterlog-пресетах;
- отсутствие синтаксических ошибок в Python-модулях;
- контракт Windows GUI/HiDPI/PDF acceptance matrix и невозможность автоматически объявить
физическую печать пройденной.

Сквозной сценарий переносимого многоязычного проекта и суточного LAS запускается отдельно:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_multilingual_geologpkg_workflow.py
```

Он использует `tests/fixtures/las_sync`: первый LAS, допустимый суточный append и конфликтующий
LAS. Проверяются RU/KK/EN, reopen, duplicate no-op, конфликт без мутации, три PDF и копирование
одного `.geologpkg` в каталог «другого компьютера».

### RPT-COMP-01: persisted report composition

Проверка project-format v37 и UI restore boundary:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_report_composition_persistence.py
```

Regression подтверждает JSON/`.geologpkg` round-trip, безопасную миграцию v36 с пустой
composition, отказ от ссылок на неизвестный dataset и восстановление orientation/order/
Auto-Show-Hide в report layout dialog. Composition является presentation state и не меняет
source LAS, расчётные series или geological records.

`tests/test_report_annotations.py` дополнительно проверяет отказ загрузки annotation schema
с JSON boolean, float, string, null и неподдерживаемыми целочисленными версиями. Валидная
целочисленная v1 сохраняется через существующие JSON/package round-trip regressions.

### RPT-COMP-01: saved chart columns

`tests/test_report_chart_panel_composition.py` проверяет JSON/package controller save/reopen,
legacy v37 defaults, bounded malformed settings, RU/KK/EN dialog restore/reorder/Cancel,
standard/OPUS default order, фактические preview/PDF painters и все скрытые колонки.
Проверяется неизменность source arrays/dataset fingerprint и отсутствие переноса аннотации
скрытой колонки к соседней. System print использует тот же подготовленный PDF и settings.

### Проверка состояния daily LAS preview (WELL-02)

Проверка привязки daily LAS preview к состоянию данных (первый инкремент WELL-02):

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_daily_las_growth.py tests/test_daily_las_growth_dialog.py tests/test_proj04_daily_append_rollback.py tests/test_daily_las_growth_autosave.py
python -m benchmarks.benchmark_daily_las_preview
```

Проверяются изменения вне перекрытия, единицы, локальные кривые, отказ без мутации, повторный
анализ, отмена/ошибка окна, autosave и совместимость исторического audit SHA-256.
Benchmark измеряет только fingerprint 100k/1M, с лимитом временных выделений 4 MiB.

## 3. Расширенная проверка в headless-контейнере

Когда в среде нет PySide6, pyqtgraph или lasio, используйте:

```powershell
python scripts/run_headless_tests.py
```

Скрипт сначала выполняет collection всего набора. Он исключает файл только тогда, когда collection
заблокирован реально отсутствующим модулем из закрытого списка `PySide6`, `pyqtgraph`, `lasio`.
Любая другая collection-ошибка остаётся фатальной. Это диагностический reduced-environment gate,
а не замена полному Windows-прогону. Async ETP-тесты при этом выполняются через явно загруженный
`pytest_asyncio.plugin`.

## 4. Полный автоматический gate

В установленном Windows-окружении:

```powershell
$env:PYTHONUTF8 = "1"
python tools/check_documentation.py
python -m ruff check src tests tools scripts
python -m mypy src
python scripts/run_tests.py -p no:cacheprovider
```

Каждая команда должна завершиться с кодом `0`. Успешный выборочный набор не заменяет полный
прогон. Пропуски обязательных сценариев, зависание процесса, native crash Qt или изменённые
тестами файлы проекта считаются блокирующими дефектами.

UTF-8 фиксируется явно: иначе Windows console с CP1251 может аварийно завершить `mypy` при выводе
диагностики, содержащей символы единиц измерения, и замаскировать обычный type-check debt под
внутреннюю ошибку инструмента.

`scripts/run_tests.py` является штатной оболочкой полного pytest-прогона. Она отключает случайные
глобальные плагины, но явно загружает проектный `pytest_asyncio.plugin`, поэтому async ETP-тесты
не пропускаются. Оболочка сохраняет код результата тестов и изолирует завершение процесса от
нестабильной выгрузки нативных Qt DLL.

## 5. Security gate и CI artifacts

После установки окружения из lock-файла выполняется:

```powershell
python tools/release_security_gate.py
```

Команда запускает `pip-audit` в строгом hash-режиме, создаёт CycloneDX JSON SBOM, проверяет
исходный код через `detect-secrets` и запускает Bandit для `src`, `tools` и `scripts`. Результаты
пишутся только в игнорируемый каталог `build/ci-artifacts/security`:

- `dependency-audit.json`;
- `sbom.cdx.json`;
- `secret-scan.json`;
- `bandit.json`;
- `security-manifest.json` с SHA-256 lock-файла, командами и статусами.

Workflow `.github/workflows/release-gate.yml` отдельно выполняет Windows quality gate,
Windows GUI/HiDPI/PDF acceptance и Windows security gate. Логи качества, acceptance evidence
и security reports загружаются как три CI artifact с retention 30 дней. Artifact не коммитится
и не считается успешным gate, если соответствующая команда завершилась ненулевым кодом.

## 6. SEC-03: bounded LAS/XML inputs

Регрессия `tests/test_bounded_input_limits.py` проверяет раннее прекращение binary read, chunk size,
XML namespace/text/tail, запрет DTD/entity/notation и отдельные лимиты bytes, depth, elements,
text, attributes и attribute bytes. Интеграционные случаи подтверждают те же ограничения в
WITSML inventory и ChannelSet data import. `tests/test_las_adapter.py` проверяет, что oversized LAS
отклоняется до вызова `lasio`, а семантический parser получает уже проверенную in-memory копию.

Минимальный локальный запуск:

```bash
python -m pytest -q tests/test_bounded_input_limits.py tests/test_witsml_inventory.py \
  tests/test_witsml_data_arrays.py tests/test_witsml1411_soap.py tests/test_lossless_las.py
```

## 7. SEC-04: WITS0 ownership marker и remote-bind policy

`tests/test_wits0_reliability.py` проверяет fail-closed retention без marker, явное принятие
непустого каталога, отказ при повреждённом marker и невозможность авторизовать другой путь
скопированным marker. `tests/test_wits0_capture.py` проверяет loopback default, обязательные
warning acknowledgement и CIDR allowlist для non-loopback server, отдельное разрешение wildcard
`0.0.0.0`, запрет global/unbounded networks и фильтрацию peers политикой. UI contract проверяет
поля allowlist, warning и adoption flow.

Минимальный локальный запуск:

```bash
python -m pytest -q tests/test_wits0_reliability.py tests/test_wits0_capture.py \
  tests/test_wits0_capture_dialog.py
```

## 8. Автоматическая Windows GUI/HiDPI/PDF matrix

`tools/windows_release_matrix.py` запускается отдельным процессом для каждого Qt scale factor
`1.0`, `1.25`, `1.5` и `2.0`. Матрица проверяет A4/A3/roll, portrait/landscape, Fit/100%,
continuation pages, Unicode RU/KK/EN, инженерные символы, создание и повторное чтение PDF. Для
каждого случая сохраняются PDF, снимок тестового QWidget и `windows-release-checklist.json`.
Результаты создаются только в игнорируемом `build/ci-artifacts/windows-acceptance`.

`a4-portrait-fit` дополнительно рендерит тот же REL-03/CUT-03 acceptance sheet, который используется
при физической печати: длинный rich-text, границы интервала, простой LBA, цвет и детерминированное
cuttings image через production `AnnotationRecord(kind=IMAGE)` / `TabletAnnotationItem` image
renderer. Это проверяет production image paint path в PDF, но не заменяет осмотр бумаги.

Локальный запуск одного масштаба в Windows:

```powershell
python tools/windows_release_matrix.py `
  --scale-factor 1.25 `
  --platform windows `
  --output-dir build/ci-artifacts/windows-acceptance/1_25
```

CI запускает все четыре масштаба. Успешная автоматическая матрица получает общий статус
`pending_physical_printer`: наличие PDF и screenshots не доказывает реальную подачу бумаги,
цвет, clipping, поля драйвера и читаемость физического отпечатка.

## 9. Ручная Windows-приёмка GUI и физической печати

Автоматические source-contract, headless и Windows matrix не заменяют проверку настоящего
интерфейса и принтера. Минимальный smoke-сценарий:

1. Запустить приложение командой `python -m geoworkbench.app.main`.
2. Импортировать временную и глубинную таблицы GeoScape2/GS2.
3. Переключить вертикальную ось TIME/DATETIME ↔ DEPTH и проверить подписи шкалы.
4. Применить несколько заводских и пользовательских форм подряд.
5. Убедиться, что формы используют линейную шкалу по умолчанию и нулевые LAS-значения не
   разрывают кривую.
6. Сохранить проект, закрыть приложение, повторно открыть проект и повторить переключение формы.
7. Проверить планшет, аннотации, PDF, печать, внешний монитор и DPI 100/125/150%.

При ошибке нужно создать diagnostics ZIP через меню «Справка» и приложить его вместе со
скриншотом, исходным файлом и точной последовательностью действий.

Физический acceptance checklist фиксируется той же командой. `passed` допустим только после
реальной отправки всех cases на принтер и отдельного подтверждения каждого визуального критерия
после осмотра бумаги. Полный операторский порядок: [PHYSICAL_PRINT_ACCEPTANCE.md](PHYSICAL_PRINT_ACCEPTANCE.md).

```powershell
python tools/windows_release_matrix.py `
  --scale-factor 1.0 `
  --platform windows `
  --output-dir build/ci-artifacts/windows-acceptance/physical `
  --printer "ТОЧНОЕ ИМЯ ПРИНТЕРА" `
  --operator "ФИО инженера" `
  --print-test `
  --confirm-rich-text `
  --confirm-cuttings-photo `
  --confirm-custom-heading `
  --confirm-interval-bounds `
  --confirm-color `
  --confirm-driver-margins `
  --confirm-no-driver-warning `
  --confirm-physical-output `
  --physical-notes "модель принтера, бумага/лоток, замечания" `
  --require-physical
```

Команда последовательно проверяет и печатает A4, A3, custom и roll cases, включая все страницы
продолжения. Без `--print-test`, `--operator`, всех семи `--confirm-*` evidence flags и финального
`--confirm-physical-output` инструмент не может записать physical-printer status `passed`.
Полученный checklist хранится как release artifact, а не в Git.

## 10. PERF-01…04: acquisition и tablet performance contracts

`tests/test_acquisition.py` проверяет default batch 64, отсутствие full projection digest во время
`append_many`, геометрический рост capacity, logical rollback mixed batch и детерминированное
восстановление incremental chain после replay. WITS0 и ETP runtime передают собственный
`drain_batch_size` в единый controller boundary.

`tests/test_acquisition_replay_memory.py` закрепляет PERF-02: fresh replay не выполняет
`deepcopy(Well)` и не копирует unrelated datasets; checkpoint resume staging копирует только один
изменяемый acquisition Dataset, а immutable journal/checkpoints/events переиспользуются через
новые контейнеры без ослабления transactional rollback.

`tests/test_acquisition_benchmark.py` проверяет логику PERF-03 guardrails: nearest-rank p95,
обязательный batch64, `T(2N)/T(N) <= 2.5`, p95 `<= 50 ms` и last/first `<= 2`. Сам wall-clock
performance не помещается в обычный unit suite: enforcing runner выполняется Windows quality gate
на `50k/100k/1M` и сохраняет JSON artifact.

`tests/test_geometry_cache_byte_budget.py` закрепляет PERF-04: точный `numpy.nbytes` accounting,
LRU eviction по byte budget и entry count, MRU promotion после hit, oversize geometry без
retention, освобождение bytes при clear/invalidate и независимые revision keys. Тест также
проверяет read-only sampled arrays. `tests/test_curve_sampling_benchmark.py` выполняет малый
production-seam cold→hit→zoom worker и проверяет structural benchmark contract.

Минимальный correctness-запуск:

```bash
python -m pytest -q tests/test_acquisition.py tests/test_acquisition_replay_memory.py \
  tests/test_acquisition_benchmark.py tests/test_geometry_cache_byte_budget.py \
  tests/test_curve_sampling_benchmark.py tests/test_wits0_acquisition.py \
  tests/test_etp12_acquisition.py tests/test_acquisition_codec.py
```

Воспроизводимые performance-runs:

```powershell
python benchmarks/benchmark_acquisition.py --json
python benchmarks/benchmark_curve_sampling.py --json
```

Quality gate сохраняет PERF-03 как
`build/ci-artifacts/quality/acquisition-benchmark.txt`. Каждый размер запускается в отдельном
worker-процессе; p95 и first/last сравниваются по полным batch64. Batch-aligned окно содержит
`157 × 64 = 10 048` строк, поэтому partial tail не искажает последнюю метрику. Peak RSS
фиксируется для наблюдения, но PERF-03 не задаёт отдельный RSS threshold.

Принятый Windows baseline PERF-03 release-gate #886: 50k/100k/1M —
`3.504 / 7.027 / 70.605 s`, p95 batch64 — `4.684 / 4.663 / 4.640 ms`, last/first —
`1.017 / 1.008 / 0.988`; `T(100k)/T(50k)=2.005`, violations отсутствуют.

PERF-04 сохраняется как `build/ci-artifacts/quality/curve-sampling-benchmark.txt`. Runner
изолирует 1M/5M/10M samples в отдельных процессах и для каждого выполняет cold miss, O(1) cache
hit и zoom miss при `max_points=4096`, одновременно проверяя `current_bytes <= max_bytes`.
Принятый Windows baseline release-gate #894: cold `43.049 / 161.581 / 289.547 ms`, hit
`0.0038 / 0.0036 / 0.0034 ms`, zoom `27.797 / 106.746 / 197.813 ms`, peak RSS
`84.5 / 302.1 / 574.2 MiB`. Во всех сценариях две cached geometry занимают `131 072 B` из
hard budget `67 108 864 B`.

### RPT-GAS-VIS-01: ratio scatter presentation

Газовые отношения и интерпретационные коэффициенты проверяются как дискретные point-series
без соединяющей линии, а обычные глубинные газовые кривые сохраняют line presentation:

```powershell
python -m pytest -q -p no:cacheprovider \
  tests/test_gas_curve_rendering_continuity.py \
  tests/test_tablet_gas_segment_mask.py \
  tests/test_tablet_view.py \
  tests/test_tablet_print_quality.py \
  tests/test_masterlog_renderer.py \
  tests/test_interpretation_report_charts.py \
  tests/test_gas_07_golden_acceptance.py
```

Shared predicate покрывает Haworth/WH-BH-CH, C1/C2…C1/C5, isomer ratios, Pixler и OPUS
ratio-series. Он намеренно исключает C1–C5/iso-normal components, TG/normalized gas,
`OPUS_TG_PCT` и `*_REL`. Tablet regression требует `symbol="o"` и отсутствие polyline
для ratio даже после STYLE-refresh; обычный C1/TG и ROP/DEXP сохраняют линии. Tablet print
может увеличить размер ratio marker, но не создаёт линию. Masterlog и hydrocarbon PDF/PNG
проверяют тот же glyph contract. C1–C5 ramp-report остаётся линейным временным профилем,
а relative-gas `*_REL` сохраняет cumulative 0–100% stacked fill. Расчётные массивы,
sampling/range и source LAS этим контрактом не меняются.


Windows quality gate дополнительно изолирует `tests/test_session_safety.py` по одному test node
на процесс. Это не ослабляет тесты: после воспроизводимого `0xC0000005` в
`pyqtgraph.ViewBoxMenu` файл исключён из длинного shared Qt shard, а
`tests/test_test_runner_contract_0790.py` проверяет наличие всех пяти test nodes как отдельных
native batches. Python assertion failures и ненулевые exit status по-прежнему немедленно
останавливают gate.

### REPORT-I18N-01: atomic RU/KK/EN report language

Office-export boundary проверяется отдельно от численных расчётов:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_report_i18n_atomic_language.py `
  tests/test_readable_interpretation_export.py `
  tests/test_hydrocarbon_report_client_limitations.py
```

Regression требует, чтобы выбранный язык workspace явно передавался в XLSX/DOCX; polished
Word cover и body использовали один язык; export progress и missing-value Haworth/DEXP labels
не возвращались к русскому fallback в KK/EN. Проверка содержимого выполняется по фактическому
`word/document.xml`, а не только по UI captions. Численные значения и report model этим
контрактом не изменяются.

### PERF-07: LAS import, first render и viewport baseline

Correctness coverage for the large-LAS profiling boundary:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_process_metrics.py `
  tests/test_las_adapter.py `
  tests/test_dataset_import_jobs.py `
  tests/test_main_window.py
```

The tests preserve the existing `las.import.performance` timing contract and verify RSS checkpoints
without exposing source values/full paths. PERF-07 additionally requires non-negative
`parse_stream_setup_ms`, `parse_lasio_ms` and `parse_index_ms`; these are observational
subphases of the existing `parse_ms`, not independent parser semantics or release thresholds.
The end-to-end benchmark carries the same fields into the Windows quality artifact. For the numeric fast-path
slice the clean PERF-07 fixture must report `parse_backend=numpy-loadtxt`; integration tests verify
NULL replacement, positional curve assignment and a `WRAP=YES` compatibility fallback that performs
the established full lasio read. Unsupported/malformed layouts must fail closed to that fallback rather
than partially accepting a fast matrix. Job-level tests guard the ordered
`job_load → policy → review → register → total` phases and failure-stage metrics. Main-window
tests verify both successful presentation and the existing fail-safe recovery path emit
`las.import.presentation` with duration/RSS. Memory collection is best-effort and cannot fail an
otherwise valid import. These metrics are observational; performance thresholds require a measured
Windows baseline rather than unit-test wall-clock assertions.

The first presentation-coalescing regression is intentionally separate from the LAS metrics:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_presentation_refresh.py `
  tests/test_tablet_partial_title_refresh_source.py
```

It verifies typed intent merging/reset semantics and guards that drag-width/drag-order handlers
schedule Project Tree + window-title refresh instead of calling them synchronously. The width drag
must still use the immediate `DirtyReason.STATIC` track refresh. No test permits coalescing
Dataset replacement, Undo/Redo, import presentation, or a full TabletView rebuild.

Visible-depth refresh regression:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_main_window_visible_depth_refresh.py `
  tests/test_main_window.py::test_curve_metadata_history_refresh_preserves_tablet_track_widgets `
  tests/test_tablet_view.py::test_curve_metadata_refresh_updates_headers_and_membership_in_place
```

The manual range case must keep `DirtyRenderStats.full_updates` and `partial_updates` unchanged
while the displayed/layout range changes in place. Reset must increment `full_updates` exactly
once, preserving the existing default-range resolution, and neither path may rebuild Project Tree.
Curve-metadata history regression additionally requires unchanged `full_updates`, stable track
widget identity and in-place header/unit refresh across Undo/Redo. TabletView metadata regression
also covers mnemonic rename reconciliation without restoring the full widget tree.

End-to-end PERF-07 regression and canonical Windows runner:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_perf07_las_tablet_pipeline.py
python benchmarks/benchmark_las_tablet_pipeline.py --json
```

Обычный unit test использует малый temporary LAS (1000 строк, 8 кривых, 4 видимых track) и
проверяет production import → `TabletView.set_layout_and_dataset()` → scroll → zoom. Он не
содержит wall-clock assertions. Default benchmark использует M-1-shaped fixture: 27 500 строк,
351 data curve, 16 visible curve-track и viewport 1600×900. Release gate сохраняет JSON как
`build/ci-artifacts/quality/las-tablet-pipeline-benchmark.txt`.

Structural gate требует ровно один full rebuild для первого presentation и ноль дополнительных
`DirtyRenderStats.full_updates` на scroll/zoom. `tablet.render.full.finished` дополнительно
содержит `duration_ms`, start/end RSS и peak RSS.

Принятый Windows baseline Release gate #2297 на PR #423: import `12 484.34 ms`, first render
`629.01 ms`, scroll `60.29 ms`, zoom `109.67 ms`; navigation не увеличила full-render counter.
Release gate #2299 затем разложил import на source `809.28 ms`, parse `5 957.19 ms`,
Dataset materialization `14 263.00 ms`, report `44.68 ms`, подтвердив materialization как
крупнейшую фазу.

Текущий regression contract требует наличие неотрицательных subphase metrics:
`dataset_setup_ms`, `dataset_curve_values_ms`, `dataset_curve_canonical_ms`,
`dataset_curve_semantic_ms`, `dataset_curve_store_ms`, `dataset_headers_ms`. Эти метрики
наблюдательные и не меняют import semantics. Следующая оптимизация допускается только после
Windows materialization-subphase baseline.

Release gate #2301 локализовал bottleneck в `dataset_curve_values_ms` (13.89 s из 14.09 s).
Регрессия `test_import_las_materializes_lasio_data_matrix_once` использует test double с
счётчиком computed `data` property и требует ровно одно обращение на импорт при корректных
значениях всех curve columns. Это структурный guardrail против возврата O(curves × full-matrix)
работы; hardware-dependent timing assertion не используется.

## 11. Регрессия GeoScape2/GS2 временного планшета

`tests/test_gs2_time_tablet_rendering.py` проверяет единый расчёт фактической ширины
DATETIME-колонки, canvas и групповых заголовков, а также один transactional render при смене
dataset. Qt-сценарий в `tests/test_tablet_view.py` подтверждает, что статическое обновление не
сжимает временную ось и не нарушает выравнивание треков.

Минимальный запуск:

```bash
python -m pytest -q tests/test_gs2_time_tablet_rendering.py \
  tests/test_gs2_form_axis_hotfix_0789.py tests/test_tablet_view.py
```

## 12. Газовый conditioning, расчёты и rendering

`calculations/gas_conditioning.py` является Qt-независимой границей подготовки C1–C5. Он обязан
сохранять source arrays, поддерживать increasing/descending/duplicate depth, интерполировать
только короткие bounded gaps и возвращать interpolation masks. После conditioning
`calculate_conditioned_ratios()` рассчитывает `TG_CALC`, относительные компоненты, Haworth,
изомерные отношения и Pixler. `ProjectSession` обновляет derived curves с versioned provenance.

Обязательный локальный набор:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_gas_conditioning.py `
  tests/test_project_session_gas_ratios.py `
  tests/test_gas_curve_rendering_continuity.py `
  tests/test_complex_gas_form.py `
  tests/test_a4_factory_templates.py
```

Контракты:

- source C1–C5 и depth не изменяются;
- mixed/nonfinite axis отклоняется;
- short gap восстанавливается, long/edge outage остаётся `NaN`;
- конечный zero не перезаписывается и разрывает logarithmic curve;
- duplicate-depth finite measurement имеет приоритет над missing row;
- C4/C5 не учитываются одновременно как aggregate и split family;
- сумма доступных `*_REL` равна 100% на валидной строке;
- zero denominator не создаёт infinity;
- recalculation сохраняет curve ID, повышает version и обновляет metadata/provenance;
- gas-only render policy не применяется к GR/ROP/DEXP;
- context points сохраняют сегмент на границе viewport/PDF page;
- screen/preview/PDF используют одинаковые derived arrays и segment semantics.

Ручной regression выполняется после повторной команды **«Рассчитать базовые Gas Ratio»** на
обезличенном интервале `1703.28–1753.28 м`. Старый PDF автоматически не обновляется.

Диагностический benchmark:

```powershell
python benchmarks/benchmark_gas_conditioning.py 100000 1000000 --repeats 3
python benchmarks/benchmark_gas_conditioning.py 100000 1000000 --repeats 3 --json
```

Benchmark измеряет conditioning семи компонентов и полный derived profile. Обязательные
scaling/RSS thresholds закрепляются после стабильного Windows baseline в задаче GAS-08; случайный
wall-clock assertion не добавляется в обычный unit suite.

## 13. GAS-05: единый continuity policy и segment mask

`tests/test_curve_continuity_policy.py`, `tests/test_gas_conditioning.py`, `tests/test_gas_curve_rendering_continuity.py` и `tests/test_tablet_gas_segment_mask.py` проверяют общий cadence policy, короткие и длинные пропуски, реальные нули, viewport/page context и явный PyQtGraph connect mask. Relative gas, Haworth, Pixler и source C1–C5 используют тот же экранный/печатный geometry path.

```powershell
python -m pytest -q tests/test_curve_continuity_policy.py tests/test_gas_conditioning.py tests/test_gas_curve_rendering_continuity.py tests/test_tablet_gas_segment_mask.py
```

## 13A. ОПУС: формулы, автоматическая интерпретация и паспорт методики

Минимальная проверка отдельного режима ОПУС и одинакового содержания отчётов:

```powershell
python -m pytest -p no:cacheprovider -q tests/test_opus_screening.py tests/test_hydrocarbon_interpretation.py tests/test_interpretation_report_charts.py tests/test_interpretation_report_identity.py
```

Набор закрепляет следующие контракты:

- равенство результатов для эквивалентных входов в `% об.` и ppm;
- четыре контрольные формулы и отсутствие `OPUS5_REF` в runtime/экспорте;
- классификацию только по отсчётам выше порога аномалии;
- единственное пересечение перекрывающихся диапазонов и отказ от класса вне профиля;
- явную цепочку ОПУС → Haworth/Pixler → неопределённый тип;
- сохранение найденных интервалов при низком фоне с отдельной отметкой применимости;
- одинаковые ОПУС-кривые на экране и в PDF и полный ряд глубин в XLSX;
- наличие в HTML/PDF, DOCX и XLSX формул, правил интерпретации, источников и степени
  подтверждения методики.

## 13B. Профиль «ОПУС Газомер»

Этап `OPUS-01` закреплён в `tests/test_opus_gasomer_fixture.py`: primary-workbook SHA,
контрольная строка, пять формул, каждая граница ниже/на/выше, явная errata AB4 и уникальная
мода без произвольного разрешения ничьей. `tests/test_opus_gasomer_batch.py` закрепляет
`OPUS-02`: ppm/% equivalence, синхронный независимый TotalGas, LOD boundary, missing/zero/
below-LOD/invalid states, зависимости отдельных показателей и неизменность source arrays.
`tests/test_opus_gasomer_interval.py` закрепляет `OPUS-03`: уникальную поддержку по
синхронным строкам, ничью интервала, QC/vote distributions, explicit maximum span и
доказательство синтетического legacy-состава из разных глубин.
`tests/test_opus_gasomer_detector.py` закрепляет `OPUS-04`: низкий фон без hard gate, отсутствие
ложного события на ровном фоне, смену локального фона, ppm/% equivalence, обязательный LOD,
монотонную прямую/обратную глубину и сохранение missing/invalid states.
`tests/test_opus_gasomer_report.py` закрепляет `OPUS-05/06`: отдельный TotalGas и явный LOD,
готовый report snapshot с прямым классом/support, пятью голосами/QC и provenance, одинаковые
формулы/класс в HTML, XLSX, DOCX, PDF и print HTML, неизменность исправления
`AB2>AB5=250000` → `AB2>=250000`, а также запрет скрытого detector LOD.
`tests/test_opus_gasomer_performance_contract.py` и
`benchmarks/benchmark_opus_gasomer.py` закрепляют `OPUS-07`: chunked regular-axis fast path,
physical-window fallback для нерегулярной оси, 25k/100k/1M и additional traced peak memory.

Воспроизводимый performance-run:

```powershell
python benchmarks/benchmark_opus_gasomer.py 25000 100000 1000000 --json
```

Контрольный Windows/Python 3.11 run 30 августа 2026 года:

| Строк | Batch, с | Detector, с | Batch peak, MiB | Detector peak, MiB |
|---:|---:|---:|---:|---:|
| 25 000 | 0,024 | 0,293 | 5,1 | 64,6 |
| 100 000 | 0,034 | 0,841 | 18,5 | 67,9 |
| 1 000 000 | 0,381 | 8,168 | 185,0 | 118,6 |

Traced peak не включает уже созданные source arrays. От 100k к 1M batch/detector дали
11,28×/9,72× времени при росте данных 10×; retained/result arrays растут линейно, а временный
rolling block ограничен по числу window elements. Пересчёт при PDF/печати запрещён report
snapshot-контрактом и проверяется экспортным тестом.

Дальнейшая полевая проверка:

1. confusion matrix на независимых интервалах ГИС/испытаний;
2. анализ false positive/false negative и отдельная версия полевой калибровки.

Полевой acceptance выполняется отдельно на обезличенных интервалах с независимым заключением
ГИС/испытаний. Для каждого класса строится confusion matrix и анализируются false positive и
false negative. До этого автоматический результат называется предварительным скринингом.
Подробные ожидаемые значения и порядок этапов:
[OPUS_GASOMER_IMPLEMENTATION.md](OPUS_GASOMER_IMPLEMENTATION.md).

## 13C. WITS operator workspace, live calculations and alarms

Для WITS-UX/CALC/GASCTX/ALARM/INTERP обязательны отдельные уровни проверки:

- **headless forms:** roundtrip Save/Reset по canonical mnemonic; новый Dataset/curve ID не ломает
  выбор; factory template не мутируется;
- **Qt adaptive:** форма выбирается до runtime, sidebar collapse, fullscreen → back, LIVE PREVIEW →
  persistent handoff, DPI 100/125/150/200%;
- **derived parity:** WH/BH/CH, Pixler и DEXP/DEXPC live результат совпадает с batch calculation
  на одинаковом интервале; проверяются missing inputs, NaN/zero и UOM conversion;
- **gas context:** background baseline не обучается connection/trip/circulation spikes;
  formation_show требует stable drilling + excursion; отсутствие контекста даёт
  elevated_unclassified;
- **interpretation markers:** line/band остаётся на исходной axis coordinate, badge может
  визуально смещаться; одинаковые соседние классы объединяются; overlapping labels не перекрываются;
- **alarms:** min/max boundary, hysteresis, debounce/minimum-duration, acknowledgement, mute,
  restart persistence и отсутствие repeated audio на каждом sample;
- **performance:** live-derived + alarms остаются bounded по памяти и не добавляют O(N²) на redraw;
- **field acceptance:** anonymized real GSWITS, reconnect/reopen, connection/trip events и
  подтверждение специалистом ГТИ, что fluid screening не смешан с gas origin.

## 13D. Формульный аудит, печатный стиль и флюид-выноски

Обязательные regression-gates для CALC-AUDIT-01 / PRINT-STYLE-01 / REPORT-ANNOT-01:

- все профили из `build_all_sourced_formula_registry()` присутствуют в method audit manifest;
- Haworth/Pixler/DEXP/DEXPC остаются strict primary/publication verified;
- ОПУС допускает `secondary_crosscheck` / `workbook_reproduced`, а detector defaults —
  только `engineering_default` pending field calibration;
- Report Passport для sourced calculation сохраняет formula id/version/provenance,
  expression hash и source;
- canonical print wordmark — **DIGITAL GEOLOG GASRATIO&PIXLER** — одинаков в PDF, Masterlog,
  DOCX/XLSX и PDF creator metadata;
- `tests/test_product_branding.py` дополнительно запрещает полный canonical wordmark literal во всех `src/**/*.py`, кроме `geoworkbench/brand.py`, чтобы новые adapters не создавали второй source of truth;
- polished interpretation DOCX проверяется с подменённым `ReportVisualProfile`: production OOXML обязан использовать semantic accent/text/muted colours, title/body/table sizes, table header fill и border roles из профиля;
- Masterlog neutral-chrome regression подменяет `ReportVisualProfile` и проверяет реальные
  QPainter page/accent-soft placeholder fills и text/border/border-strong/critical pens; lithology,
  stratigraphy, LBA, user curve и annotation/callout colours остаются отдельными semantics;
- fluid callout явно содержит тип флюида, а ambiguous/no-consensus не превращается в
  искусственно выбранный gas/oil class;
- dense adjacent callouts остаются внутри track bounds; для A4/A3 выполняются visual/PDF
  regression и grayscale-проверка;
- цвет не является единственным признаком: текстовая подпись должна сохранять смысл
  после grayscale/monochrome печати.

## 14. Правило обновления тестов и документации

Любое изменение запуска, импорта, формы, миграции, расчётного профиля, формата проекта или
пользовательского поведения должно в одном инкременте обновлять:

- production code;
- positive/boundary/negative regression tests;
- `PROJECT_PLAN.md`, если изменились приоритеты, риск или статус задачи;
- `ARCHITECTURE.md`, если изменилась граница или источник истины;
- корневой README, если изменился запуск или базовый workflow;
- соответствующие RU/KK/EN-инструкции;
- `CHANGELOG.md`;
- `tools/check_documentation.py`, если новый контракт можно проверить автоматически.

Версия не считается готовой только по `compileall` или выбранным тестам. CI artifact должен
показывать реально выполненные проверки. После интеграции удаляются временные ветки, patch
workflow, trigger-файлы и artifacts.

Для composition-root контракта ARCH-01 минимальный regression-набор:

```bash
python -m pytest -q tests/test_application_context.py tests/test_application_context_ui_wiring.py \
  tests/test_etp12_dialog_typing.py tests/test_witsml1411_soap.py
```

Он проверяет отдельный project scope, process-wide registry/report services, DI credentials/audit
для WITSML/ETP и production MainWindow wiring. Полный Release gate остаётся обязательным.

Для первого feature-coordinator инкремента ARCH-02:

```bash
python -m pytest -q tests/test_witsml_import_coordinator.py \
  tests/test_witsml_project_import_controller.py tests/test_witsml_import_dialog_source.py
```

Набор фиксирует автоматический выбор target well, атомарную регистрацию уже проверенного commit
и source-contract, запрещающий MainWindow напрямую создавать WITSML project-mutation controller.

Для второго ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_lag_correction_project_controller.py \
  tests/test_lag_correction_ui_source.py
```

Набор проверяет source/projection selection, восстановление исходной projection только при
неизменённом выборе, typed missing-source failure и отсутствие прямой записи
`current_dataset_id` из MainWindow.

Для третьего ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_gas_ratio_project_controller.py \
  tests/test_project_session_gas_ratios.py
```

Набор проверяет conditioned Gas Ratio/Haworth/Pixler persistence, controller rebinding,
совместимый session shim и source-contract, запрещающий MainWindow напрямую вызывать mutating
`ProjectSession.calculate_basic_gas_ratios()`.

Для четвёртого ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_gs2_import_coordinator.py \
  tests/test_dataset_import_jobs.py tests/test_proj04_gs2_source_registry.py
```

Набор проверяет GS2 enrichment/registration, provenance source registry, отсутствие прямых
Dataset-записей в обоих слоях MainWindow и отсутствие второго production `open_gs2()`.

Для пятого ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_canvas_object_transfer_coordinator.py \
  tests/test_canvas_object_transfer_mainwindow.py \
  tests/test_canvas_object_transfer_workflow.py
```

Набор проверяет transactional material autosave, session rebinding, invalidation старого review
и source-contract, запрещающий production UI создавать canvas controller/workflow вручную.

Для шестого ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_late_analysis_coordinator.py \
  tests/test_late_analysis_review_dialog.py \
  tests/test_well_analysis_update_workflow.py
```

Набор проверяет source load, WELL-02 apply/material autosave, completion count, project rebinding,
инвалидацию старого review и отсутствие ad-hoc controller/workflow в production MainWindow.

Финальный ARCH-02 mutation boundary:

```bash
python -m pytest -q tests/test_arch02_ui_mutation_boundary.py
```

AST/source-contract запрещает прямые assignments и mutating calls к ProjectSession/project
collections/Dataset/Well из обоих MainWindow-слоёв и проверяет наличие утверждённых feature
coordinators. Полный Release gate остаётся обязательным перед merge.

Первый ARCH-03 state extraction:

```bash
python -m pytest -q tests/test_curve_pencil_state.py tests/test_tablet_edit_pipeline.py
```

Набор проверяет Qt-независимые transitions Curve Pencil и совместимость существующего TabletView
edit pipeline. Полный Release gate остаётся обязательным перед merge.

Второй ARCH-03 navigation extraction:

```bash
python -m pytest -q tests/test_tablet_navigation_coordinator.py
```

Набор проверяет projection visible range → scrollbar state, full-range collapse, обратное
scrollbar → visible range преобразование и существующие pan/zoom/keyboard transitions.

Третий ARCH-03 interval editing extraction:

```bash
python -m pytest -q tests/test_interval_editing_state.py tests/test_tablet_edit_pipeline.py
```

Набор проверяет mode/default-type transitions, lifecycle CREATE/RESIZE gesture и source-contract,
что `TabletView` делегирует editing-session state Qt-независимому компоненту.

Четвёртый ARCH-03 selection-state extraction:

```bash
python -m pytest -q tests/test_selection_interaction.py
```

Набор проверяет единый interval-selection source of truth в `SelectionManager`, active
interpretation context и source-contract на отсутствие параллельных selected-id полей в `TabletView`.

Пятый ARCH-03 render-state extraction:

```bash
python -m pytest -q tests/test_tablet_render_state.py \
  tests/test_tablet_geometry_cache.py tests/test_tablet_overlay_layers.py
```

Набор проверяет ownership geometry/static caches, dirty invalidation и отсутствие прямого
mutable render-state ownership в `TabletView`.

Финальный ARCH-03 tablet-state boundary:

```bash
python -m pytest -q tests/test_arch03_tablet_state_boundary.py
```

AST/source-contract проверяет отсутствие legacy mutable state в `TabletView.__init__`, наличие
утверждённых headless state/coordinator components, stateless sampling boundary и отсутствие
PySide6/pyqtgraph top-level imports в ARCH-03 state modules.

Первый ARCH-04 semantic-context boundary:

```bash
python -m pytest -q tests/test_semantic_channels.py tests/test_semantic_binding_propagation.py
```

Набор проверяет immutable context, deterministic catalog version, mapping evidence, stale-context
rejection, compatibility `resolve()` и переход LAS на `context() → resolve_context()`.

Второй ARCH-04 CSV semantic-context slice:

```bash
python -m pytest -q tests/test_semantic_csv_import.py tests/test_semantic_channels.py
```

Набор проверяет CSV/TXT column/header evidence, catalog version provenance и source-contract на
`context() → resolve_context()` без отдельного semantic resolver path.

Третий ARCH-04 Paradox semantic-context slice:

```bash
python -m pytest -q tests/test_paradox_import.py tests/test_semantic_channels.py
```

Набор проверяет Paradox field/mapping evidence, raw-time projection, catalog version provenance
и source-contract на `context() → resolve_context()` без legacy resolver path.

Четвёртый ARCH-04 WITS0 semantic-context slice:

```bash
python -m pytest -q tests/test_wits0_import_review.py tests/test_semantic_channels.py
```

Набор проверяет WITS0 record/item/source-id evidence, automatic/reviewed mapping state,
catalog version provenance и source-contract без legacy `SemanticChannelDictionary.resolve()`.

Пятый ARCH-04 WITSML semantic-context slice:

```bash
python -m pytest -q tests/test_witsml_data_arrays.py tests/test_semantic_channels.py
```

Набор проверяет WITSML channel position/key/uuid evidence, automatic/reviewed/commit mapping state,
catalog version provenance и отсутствие legacy resolver path в общем WITSML Import Review.

Шестой ARCH-04 generic Import Review semantic-context slice:

```bash
python -m pytest -q tests/test_import_review.py tests/test_import_review_controller.py \
  tests/test_semantic_channels.py
```

Набор проверяет read-only inspection, reviewed remapping, сохранение исходного importer evidence
при manual override, catalog version provenance и отсутствие production legacy resolver path.

Седьмой ARCH-04 ETP 1.2 semantic-context slice:

```bash
python -m pytest -q tests/test_etp12_acquisition.py tests/test_etp12_source_contracts.py \
  tests/test_semantic_channels.py
```

Набор проверяет ETP channel URI/id evidence, automatic/reviewed/commit mapping state,
catalog version provenance, сохранение UOM conversion plan и отсутствие legacy semantic resolver.

Финальный ARCH-04 production-wide semantic boundary audit:

```bash
python -m pytest -q tests/test_arch04_semantic_context_boundary.py tests/test_semantic_channels.py
```

AST/source-contract проходит весь `src/geoworkbench`, отслеживает production-объекты
`SemanticChannelDictionary` по типам, factory и присваиваниям и запрещает legacy
`.resolve()` вне compatibility shim. Одноимённые resolver-методы UOM и других сервисов
не считаются нарушением.

ARCH-05 layer import boundary:

```bash
python -m pytest -q tests/test_arch05_layer_import_boundary.py
```

Recursive AST-contract проходит все Python-файлы `src/geoworkbench/domain` и
`src/geoworkbench/calculations`. Проверяются absolute/relative `Import` и `ImportFrom`
в любом AST scope; запрещены PySide/PyQt, PyQtGraph/qtpy, `geoworkbench.ui` и
`geoworkbench.printing`. Таким образом нижние domain/calculation слои остаются headless и
не получают обратную зависимость на UI/printing adapters.

ARCH-06 versioned calculation/conditioning profiles:

```bash
python -m pytest -q tests/test_calculation_profiles.py \
  tests/test_gas_conditioning.py tests/test_gas_ratio_project_controller.py \
  tests/test_project_session_gas_ratios.py tests/test_formula_profiles.py
```

Набор проверяет immutable `GasRatioCalculationProfile`, versioned
`CurveContinuityPolicy`, exact profile resolution, передачу profile UI → controller →
calculations, сохранение profile/policy identity в dataset parameters и неизменность формул/
bounded interpolation в Qt-независимом `calculations` слое.

## 15. Каталоги печатных шапок и логотипов

Минимальная доменная и SKF-проверка:

```bash
python -m pytest -q tests/test_header_catalog.py tests/test_logo_catalog.py \
  tests/test_project_logo_catalog_migration.py tests/test_masterlog_presets.py \
  tests/test_skf_importer.py
```

Полный Windows Release gate дополнительно проверяет Qt-диалоги, A4/A3 portrait/landscape,
многостраничный PDF, SVG/PNG assets и отсутствие регрессий существующих Masterlog/форм.

## 16. Приёмка утверждённого сценария WELL-01…06

Для реализованного паспорта WELL-01:

```powershell
python scripts/run_tests.py -p no:cacheprovider tests/test_well_passport_storage.py tests/test_well_passport_headers.py tests/test_well_passport_dialog.py tests/test_well_passport_pdf.py
```

Набор проверяет валидацию и no-op, отмену, выбор legacy-значений, миграцию конструкции,
раздельность скважин и языков, JSON/пакет/перенос/pending recovery, потерянные assets,
скрытие логотипа, обе A4-ориентации и фактическое содержимое PDF на RU/KK/EN. Отдельные
regressions подтверждают, что паспорт предлагает только catalog-backed customer/contractor
logos, новый uncatalogued raw asset отклоняется controller boundary, а неизменённая legacy
raw-logo ссылка остаётся совместимой при правке других полей. PDF-тест инициализирует
Unicode-шрифты тем же способом, что точка входа приложения.
Ручная проверка: «Файл → Паспорт скважины», заполнить общие поля и переводы, сохранить
диалог и проект (Ctrl+S), открыть повторно и сравнить две ориентации в Центре печати.
Физическую печать этот набор не подменяет.

Матрица принята 5 сентября 2026 года для будущих инкрементов, а не как отчёт о пройденных
проверках. Основа — существующий `tests/test_multilingual_geologpkg_workflow.py`, но он один
не подтверждает готовность всех новых сценариев. Требования WFLOW-001…006 находятся в
[REQUIREMENTS.md](REQUIREMENTS.md); этапы закрываются только в [PROJECT_PLAN.md](PROJECT_PLAN.md).

| Этап | Обязательные сценарии и ожидаемые результаты |
|---|---|
| WELL-01 | Миграция legacy JSON/пакета с несовпадающими реквизитами шапок: сохранить исходные варианты, отмена без записи, подтверждённый общий паспорт. Две скважины не меняют друг друга; save/reopen/backup/recovery/перенос сохраняют ID, числовые данные, все языки, логотипы и конструкцию |
| WELL-02 | Накопительный LAS и только новый суффикс; повтор поставки/no-op; новая кодовая литология/шлам поверх уже заполненных списков; поздний анализ только в выбранные пустоты; correction с явным diff. Проверить оси/единицы, границы, неизвестные коды и конфликт профилей фирмы, ручные overrides и переводы. Ноль сохранён, пропуск источника не очищает проект |
| WELL-02 / запись | Изменение источника после preview, отмена, сбой применения/записи, disk-full, внешняя смена проекта. Нет частичного применения; прежняя дисковая ревизия остаётся читаемой, несохранённое состояние обозначено явно, backup проверен. Рассчитанные кривые помечаются для пересчёта по зависимостям |
| WELL-03 | Переключение вкладок удерживает черновики; Cancel не пишет. Несколько шаблонов добавляют три последовательности блоков; save/reopen сохраняет версии, форматирование и ручные дополнения. Изменение каталога не меняет сохранённые описания; обновление блока не стирает другой язык |
| WELL-04 | Пустой перевод, черновик, подтверждённая и устаревшая версии. Изменение исходного поля затрагивает только зависимые переводы; новая глубина не сбрасывает старые статусы. Fallback не записан как перевод, legacy не объявлен проверенным, список готовности ограничен выбранным диапазоном |
| WELL-05 | A4 portrait/landscape × RU/KK/EN для каждой формы: шапка/лист/планшет одной ориентации и языка, одинаковые числовые данные/границы, длинные подписи и rich text без clipping. Пользовательская пара, универсальная шапка, отсутствующая пара и «без шапки» сохраняют намерение пользователя, реквизиты и правки после открытия проекта |
| WELL-06 | Выбор полного/нового/произвольного диапазона, нескольких форм/языков/ориентаций: все результаты одной сохранённой ревизии. Неполный перевод блокирует итоговую выдачу обязательного поля, явный черновик помечен. Изменения проекта во время выпуска не попадают в snapshot; частичный сбой и повтор не смешивают ревизии и не изменяют старые PDF |

Для удаления блока редактор сохраняет невидимую anchor-границу с его `block_id`. Тест обязан
проверять HTML round-trip, атомарное удаление выбранной вставки из RU/KK/EN, сохранение ручного
текста до/после неё и отказ от удаления старого блока без однозначной границы. Для литологии
дополнительно проверяются независимые черновики вкладок, заполнение RU/KK/EN одним заводским
шаблоном, атомарность controller update при ошибочном языке и отсутствие неявного переноса
legacy/`und` fallback в русский перевод.
Для стратиграфии дополнительно проверяются одновременные название и описание RU/KK/EN,
заполнение всех доступных названий из справочника, сохранение общих глубин/кода/ранга/цвета/
параметров подписи и отсутствие частичной мутации при ошибочном языке.
Быстрый ввод из планшета/Masterlog обязан вернуть те же три языковые версии и один набор чисел.
Для кальциметрии/ЛБА проверяются независимые вкладки описания и заключения, однократный ввод
чисел и классификационных признаков, атомарный отказ при ошибочном языке и защита legacy-fallback.
Для project v31 проверяются миграция v30 без переприсвоения legacy-текста, RU/KK/EN round-trip
на обоих уровнях интерпретации, строгий отказ от неизвестного языка и атомарность controller API.
UI интерпретаций дополнительно проверяет вкладки обоих уровней, единичные числовые поля,
локализованные строки таблицы и отсутствие записи показанного legacy-fallback как перевода.
Для project v32 проверяются round-trip состояния перевода с языком/ревизией источника,
ревизией перевода и зависимостями, отклонение неизвестного языка и миграция v31 в пустой
реестр без ложного состояния `reviewed`.
Доменный workflow WELL-04 проверяется на цепочке draft → reviewed → stale, отказе проверки
при изменённом источнике/зависимости, сохранении номера ревизии и изоляции соседних полей.
Контроллер статусов проверяется на атомарность, content revision/dirty, undo/redo, no-op при
несвязанном изменении и блокировку undo после внешней мутации состояния скважины.
Для project v33 проверяются round-trip ledger ревизий авторских полей, пустая миграция v32,
отказ от отрицательных значений и точечное stale/undo без изменения соседнего интервала.

Данные для автоматизации — синтетические/обезличенные. PDF-приёмка включает проверку текста,
границ страниц и визуальный осмотр RU/KK/EN, а не только создание непустого файла. Физическая
печать и Windows HiDPI проверяются через действующий REL-03, новые функции не считаются готовыми
по одному `compileall`. При чисто документационном утверждении этого решения выполняется
документационный gate из [DOCUMENTATION_POLICY.md](DOCUMENTATION_POLICY.md), без заявления
об успешной runtime-приёмке ещё не реализованных функций.

### WELL-02: read-only план числовых обновлений

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_well_update_plan.py tests/test_daily_las_growth.py tests/test_daily_las_growth_dialog.py tests/test_proj04_daily_append_rollback.py tests/test_daily_las_growth_autosave.py
python -m benchmarks.benchmark_well_update_plan
```

Проверяются новая глубина, NaN→0, correction с before/after, отсутствие очистки при
NaN источника, восходящая/нисходящая ось, локальные кривые, ограничение diff,
неизменность обоих Dataset, несовместимые единицы/домен/скважина и устаревший fingerprint.
Локальный Windows baseline 6 сентября 2026: 74 профильных теста прошли; synthetic
100k/1M (одна кривая, заполнение пропусков) — 0.423/4.235 s, ratio 10.01 при 10× строк.
В DTO остаётся 200 ячеек diff при полном счётчике. Это замер времени данного сценария,
не RSS gate и не проверка транзакционного применения новых режимов.

Полный локальный Windows-прогон этого инкремента завершился с кодом 0: 2904 passed, 8 skipped; 8 основных shards и 124 native-heavy batches. Полные Ruff, mypy (486 модулей), documentation audit и diff check прошли. Bandit не установлен в окружении; полный release security gate и физическая приёмка REL-03 остаются открытыми.

Повторная проверка WELL-02 покрыта в `test_well_update_plan.py`: полный/сокращённый/пустой
preview, изменение источника, старого участка, локальной кривой, headers, имени/SHA-256
файла и подмена счётчиков/diff. Успех и отказ сохраняют оба Dataset без изменений.

### Применение WELL-02 и история v26

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_well_update_plan.py tests/test_well_update_apply.py tests/test_well_update_workflow.py tests/test_daily_las_growth_dialog.py tests/test_daily_las_growth_autosave.py tests/test_proj04_daily_append_rollback.py
python -m benchmarks.benchmark_well_update_apply
```

Покрываются явный выбор ячеек, скрытый/подменённый diff, возрастающая/убывающая ось,
NaN и ноль, no-op после повторного анализа, ошибки выделения памяти/регистрации источника,
отмена, external-change, disk-full без ложного успеха, пакетный roundtrip исходных LAS и
истории, миграция v25 → v26 и отказ повреждённой истории. Benchmark 100k/1M проверяет
200 выбранных ячеек и предел временной памяти 240 bytes/row + 8 MiB.

### Геологическое дополнение WELL-02 (v27)

Целевые проверки: `tests/test_well_geology_update.py` и
`tests/test_well_geology_workflow.py`: свободные интервалы, ручные описания и переводы,
коллизии поставщиков, неизвестные коды, разрывы глубины, устаревший план, сохранение
профиля и исходника, откат при ошибке, миграция v26.
Полный прогон и security gate текущего инкремента пока не завершены.


### ARCH-07: общая история редактирования

Первый инкремент проверяет общий chronological stack для Curve Pencil и LAS Header Editor:
cross-domain порядок undo/redo, очистку всей redo-ветки после нового изменения, неизменность
стеков при conflict, listener state для QAction, domain-safe локальный curve undo и глобальную
маршрутизацию MainWindow. Второй инкремент добавляет Curve Metadata update/create/remove:
проверяются shared-history injection, запрет локального undo через более новую команду другого
домена, сохранение существующих conflict guards и global MainWindow routing. Третий инкремент
добавляет Curve Transfer: перенос нескольких кривых является одной командой общего history,
локальные transfer Undo/Redo не перескакивают через более новую команду другого домена, metadata
и values external-change остаются fail-closed, а полностью отменённая Curve Pencil правка не
блокирует последующий Undo переноса из-за одного лишь увеличившегося version counter. Четвёртый
инкремент добавляет Dataset Merge: проверяются два последовательных merge с многошаговым
Undo/Redo, восстановление layout/source sidecars, global MainWindow routing, domain-safe локальные
Merge actions, блокировка при реальном изменении результата и успешный Undo после полностью
отменённой Curve Pencil правки несмотря на увеличившийся curve version. Отдельный disk/export
rollback regression проверяет, что неуспешный merge не остаётся в history и восстанавливает
существовавшую до операции redo-ветку. Пятый инкремент добавляет in-place External LAS Insert:
проверяются shared-history injection, несколько последовательных вставок, domain-safe локальный
Undo, factual metadata/value conflict guard, Undo после полностью отменённой Curve Pencil правки и
global MainWindow routing. Шестой инкремент добавляет Lithology Add/Update/Delete: проверяются
многошаговый chronological Undo/Redo, сохранение identity интервала, translation-tracking
sidecars, domain-safe local undo, fail-closed внешний конфликт и global MainWindow routing.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_edit_history.py tests/test_curve_editing_controller.py tests/test_header_editing_controller.py tests/test_curve_metadata_controller.py tests/test_curve_transfer_controller.py tests/test_dataset_merge_controller.py tests/test_external_las_insert_controller.py tests/test_lithology_controller.py tests/test_main_window.py
```


### RPT-QA-01: многостраничные PDF-графики и подписи параметров

Печатный renderer обязан изолировать `QPainter` state между fluid-marker overlay и следующим
листом. Regression воспроизводит ранее наблюдавшийся дефект: полупрозрачная белая marker brush
не должна оставаться активной и превращать финальный `drawRect()` следующей страницы в белую
заливку поверх уже нарисованных кривых. Отдельно проверяется, что legend label берётся из
semantic/Sensors metadata и методики отчёта: source mnemonics вроде `S106`, `S1003`, `S224`
не используются как основной пользовательский заголовок, когда известны «Скорость бур.»,
«Расх. на вых.» и `D-exponent`.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_hydrocarbon_interpretation_pdf_chart_range.py tests/test_interpretation_report_charts.py
```


Дополнительный fluid-classification regression сохраняет сырые Haworth/Pixler палетки, но
проверяет report-safe decision layer: конкретный нефтяной подтип разрешается только при
`wetness robust z >= 2.0`, согласованной Pixler oil-band и немixed profile; иначе результат
понижается до вероятных жидких УВ или переходного «жидкие УВ / газоконденсат». Формулировки
и rationale проверяются одновременно на русском, казахском и английском языках.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_gas_ratio_interpretation.py tests/test_hydrocarbon_interpretation.py
```


### RPT-QA-01: терминология флюида и читаемые параметры

Видимые отчёты и графики не должны показывать vendor/source mnemonics вроде `S224`,
`S106`, `S1003`, если semantic/Sensors resolver однозначно определяет физический параметр.
Например `S224` в пользовательском выводе становится `D-exponent`. Exact source mnemonic
сохраняется в доменной модели и скрытых audit/source sheets для воспроизводимости.

Fluid labels проверяются на трёх языках как один семантический контракт:
- неопределённый тип: «УВ-флюид неопределённого типа»;
- жидкая тенденция без подтипа: «жидкая УВ-фаза; тип не установлен»;
- согласованная light-oil тенденция: «признаки лёгкой нефтяной фазы»;
- переход light oil / gas condensate: «жидкая УВ-фаза; возможны лёгкая нефть или газоконденсат»;
- газовый класс: «газовая УВ-фаза».

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_parameter_labels.py tests/test_interpretation_report_charts.py tests/test_hydrocarbon_interpretation.py tests/test_hydrocarbon_fluid_markers.py
```


### RPT-QA-01: OPUS-графики и OPUS Газомер

OPUS использует тот же presentation contract, что и стандартный отчёт. В пользовательских
графиках `OPUS_TG_PCT` отображается как локализованное физическое имя, индикаторы ОПУС
не печатают внутренние мнемоники, а class code 1–7 сохраняется отдельно от локализованной
интерпретации. Маркерные категории должны использовать фазовые формулировки:
нефтяная фаза, газовая УВ-фаза, газоконденсатная УВ-фаза, газированная нефтяная фаза
или УВ-флюид неопределённого типа.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_hydrocarbon_fluid_markers.py tests/test_parameter_labels.py tests/test_interpretation_report_charts.py
```


## WITS-ALARM-01 runtime regression

Alarm-domain, persistence/editor and live-runtime checks can be run together with:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_wits0_alarms.py `
  tests/test_wits0_live_forms.py `
  tests/test_wits0_alarm_settings_editor.py `
  tests/test_wits0_live_alarms.py `
  tests/test_acquisition_live_view.py `
  tests/test_wits0_live_view.py `
  tests/test_wits0_operator_dashboard.py
```

The runtime regression specifically guards against debounce advancing on repeated UI refreshes, catches up every DATA_ROW in a drained batch even when the plot is paused/frozen, ignores unrelated record rows, resets pending debounce on an explicit missing channel sample, preserves active alarms through missing input, isolates duplicate canonical mnemonics by curve ID, covers derived-channel catch-up through `source-records` provenance while ignoring unrelated WITS records, and verifies acknowledgement without alarm clearing. It also verifies bounded factual activation/clear history, preservation of CLEAR+ACTIVATE on a direct opposite-side crossing, no fabricated event when a rule is seeded from an existing value, time/depth row-to-axis lookup, one audio cue for a batch containing one or more audio-enabled activations, no replay on an empty/repeated refresh, visual-policy filtering and red activation/green clear threshold markers.

PRINT-STYLE-01 standard grayscale candidate regression in
`tests/test_interpretation_report_charts.py` drives the production band painter with a real
`HydrocarbonCandidateInterval` and asserts three independent cues: filled depth band, fluid
marker geometry, and short text code. The test does not alter classification or source values.

PRINT-STYLE-01 shared-adapter regressions: `tests/test_print_style_shared_adapters.py`
экспортирует geological HTML/PDF/DOCX/XLSX на RU/KK/EN через production entry points.
Изменённый grayscale fixture profile подтверждает shared palette/typography в CSS, OOXML
и workbook styles; PDF проверяется по фактическому тексту. Source curves неизменны.
Qt painter regression проверяет ширину wordmark рядом с номером страницы и restore состояния.
Пункты толщины правил simple tablet header/footer переводятся по DPI устройства;
regression проверяет неизменную физическую толщину при 72/96/144/300/600 DPI.

Geology Office table regression в `tests/test_interpretation_report.py` проверяет все четыре
XLSX table sheets: A4 landscape, physical 100% scale, horizontal pagination, repeat row 1/column A,
минимум 24 pt для wrapped header, shared table font/header fill, alternating body fill,
numeric right alignment и canonical wordmark + &P/&N footer. Существующие проверки продолжают
подтверждать formula-like text safety и исходные типы/значения отчёта.

Document-control slice проверяется `tests/test_report_document_control.py`: 12 production
PDF/DOCX/XLSX комбинаций RU/KK/EN × standard/OPUS × empty/explicit date; authoritative
analysis interval, source-array immutability и неизменный generation audit. Шесть real-workspace
экспортов после package save/reopen подтверждают language selection и отсутствие утечки OPUS
headers в standard. Отдельный тест фиксирует frozen snapshot и formula-like literal cells.

Masterlog document-control: `tests/test_masterlog_document_control.py` проверяет 12 production
PDF/save/reopen сочетаний RU/KK/EN, пустой/явной даты и наличия паспорта скважины,
независимость копии формы и исходной оси. Ещё три GUI regression проверяют доступность
в редакторах данных/динамического поля и очистку даты при принятом паспорте.

Generic document-control: `tests/test_generic_report_control.py` covers 12 RU/KK/EN project
save/reopen HTML/DOCX combinations (bound/unbound form, empty/explicit date), parses every
XML/relationship part, checks footer PAGE/NUMPAGES and repeated table headers, escaped long
text, selected interval and unchanged source arrays. Four guards verify missing/changed form
revisions preserve an existing output; one regression checks compact footer normalization.

Generic control regression matrix now includes real XLSX export after project reopen,
RU/KK/EN sheet names, print-title/footer settings, number types, measured zero, missing
and unavailable channels. Two additional changed/missing-revision guards cover Excel;
three language cases verify formula-like document metadata remains literal text. Existing
interpretation XLSX regressions cover the extracted shared document-control adapter.

`tests/test_masterlog_control_layout.py` adds 18 real PDF export/reopen cases across RU/KK/EN,
A4/A3/roll and empty/explicit date. Each page retains the selected job interval and approvals,
reserves the footer, and preserves physical depth scale including partial final pages. Stored
forms and source arrays remain unchanged. One regression checks multilingual row suppression
and legacy inactivity; ten narrow/wide long-text cases at 72/96/144/300/600 DPI verify all
automatic text rectangles stay outside the graph body.

`tests/test_interpretation_control_footer.py` covers 24 production PDF exports after package
save/reopen: RU/KK/EN × standard/OPUS × empty/explicit date × portrait/landscape. Every
page retains document/revision/status/confidentiality and localized numbering; saved
composition, depth and curve arrays are unchanged. Ten narrow/wide QPdfWriter cases at
72/96/144/300/600 DPI verify footer bounds and extracted physical font size. One regression
checks that empty footer metadata retains legacy content geometry even with an explicit date.

Six production overflow regressions in `tests/test_interpretation_report_charts.py` replace
an old source-string suppression check. RU/KK/EN × FULL/HIDE verify a 120-rock catalog:
methodology precedes charts, full legends follow charts with every code/name preserved,
and HIDE suppresses the catalog. The existing Windows method/geology ordering regression
is retained unchanged.

`tests/test_report_document_control_docx_footer.py` adds 24 polished Word export/reopen
cases: RU/KK/EN × standard/OPUS × empty/explicit date × short/long XML-sensitive metadata.
Every XML/relationship part is parsed; footer content type and relationships, both section
references, margin reservation, percentage widths, exact row heights, PAGE/NUMPAGES and
font size are checked. Full metadata remains in the cover; footer details are bounded and
exclude date/audit values. Composition, depth and curve arrays are unchanged. Six ordinary
exports cover localized shared brand/numbering; one injected rewrite failure preserves an
existing output and removes staging files. Generic Office regressions cover the shared adapter.
Word pagination and physical printer acceptance remain separate checks.

Windows WITS operator-dashboard tests use the existing fresh-process-per-test policy
in `scripts/run_tests.py` after an observed 0xC0000005 in a large offscreen Qt shard.
`test_windows_qt_test_isolation.py` verifies that every dashboard node is scheduled exactly
once, outside the regular shard, in its own batch. All dashboard assertions remain intact.

Masterlog visual-profile regressions (`test_masterlog_header_visual_profile.py`) substitute
colour/grayscale profiles and typography/rule metrics, verify real QPainter output and
explicit form overrides, then save/reopen and export A4/A3/roll PDF in RU/KK/EN. Vector PDF
fills/borders and reusable header backgrounds must follow the injected profile; source
curve arrays and the saved template remain unchanged. Physical print acceptance remains open.

`test_masterlog_curve_legend.py` compares legend and plotted QPen colour/width/style for
all four saved line styles, checks point predicate identifier parity, vendor-bound units,
missing channels and narrow positive label rectangles. RU/KK/EN × A4/A3/roll project reopen
exports inspect PDF dash geometry and real black-on-white QPainter output; persisted
column properties and source arrays remain unchanged. Physical acceptance remains open.

Masterlog grid/profile regressions check colour/grayscale roles, saved alpha 0/0.6/1,
major/minor physical weight and five-metre coordinate invariants. RU/KK/EN reopen exports
at injected PDF writer DPI 72/300/600 verify vector border weights and depth font role,
with source arrays and templates unchanged. The production export DPI setting stays 300.

Gas-context print-track regressions (`tests/test_gas_context_print_track.py`) cover all 13 event
type codes and RU/KK/EN labels, existing registry priority for overlaps/repeats/point events,
draft/hard-exclusion visibility, neutral/grayscale border styles and exact-depth tiny bands.
Project save/reopen drives standard/enhanced PDF plus PNG preview and asserts registry/candidate
and source-array immutability. Isolated real-PDF context painters verify 6 pt codes at
72/300/600 DPI; the production interpretation PDF path uses 72 DPI. A 100-event legend with
long IDs verifies wrapping, pagination, complete text and page bounds. Physical printer and
live/tablet alarm acceptance remain open.

`tests/test_gas_context_report_identities.py` checks every InterpretationImpact and real standard/OPUS save/reopen followed
by HTML, PDF, standard/polished DOCX and XLSX export in RU/KK/EN. Repeated events keep distinct
IDs, hidden draft/hard-excluded events stay absent, XML/HTML-sensitive and formula-like IDs
remain text, and depth/TG/QC cells remain numeric. PDF assertions allow natural line wrapping;
source arrays, registry, candidates and suppressed audit evidence remain unchanged.

Existing gas-context print-track regressions retain all 13 event-code/type labels in RU/KK/EN.

## Signed-depth gas-context acceptance

`tests/test_gas_context_negative_depth_acceptance.py` проверяет отрицательные MD/TVD/TVDSS
через transactional editor, JSON/package save/reopen, выбранный standard/OPUS interval
и реальные HTML/PDF, обычный/оформленный Word, Excel на RU/KK/EN. Проверяются event ID,
границы, measured TG/manual QC/delta, числовые ячейки и неизменность источников/audit.
Отдельно проверяются UI TVDSS без clamping, отказ add/update при NaN/inf/обратных границах,
analysis range validation, time-axis rejection и неприменение чужой/неоднозначной legacy оси.
Well-wide события могут выходить за диапазон одного dataset; ограничение относится к
выбранному analysis interval. Этот автоматический gate не заменяет физическую/полевую приёмку.

## Geology-legend visual-profile regression

`tests/test_geology_legend_visual_profile.py` checks colour/grayscale semantic profile substitution,
unchanged lithology patterns and LBA intensity colours, real full/compact RU/KK/EN PDF text at
72/300/600 DPI (physical caption/table point sizes and border weights), and production
standard/OPUS PDF plus PNG after project reopen. Source arrays and geology snapshots remain
unchanged. Existing legend/readability tests cover complete code decoding, long labels,
explicit ellipsis and large-catalog pagination; physical printer acceptance remains external.

`tests/test_interpretation_chart_visual_profile.py` checks 24 real multipage PDF cases: standard/enhanced, RU/KK/EN, A4 portrait/landscape and colour/grayscale profiles. Distinct substituted palette roles must appear in actual fills, strokes and text; source curve colours, arrays and metadata remain unchanged.

`tests/test_interpretation_heading_rule_profile.py` covers invalid physical font sizes, unchanged pixel-preview fonts, real wrapped RU/KK/EN headings at 72/300/600 DPI and actual standard/enhanced multipage A4 portrait/landscape PDFs under custom typography/rule profiles. It checks full heading text, reserved bounds, physical point sizes/line widths and unchanged source arrays; remaining non-heading chart typography and physical printer acceptance are separate scopes.

`tests/test_interpretation_text_physical_dpi.py` checks 42 actual PDFs: standard/enhanced RU/KK/EN charts at 72/300/600 DPI in A4 portrait/landscape, including signed depths and substituted integer table/caption sizes, plus real candidate codes at each DPI. Extracted title, axis, legend and marker sizes must retain their physical 72-DPI baseline; source arrays/metadata and candidate identity remain unchanged.

Interpretation source curves and ratio-reference traces use non-cosmetic physical-point pens (1.25/0.7 pt); real PDF stroke-width/dash regressions at 72/300/600 DPI prevent high-resolution washout while retaining source values, colours and geometry.

Ratio-scale readability: `tests/test_ratio_scale_heading.py` проверяет реальные PDF 72/300/600 DPI, 22/40/90 pt lanes, linear/log scales, полные bounded endpoint labels без пересечения, caption profile substitution и production RU/KK/EN A4 portrait/landscape. Source arrays/metadata и continuous dashed ratio traces сохраняются.

`tests/test_interpretation_note_caption_profile.py` проверяет полный explanatory note над footer и ниже source traces в actual standard/OPUS PDF: caption profile 9 pt, RU/KK/EN, A4 portrait/landscape, 72/300/600 DPI. Отдельно проверяются полные localized no-data captions forced-empty cuttings/LBA. Source arrays/metadata сохраняются.

`tests/test_fluid_marker_legend_caption_layout.py` проверяет полный текст всех пяти фаз и пояснения, реальные font sizes, bounded/non-overlapping spans и glyph colours на RU/KK/EN, 72/300/600 DPI, 180/360/550 pt widths и default/9 pt caption profiles. Все non-empty phase subsets помещаются в global budget. Production многолистовые A4 portrait/landscape PDF сохраняют footer bounds, source arrays/metadata и candidate identities; invalid widths отклоняются.

Fluid marker legend использует QTextLayout для определения строк и явный point-metrics line pitch для измерения/рисования: Windows font bounding boxes не пересекаются при малом caption size. Строгие PDF span checks сохраняются. Planner-only report fixtures содержат пустой candidates contract.

`tests/test_curve_legend_caption_layout.py` covers 54 real PDF legend layouts (RU/KK/EN, 72/300/600 DPI, 100/180/300 pt widths, default/9 pt captions) and 36 production standard/OPUS A4 portrait/landscape PDFs. It checks full labels/units/scientific ranges, bounded non-overlapping spans, physical font size, first-line glyph alignment, measured reserve above notes, and unchanged source arrays/metadata. Additional regressions reject invalid widths, preserve missing-range colour indices, retain supplementary Unicode across Qt UTF-16 line breaks, and remeasure changed page-local ranges after replanning. Existing physical-DPI tests now assert shared caption size for curve legends.

`tests/test_interpretation_cover_physical_dpi.py` checks 24 cover contracts across actual 72/300/600 DPI PDFs: RU/KK/EN, standard/OPUS, A4 portrait/landscape and absent/explicit dates. Full localized titles/subtitles, document-control values, approvals and notes must survive with matching extracted physical font sizes and text bounds relative to 72 DPI. Six QPrinter PDF cases exercise the real paged printer adapter at 600 DPI; six production multipage renderer cases preserve the selected interval, manual identity, source arrays/metadata and absence of generation timestamps. This does not substitute for physical-printer acceptance.

Windows quality gate also isolates all four `test_navigation_organization.py` MainWindow scenarios into single-test processes after an observed 0xC0000005 in pyqtgraph PlotItem construction following earlier dialogs/scenes in a long shared Qt shard. Runner regressions verify every selector is preserved exactly once and excluded from regular shards; assertion/native failures still fail the gate.

`tests/test_interpretation_narrative_point_layout.py` checks 36 actual rich-text PDFs:
RU/KK/EN, 72/300/600 DPI, default/custom typography and regular/compact table cells.
Extracted physical fonts and full text must fit the measured document bounds; source
class selectors cannot defeat compact fallback. Twelve multipage QPdfWriter/QPrinter
PDF cases retain each of 120 rows exactly once, repeat headers and stay above footers
in A4 portrait/landscape at 600 DPI. A character-format regression preserves heading
links/bold/italic and body superscript/subscript. Physical printer acceptance is separate.

`tests/test_interpretation_cover_typography_profile.py` checks 36 actual covers:
RU/KK/EN, 72/300/600 DPI, A4 portrait/landscape, default/custom title/subtitle/body/caption
roles. Full control/context/approval labels and values, localized multiline title/subtitle,
notes and signature captions must survive; physical font sizes, page bounds and pairwise
span intersections are checked without weakening clipping assertions. Source report/identity
remain unchanged. Existing QPrinter cover checks now expect the shared 22-pt title in both
orientations; full production/high-DPI contracts remain in place.

Cover wrapped text uses QTextLayout for line breaks and explicit point-metrics pitch
for both measurement and drawing. This fixes Windows default/custom font bounding-box
overlap without relaxing the PDF intersection tolerance. Variable context row/pair heights
reserve complete labels/values before drawing. Five additional regressions reject invalid
widths and preserve explicit paragraph breaks plus supplementary Unicode via UTF-16 offsets.

`tests/test_gas_mixture_report_visual_profile.py` checks 36 production PDFs:
RU/KK/EN, 72/300/600 DPI, chart/text modes and default/substituted palette/typography.
Actual title/section/table point sizes, text colours, table header fills, full component
and Pixler numerical rows, page bounds, canonical brand and absent audit timestamp are
required. Full warnings are checked across page breaks after verifying and removing only
the separate lower-right Qt page-number block. A cross-page regression retains numeric
content inside the warning; all PDF spans, including page numbers, still undergo bounds checks.
Dataset arrays/metadata and immutable report audit remain unchanged. Six PNG
cases retain all five continuous component lines/colours and measure neutral text/page,
antialiased grid and frame palette blends at known positions. Forced font-adapter/print failures
preserve an existing PDF and remove temporary output after closing the writer. Existing interpretation rich-text
regressions verify the shared adapter extraction preserves inline formatting and pagination.

Windows depth-refresh MainWindow tests run individually through the existing native-process
isolation policy after a shared-shard PlotItem access violation during depth reset. Runner
contract tests require both nodes exactly once, retain all assertions and reject failed exits.

Masterlog document-control text explicitly resolves the common Unicode print-family stack,
independently of the UI default font. Regular/bold font regressions and RU/KK/EN production
PDFs after a UI-font change require complete document numbers, approvals, date and interval.

`tests/test_geology_report_output_language.py` проверяет 9 UI/output-language пар геологического диалога после save/reopen: реальные PDF/DOCX/XLSX, authored translations, Unicode, immutable snapshots, неизменные gas/calcimetry values и source arrays; также cancel/error на RU/KK/EN.

Generic DOCX row pagination is covered by three production RU/KK/EN exports in
`tests/test_report_document_export.py`: metadata/coverage/data rows use cantSplit,
only intended header rows repeat, rows have no keepNext/fixed-height chains, and
all sample text and source arrays remain unchanged. Physical Word/printer pagination
remains a separate acceptance step.

`tests/test_office_docx_heading_pagination.py` covers 15 production exports:
RU/KK/EN across geology, standard/OPUS and polished standard/OPUS. Title/Heading1
properties keep headings with content; ordinary paragraphs and table rows are not
chained together. Report snapshots, source depth and every curve array stay unchanged.
Word/printer visual review remains separate from OOXML acceptance.

`tests/test_report_annotation_workspace_availability.py` covers six RU/KK/EN
JSON/package-reopen workflows through the actual final-report annotation button
and real editor construction. Switching standard/OPUS/mixture modes, changing UI
language and clearing/restoring the dataset synchronize availability; disabled
clicks and direct guarded calls do not open the editor. All source arrays stay unchanged.

`tests/test_report_annotation_composer_history.py` covers six RU/KK/EN × JSON/package
workflows through the actual Composer button and dialog controls: 20 additions,
20 consecutive Undo, 20 Redo, another well's Cancel/commit, then save/reopen and
editor inspection in both wells. Every intermediate history state is checked;
scopes, source depth/C1 and clean state after reopened Cancel are preserved.
Run: `.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_composer_history.py`.
This acceptance does not replace large-LAS RSS, export or physical-printer review.

`tests/test_report_annotation_large_las_memory.py` imports real synthetic LAS fixtures
of 100k/1M rows and eight curves, then drives 20 adds/Undo/Redo and Cancel in the real
Qt editor. Per-case editor Python peak must stay below 4 MiB and sampled RSS growth
below 32 MiB; Windows requires an available RSS counter. Source SHA-256 and array
identities, clean state and empty history/composition after Cancel are asserted.
Import and hashing are excluded from the measured region; Composer preview, import
performance and PDF/printer acceptance remain separate. Metrics are recorded as
pytest properties and printed with `-s`.
Run: `.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider -s tests/test_report_annotation_large_las_memory.py`.

`tests/test_las_numeric_line_iteration.py` verifies LF/CRLF/CR with and without a
trailing newline, empty/comment lines, mixed endings and bounded unterminated tails.
An instrumented bytes fixture counts total find search ranges instead of elapsed
time; the old iterator fails the linear work budget for LF and CR. The new forward
scan retains exact row bytes and does not yield content from the following section.

`tests/test_report_annotation_history_shortcuts.py` sends real Qt Ctrl+Z and
Ctrl+Shift+Z events to the active report annotation editor in six RU/KK/EN ×
JSON/package scenarios. Every state of 20 Undo/Redo transitions, empty-history
no-op, commit/reopen, draft undo/redo plus Cancel, source arrays and clean state
are checked. Native text-field Ctrl+Z must undo typing without removing records.
Run: `.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_history_shortcuts.py`.

`tests/test_report_annotation_composer_output.py` covers six RU/KK/EN × JSON/package
workflows: real Composer/editor commits in two wells, save/reopen, preview painter,
signed PDF/passport and system-print prepared PDF plus actual QPrinter PDF output.
Observers call real painters and verify the exact persisted snapshot/output language.
Own Unicode notes appear in extracted PDF text; foreign-well and absent-track notes
do not. Source depth and every curve array remain unchanged; raster print pages
must contain images. Modal acceptance/file choices are scripted; physical printer
and HiDPI acceptance remain separate.
Run: `.venv\Scripts\python.exe scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_composer_output.py`.

Report checkpoint regression: `python scripts/run_tests.py -p no:cacheprovider tests/test_report_annotations.py` covers add/update/remove Redo, checkpoint rollback, and subsequent Redo/Undo. Composer, keyboard-history and large-LAS memory suites cover the existing editor contract; Apply and divergent history remain separate work.

Checkpoint branch regressions in `tests/test_report_annotations.py` cover Undo before the saved checkpoint, replacement edits, repeated Undo/Redo after rollback, foreign-domain Undo, foreign-session report commands and external composition deletion. Run with `python scripts/run_tests.py -p no:cacheprovider tests/test_report_annotations.py`.

Apply acceptance: `python scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_apply.py tests/test_report_annotations.py`. Real RU/KK/EN buttons exercise Apply, Undo across its checkpoint, replacement edits, Cancel and subsequent Undo/Redo; source arrays remain unchanged.

Retained report history: `python scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_retained_history.py`. RU/KK/EN Qt dialogs cover reopening, earlier Undo/Cancel, Apply, two-well command ownership and preserved stack identity. Existing Composer, keyboard and large-LAS tests remain required.

`tests/test_report_annotation_apply.py` includes six RU/KK/EN JSON/package production save/open scenarios after repeated Apply and Cancel, verifying annotation identity, clean state, blocked old-session history and unchanged depth/curve arrays.

Geology footer wiring: `python scripts/run_tests.py -p no:cacheprovider tests/test_geology_docx_shared_footer.py tests/test_office_docx_heading_pagination.py tests/test_report_document_control_docx_grid.py tests/test_office_shared_visual_profile.py`. RU/KK/EN production exports check shared bytes, footer relationship/content type, PAGE/NUMPAGES, reserved physical space and immutable report values.

Geology XLSX unit heading: `python scripts/run_tests.py -p no:cacheprovider tests/test_geology_xlsx_unit_heading.py tests/test_geology_report_output_language.py tests/test_office_shared_visual_profile.py`. Actual workbooks assert independent RU/KK/EN heading literals and immutable report snapshots.

Compound foundation: `python scripts/run_tests.py -p no:cacheprovider tests/test_compound_command_history.py tests/test_edit_history.py tests/test_report_annotations.py`. Tests cover 20-child ordering, single-entry Undo/Redo, execute/undo failure compensation, failed compensation, duplicate/empty/mixed-domain rejection and preserved history stacks.

Report compound removal: `python scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_compound_remove.py tests/test_report_annotations.py tests/test_compound_command_history.py`. Tests assert original ordering after Undo, one compound entry, checkpoint Redo/rollback, invalid-selection atomicity and foreign-session rejection.

Batch UI: `python scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_batch_dialog.py tests/test_report_annotation_compound_remove.py tests/test_report_annotation_apply.py tests/test_report_annotation_retained_history.py`. RU/KK/EN real buttons/list selection cover Delete, selection Cancel, single Undo/Redo and editor checkpoint rollback.

Batch persistence: `python scripts/run_tests.py -p no:cacheprovider tests/test_report_annotation_batch_reopen.py tests/test_report_annotation_batch_dialog.py tests/test_report_annotation_compound_remove.py tests/test_report_annotation_apply.py tests/test_report_annotation_retained_history.py`. Six RU/KK/EN JSON/package cases assert retained records, multiwell isolation, clean reopened state and unchanged depth/curves.

WITS workspace numeric boundary: `python scripts/run_tests.py -p no:cacheprovider tests/test_wits0_reliability.py tests/test_wits0_capture_dialog.py`. Positive/negative huge integers in follow_span/history_start/history_end must fall back without overwriting persisted payload or syncing settings.

Workspace identity: `python scripts/run_tests.py -p no:cacheprovider tests/test_wits0_reliability.py tests/test_wits0_capture_dialog.py`. Collision cases, Unicode, safe legacy keys, ambiguous payload preservation and real QSettings INI save/reopen are covered.

Workspace finite ranges: `python scripts/run_tests.py -p no:cacheprovider tests/test_wits0_reliability.py tests/test_wits0_capture_dialog.py`. NaN and both infinities in either boundary fail domain validation and return default persisted state without rewriting or syncing the corrupt payload.

Production capture reopen: `python scripts/run_tests.py -p no:cacheprovider tests/test_wits0_capture_reopen_runtime.py tests/test_wits0_acquisition.py tests/test_wits0_reliability.py tests/test_wits0_capture_dialog.py`. Six RU/KK/EN JSON/package cases exercise real dialog/runtime restoration, Live focus, saved view state and sequence continuation.
## GIS live source row range

`test_source_review_refreshes_row_range_without_substituting_removed_row`
checks RU/KK/EN source growth and shrinkage in an open reference dialog.
Successful source review exposes appended rows. A removed selected row stays
selected and unavailable; it never silently becomes a neighbouring sample.
Explicitly choosing a remaining row restores the current range. Operator
evidence and source values are preserved, with no implicit calibration.
## Signed geology PDF: invalid MD never replaces existing outputs

The 36-case `test_invalid_md_axis_preserves_pdf_and_passport` matrix covers
RU/KK/EN, new/existing targets and NaN, positive/negative infinity, text,
object and two-dimensional MD axes after selecting valid geology evidence.
It invokes the signed PDF API and requires its public export exception,
no new directory entries and byte-identical existing PDF/passport contents.
The malformed source axis and curve samples must remain unchanged.

### Конечная длина MD-интервала (25.10.2026)

`tests/test_interpretation_geology_interval_evidence.py` проверяет отказ
для конечных границ -1e308 / 1e308, переполняющих длину интервала,
в корреляции, расчёте пробелов и покрытия атрибутов. Источник сохраняется;
контроль -1e307 / 1e307 сохраняет измеренное покрытие 0.5.
Команда: `.venv\Scripts\python.exe scripts/run_tests.py tests/test_interpretation_geology_interval_evidence.py -p no:cacheprovider`.

### Тип кода стратиграфии (25.10.2026)

Регрессии `test_interpretation_geology_interval_evidence.py` отклоняют
None, boolean, число и массив вместо текстового кода без изменения записи.
Пустой код не даёт покрытия; ` C1 ` сохраняет код C1 и покрытие 5/8.
`test_interpretation_geology_evidence_signed_pdf.py` проверяет RU/KK/EN
и сохранность новых/существующих PDF и паспортов при повреждённом коде.
Запуск: `.venv\Scripts\python.exe scripts/run_tests.py tests/test_interpretation_geology_interval_evidence.py tests/test_interpretation_geology_evidence_signed_pdf.py -p no:cacheprovider`.

### Исходная кальциметрия (25.10.2026)

В `test_interpretation_geology_interval_evidence.py` проверяется каждый из
трёх карбонатных процентов: NaN/Inf, выход за 0–100, текст, boolean и массив
отклоняются без изменения записи. None, ноль и числовые значения сохраняют
семантику. Signed-PDF регрессии RU/KK/EN проверяют сохранность новых и
существующих PDF/паспортов при повреждённой кальциметрии.
Команда: `.venv\Scripts\python.exe scripts/run_tests.py tests/test_interpretation_geology_interval_evidence.py tests/test_interpretation_geology_evidence_signed_pdf.py -p no:cacheprovider`.

### PR #741: XML parser security regression (25.10.2026)

Word table resizing uses defusedxml for parsing; ElementTree remains the serializer.
`test_word_table_resize_rejects_xml_entities` requires EntitiesForbidden for an
entity declaration. Bandit B314 is fixed without suppressions. Run Bandit with
medium severity/confidence and the Word orientation/footer regression modules.
The first CI also had a native access violation during garbage collection in
`test_generic_office_control_after_reopen`; a local combined run reproduced a
native GC crash later in the Word footer tests. Its root cause is unresolved;
passing an isolated test does not close Qt #544. Match CI's PYTHONUTF8=1 when
running the generic report tests on Windows.

The 904-test shared-shard replay on c369cc7b passed locally in 406.79 seconds;
this does not resolve the native GC failure. After the responsive-layout changes,
CI 40229786296 exposed three legacy expectations. Identity regressions now require
the default portrait cover/body and its 9600-twip, three-equal-column control
table. The laptop-layout regression checks the orientation row between Word/Excel
and PDF/print actions, retaining the existing visibility checks. Run both modules:
`python scripts/run_tests.py tests/test_interpretation_report_identity.py tests/test_interpretation_report_responsive_layout.py -p no:cacheprovider`.

CI 40236145192 exposed a missing setup action in the responsive Word-orientation
test: export controls belong to the initially collapsed preview. The regression
now clicks the operator's preview toggle before checking both export layouts in
RU/KK/EN; visibility and language-change persistence assertions remain mandatory.
All six cases failed locally before this setup fix and passed after it. A broader
combined orientation/responsive run still terminated with a native exception;
the six-case success does not resolve that separate lifecycle issue (#544).

### INTERP-GEO-01: LBA text source validation

The same interval-evidence module also checks numeric LBA group/intensity fields:
boolean, text, arrays and NaN/Inf fail before snapshot creation, including outside
records. None stays missing and finite recorded values (including zero) keep their
coverage. Source records remain unchanged; scale interpretation is not modified.

`python scripts/run_tests.py tests/test_interpretation_geology_interval_evidence.py -p no:cacheprovider`
checks all eleven LBA text fields with malformed scalar/container inputs, including
records outside the selection. None and blank text remain missing; recorded text
retains its observed coverage. Every case checks unchanged source records.
## INTERP-GEO-01 — source record identifiers

`tests/test_interpretation_geology_interval_evidence.py` checks non-text and
blank source IDs across lithology, cuttings and stratigraphy, both inside and
outside the selected interval. Valid Unicode, numeric-looking and padded text
IDs remain byte-for-byte unchanged across all five evidence kinds, with the
same measured coverage. Source well, MD and C1 values must remain unchanged.

Independent Masterlog PDF column renderer defaults to bottom-to-top for six
compact geology/depth types, full-cell horizontal centered rock description;
per-column custom orientation/position must override defaults. Test
`test_masterlog_heading_unicode.py::test_default_masterlog_column_captions_and_manual_overrides`
records paint direction via Qt QPdfWriter without modifying geological data.

## INTERP-GEO-01 — unique source provenance

`tests/test_interpretation_geology_interval_evidence.py` rejects duplicate
source IDs within lithology, cuttings or stratigraphy before snapshot creation,
including a second record outside the selected interval. The six regressions
failed before the fix and preserve well contents, MD and C1 values. Existing
tests retain exact IDs across distinct categories and multiple evidence kinds
from one cuttings sample. This validation never renames or drops source records.
