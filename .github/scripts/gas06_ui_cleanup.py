from __future__ import annotations

import json
import subprocess
from pathlib import Path

BASE_SHA = "48fa9d21db89323c28adf9f6c750e15fb0cadca8"


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} match, found {count}")
    return text.replace(old, new, 1)


# Repair literal line breaks accidentally materialized inside two f-strings.
dialog_path = Path("src/geoworkbench/ui/data_inspector_dialog.py")
dialog = dialog_path.read_text(encoding="utf-8")
for expression in (
    "self._number(gas_qc.nominal_depth_step)",
    "gas_qc.affected_depth_row_count",
):
    broken = f'f"{{{expression}}}' + chr(10) + '"'
    repaired = rf'f"{{{expression}}}\n"'
    dialog = replace_once(dialog, broken, repaired, label=expression)
dialog_path.write_text(dialog, encoding="utf-8")

translations = {
    "en": {
        "data.gas_qc": "Gas conditioning QC",
        "data.gas_qc_affected_rows": "Affected depth rows",
        "data.gas_qc_component": "Component",
        "data.gas_qc_max_gap": "Max interpolation gap",
        "data.gas_qc_nominal_step": "Nominal depth step",
        "data.gas_qc_none": "No saved gas-conditioning QC provenance for this dataset.",
        "data.gas_qc_ranges": "Restored depth ranges",
        "data.gas_qc_restored_points": "Restored points",
        "data.gas_qc_restored_samples": "Restored component samples",
    },
    "ru": {
        "data.gas_qc": "QC кондиционирования газа",
        "data.gas_qc_affected_rows": "Затронутые строки глубины",
        "data.gas_qc_component": "Компонент",
        "data.gas_qc_max_gap": "Максимальный интервал интерполяции",
        "data.gas_qc_nominal_step": "Номинальный шаг глубины",
        "data.gas_qc_none": "Для этого набора данных нет сохранённого QC кондиционирования газа.",
        "data.gas_qc_ranges": "Восстановленные диапазоны глубины",
        "data.gas_qc_restored_points": "Восстановленные точки",
        "data.gas_qc_restored_samples": "Восстановленные значения компонентов",
    },
    "kk": {
        "data.gas_qc": "Газды кондициялау QC",
        "data.gas_qc_affected_rows": "Өзгерген тереңдік жолдары",
        "data.gas_qc_component": "Компонент",
        "data.gas_qc_max_gap": "Интерполяцияның ең үлкен аралығы",
        "data.gas_qc_nominal_step": "Тереңдіктің номинал қадамы",
        "data.gas_qc_none": "Бұл деректер жиыны үшін газды кондициялау QC деректері сақталмаған.",
        "data.gas_qc_ranges": "Қалпына келтірілген тереңдік аралықтары",
        "data.gas_qc_restored_points": "Қалпына келтірілген нүктелер",
        "data.gas_qc_restored_samples": "Қалпына келтірілген компонент мәндері",
    },
}

for language, values in translations.items():
    path = f"src/geoworkbench/resources/i18n/{language}.json"
    base = subprocess.check_output(
        ["git", "show", f"{BASE_SHA}:{path}"],
        text=True,
        encoding="utf-8",
    )
    anchor = '  "data.evidence_warnings": '
    lines = base.splitlines(keepends=True)
    insertion_index = next(
        index + 1 for index, line in enumerate(lines) if line.startswith(anchor)
    )
    addition = "".join(
        f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},\n"
        for key, value in values.items()
    )
    lines.insert(insertion_index, addition)
    updated = "".join(lines)
    parsed = json.loads(updated)
    for key, expected in values.items():
        if parsed.get(key) != expected:
            raise RuntimeError(f"Localization mismatch: {language}:{key}")
    Path(path).write_text(updated, encoding="utf-8")

for temporary in (
    Path(".github/scripts/gas06_ui_cleanup.py"),
    Path(".github/workflows/gas06-ui-cleanup.yml"),
):
    temporary.unlink(missing_ok=True)
