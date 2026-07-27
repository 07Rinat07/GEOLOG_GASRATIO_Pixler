from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr


WITSML_1SERIES_NAMESPACE = "http://www.witsml.org/schemas/1series"


def wells_query() -> str:
    return (
        f'<wells xmlns="{WITSML_1SERIES_NAMESPACE}" version="1.4.1.1">'
        '<well uid=""><name/><field/><operator/><dTimLastChange/></well>'
        '</wells>'
    )


def wellbores_query(uid_well: str) -> str:
    return (
        f'<wellbores xmlns="{WITSML_1SERIES_NAMESPACE}" version="1.4.1.1">'
        f'<wellbore uid="" uidWell={quoteattr(uid_well)}>'
        '<nameWell/><name/><statusWellbore/><purposeWellbore/><dTimLastChange/>'
        '</wellbore></wellbores>'
    )


def logs_query(uid_well: str, uid_wellbore: str) -> str:
    return (
        f'<logs xmlns="{WITSML_1SERIES_NAMESPACE}" version="1.4.1.1">'
        f'<log uid="" uidWell={quoteattr(uid_well)} uidWellbore={quoteattr(uid_wellbore)}>'
        '<nameWell/><nameWellbore/><name/><indexType/><indexCurve/><direction/>'
        '<startIndex/><endIndex/><startDateTimeIndex/><endDateTimeIndex/>'
        '<dTimLastChange/>'
        '<logCurveInfo uid=""><mnemonic/><unit/><curveDescription/><typeLogData/>'
        '<minIndex/><maxIndex/><nullValue/></logCurveInfo>'
        '</log></logs>'
    )


def log_data_query(
    uid_well: str,
    uid_wellbore: str,
    uid_log: str,
    *,
    mnemonics: tuple[str, ...] = (),
    start_index: str | None = None,
    end_index: str | None = None,
    start_datetime_index: str | None = None,
    end_datetime_index: str | None = None,
) -> str:
    selectors: list[str] = []
    if start_index is not None:
        selectors.append(f"<startIndex>{escape(start_index)}</startIndex>")
    if end_index is not None:
        selectors.append(f"<endIndex>{escape(end_index)}</endIndex>")
    if start_datetime_index is not None:
        selectors.append(
            f"<startDateTimeIndex>{escape(start_datetime_index)}</startDateTimeIndex>"
        )
    if end_datetime_index is not None:
        selectors.append(
            f"<endDateTimeIndex>{escape(end_datetime_index)}</endDateTimeIndex>"
        )
    mnemonic_list = ",".join(item.strip() for item in mnemonics if item.strip())
    log_data = "<logData>"
    if mnemonic_list:
        log_data += f"<mnemonicList>{escape(mnemonic_list)}</mnemonicList>"
    log_data += "<unitList/><data/></logData>"
    return (
        f'<logs xmlns="{WITSML_1SERIES_NAMESPACE}" version="1.4.1.1">'
        f'<log uid={quoteattr(uid_log)} uidWell={quoteattr(uid_well)} '
        f'uidWellbore={quoteattr(uid_wellbore)}>'
        '<nameWell/><nameWellbore/><name/><indexType/><indexCurve/><direction/>'
        + "".join(selectors)
        + '<logCurveInfo uid=""><mnemonic/><unit/><curveDescription/><typeLogData/>'
        '<minIndex/><maxIndex/><nullValue/></logCurveInfo>'
        + log_data
        + '</log></logs>'
    )
