# WITS / Mud-Logging Gas Event Context

## Purpose

High Total Gas alone is not proof of a hydrocarbon-bearing interval. The interpreter must separate
geological signals from operational and QC events. Gas origin/context is independent from Haworth/
Pixler fluid screening.

## Working classes

- **Background gas (BGG)** — baseline gas under stable drilling through a relatively uniform interval.
- **Formation gas show** — a robust excursion above background under suitable drilling context,
  after excluding connection/trip/test/calibration events.
- **Connection gas (CG)** — a short gas peak associated with pumps-off/pipe connection, expected
  at surface roughly one lag after the connection.
- **Trip gas (TG)** — gas accumulated during tripping/pumps-off and detected when circulation resumes.
- **Circulated/recycled gas** — gas associated with circulation or residual gas re-entering the mud loop.
- **Chromatograph test/calibration gas** — certified test gas or QC injection into the analyzer;
  never interpreted as a formation show.
- **Mud-logging gas-line test** — gas introduced to verify the sample line/extraction path;
  excluded from geological interpretation.
- **Lag tracer/carbide test** — deliberately introduced tracer used to verify lag.
- **Elevated-unclassified** — gas is elevated but the origin cannot be determined reliably.

## Automatic detection plus operator confirmation

Use a hybrid workflow. Automatic rules use pump/SPM/flow, ROP, bit depth, block position,
on/off-bottom state, drilling activity, connection/trip events, and the lag model.

The operator may also create a confirmed manual interval with event kind, depth or elapsed-time
axis, start/end, optional observed/reference value and unit, comment, and confirmed status.
Manual QC/test intervals override automatic formation-show classification.

## Lag and depth attribution

Store surface detection and lag-corrected bit depth separately. A report should retain the
surface time/depth, lag estimate, corrected bit depth, and lag source (calculated, connection marker,
tracer/carbide test, or manual correction). Without valid lag, the application must not confidently
assign surface gas to a specific drilled formation.

## References

SLB Energy Glossary (background gas, connection gas, trip gas, lag gas, carbide lag test,
recycled gas); SLB Oilfield Review *Defining Mud Logging*; GEOLOG Surface Logging specifications;
AAPG Wiki *Mudlogging: gas extraction and monitoring*.
