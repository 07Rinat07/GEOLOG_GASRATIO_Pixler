# Типтелген operational events

Күйі: event contract 0.7.41 нұсқасында енгізілді және ағымдағы project format v20 ішінде сақталады.

Operational event — бір ұңғымаға және тереңдікке және/немесе уақытқа байланыстырылған
өзгермейтін бұрғылау немесе геологиялық бақылау. Qt-тан тәуелсіз contract project storage,
QC, mutation controller және report resolver үшін ортақ.

## Оқиға түрлері

Алты қатаң discriminator қолданылады:

| `kind` | Payload |
|---|---|
| `drilling` | activity, ROP, RPM, WOB, hookload |
| `gas` | Total Gas, methane, ethane, propane, connection gas |
| `show` | show type, intensity 1–5, fluorescence colour, description |
| `sample` | sample code/type, bottom depth, description |
| `casing` | casing type, outer diameter, shoe depth, status |
| `formation_top` | formation code/name, confidence, description |

Басқа kind payload-ы, белгісіз discriminator/field және dictionary key мен `event_id`
сәйкессіздігі қабылданбайды.

## Ортақ envelope

Әр event ішінде тұрақты `event_id`, `well_id`, `kind`, `depth_m`, `elapsed_time_s` немесе
`measured_at` anchor-лары, optional `received_at`, source, positive revision, calibration
reference, typed payload және есептелген QC flags бар. ISO-8601 timestamp timezone қамтуы тиіс
және UTC `Z` түріне canonicalize жасалады.

## QC schema v1

`OperationalEventQcEvaluator` ұңғыманың толық collection-ын детерминирленген түрде қайта
есептейді:

- `duplicate` — kind, anchors және payload бірдей;
- `out_of_order` — arrival order primary coordinate ретіне қайшы;
- `gap` — depth/time policy шегінен асқан аралық;
- `stale` — arrival delay policy шегінен асқан;
- `calibration_missing` және `calibration_expired` — calibration бақылауы.

Threshold мәндері immutable `OperationalEventQcPolicy` ішінде. Gas events үшін calibration
әдепкіде міндетті. Нәтиже JSON key ретіне тәуелді емес.

## Өзгерту шекарасы

`OperationalEventController` create, optimistic revision update, remove, well identity check,
deterministic list және әр mutation-нан кейін толық QC recalculation орындайды. UI/import adapter
`Well.operational_events` моделін тікелей өзгертпеуі тиіс.

## Project format v20 ішінде сақтау

Events `well.operational_events` ішінде event ID бойынша сақталады. `v16 → v17` migration әр
ұңғымаға бос collection қосады және datasets/interpretations деректерін өзгертпейді. Decoder
нақты payload class-ты қалпына келтіреді және бұзылған record-ты қабылдамайды.

## ReportDefinition integration

`resolve_operational_event_report()` дайын `ResolvedReportDefinition` аралығын қайта
есептемей қолданады. Depth, relative-time және datetime indexes тиісінше `depth_m`,
`elapsed_time_s` және UTC `measured_at` мәндеріне map жасалады. `DRILLING` section drilling
events-ті, `EVENTS` section барлық түрді немесе `event_kinds` filter-ін таңдайды.

Append-only growing dataset, checkpoints және deterministic replay 0.7.42 нұсқасында аяқталды.
Events сол revision/QC controller арқылы бірдей fingerprint-пен қайталанады. Келесі срез — source
journal-ды өзгертпейтін versioned lag/depth correction. [Acquisition replay](ACQUISITION_REPLAY.md).
