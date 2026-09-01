from __future__ import annotations

import json
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


replace_once(
    "src/geoworkbench/project/data_inspector_controller.py",
    "@dataclass(slots=True)\nclass DataInspectorController:\n",
    '''@dataclass(frozen=True, slots=True)
class GasConditioningQcIntervalInspection:
    minimum_depth: float
    maximum_depth: float
    sample_count: int


@dataclass(frozen=True, slots=True)
class GasComponentConditioningQcInspection:
    mnemonic: str
    interpolated_sample_count: int
    max_gap: float | None
    intervals: tuple[GasConditioningQcIntervalInspection, ...]


@dataclass(frozen=True, slots=True)
class GasConditioningQcInspection:
    nominal_depth_step: float
    affected_depth_row_count: int
    interpolated_component_sample_count: int
    components: tuple[GasComponentConditioningQcInspection, ...]


@dataclass(slots=True)
class DataInspectorController:
''',
)

replace_once(
    "src/geoworkbench/project/data_inspector_controller.py",
    "    def import_issues(self) -> tuple[LasImportIssue, ...]:\n",
    '''    def gas_conditioning_qc(self) -> GasConditioningQcInspection | None:
        summary = self._dataset().gas_conditioning_qc
        if summary is None:
            return None
        return GasConditioningQcInspection(
            nominal_depth_step=summary.nominal_depth_step,
            affected_depth_row_count=summary.affected_depth_row_count,
            interpolated_component_sample_count=summary.interpolated_component_sample_count,
            components=tuple(
                GasComponentConditioningQcInspection(
                    mnemonic=component.mnemonic,
                    interpolated_sample_count=component.interpolated_sample_count,
                    max_gap=component.max_gap,
                    intervals=tuple(
                        GasConditioningQcIntervalInspection(
                            minimum_depth=interval.minimum_depth,
                            maximum_depth=interval.maximum_depth,
                            sample_count=interval.sample_count,
                        )
                        for interval in component.interpolated_intervals
                    ),
                )
                for component in summary.components
            ),
        )

    def import_issues(self) -> tuple[LasImportIssue, ...]:
''',
)

replace_once(
    "src/geoworkbench/ui/data_inspector_dialog.py",
    '''        self.tabs.addTab(curves_page, self._t("data.curves"))

        self.issue_table = QTableWidget(0, 3)
''',
    '''        self.tabs.addTab(curves_page, self._t("data.curves"))

        gas_qc_page = QWidget()
        gas_qc_layout = QVBoxLayout(gas_qc_page)
        self.gas_qc_summary = QPlainTextEdit()
        self.gas_qc_summary.setObjectName("gas-conditioning-qc-summary")
        self.gas_qc_summary.setReadOnly(True)
        self.gas_qc_summary.setMaximumHeight(120)
        gas_qc_layout.addWidget(self.gas_qc_summary)
        self.gas_qc_table = QTableWidget(0, 4)
        self.gas_qc_table.setObjectName("gas-conditioning-qc-table")
        self.gas_qc_table.setHorizontalHeaderLabels(
            [
                self._t("data.gas_qc_component"),
                self._t("data.gas_qc_restored_points"),
                self._t("data.gas_qc_max_gap"),
                self._t("data.gas_qc_ranges"),
            ]
        )
        self.gas_qc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.gas_qc_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        gas_qc_layout.addWidget(self.gas_qc_table)
        self.tabs.addTab(gas_qc_page, self._t("data.gas_qc"))

        self.issue_table = QTableWidget(0, 3)
''',
)

replace_once(
    "src/geoworkbench/ui/data_inspector_dialog.py",
    '''        self.curve_table.resizeColumnsToContents()

        issues = self.controller.import_issues()
''',
    '''        self.curve_table.resizeColumnsToContents()

        gas_qc = self.controller.gas_conditioning_qc()
        if gas_qc is None:
            self.gas_qc_summary.setPlainText(self._t("data.gas_qc_none"))
            self.gas_qc_table.setRowCount(0)
        else:
            self.gas_qc_summary.setPlainText(
                f"{self._t('data.gas_qc_nominal_step')}: "
                f"{self._number(gas_qc.nominal_depth_step)}\n"
                f"{self._t('data.gas_qc_affected_rows')}: "
                f"{gas_qc.affected_depth_row_count}\n"
                f"{self._t('data.gas_qc_restored_samples')}: "
                f"{gas_qc.interpolated_component_sample_count}"
            )
            self.gas_qc_table.setRowCount(len(gas_qc.components))
            for row, component in enumerate(gas_qc.components):
                restored_ranges = "; ".join(
                    f"{self._number(interval.minimum_depth)}–"
                    f"{self._number(interval.maximum_depth)} ({interval.sample_count})"
                    for interval in component.intervals
                )
                values = (
                    component.mnemonic,
                    str(component.interpolated_sample_count),
                    self._number(component.max_gap),
                    restored_ranges or "—",
                )
                for column, value in enumerate(values):
                    self.gas_qc_table.setItem(row, column, QTableWidgetItem(value))
            self.gas_qc_table.resizeColumnsToContents()

        issues = self.controller.import_issues()
''',
)

replace_once(
    "tests/test_data_inspector_controller.py",
    "from geoworkbench.domain.models import (\n",
    '''from geoworkbench.domain.gas_conditioning_qc import (
    GasComponentConditioningQc,
    GasConditioningQcInterval,
    GasConditioningQcSummary,
)
from geoworkbench.domain.models import (
''',
)

append_once(
    "tests/test_data_inspector_controller.py",
    "test_data_inspector_exposes_persisted_gas_conditioning_qc_without_recalculation",
    '''def test_data_inspector_exposes_persisted_gas_conditioning_qc_without_recalculation() -> None:
    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.gas_conditioning_qc = GasConditioningQcSummary(
        nominal_depth_step=1.0,
        affected_depth_row_count=2,
        interpolated_component_sample_count=2,
        components=(
            GasComponentConditioningQc(
                mnemonic="C1",
                interpolated_sample_count=2,
                interpolated_intervals=(GasConditioningQcInterval(100.0, 101.0, 2),),
                max_gap=4.0,
            ),
        ),
    )

    inspection = controller.gas_conditioning_qc()

    assert inspection is not None
    assert inspection.nominal_depth_step == 1.0
    assert inspection.affected_depth_row_count == 2
    assert inspection.interpolated_component_sample_count == 2
    assert inspection.components[0].mnemonic == "C1"
    assert inspection.components[0].interpolated_sample_count == 2
    assert inspection.components[0].max_gap == 4.0
    assert inspection.components[0].intervals[0].minimum_depth == 100.0
    assert inspection.components[0].intervals[0].maximum_depth == 101.0
    assert inspection.components[0].intervals[0].sample_count == 2
''',
)

replace_once(
    "tests/test_data_inspector_dialog.py",
    "from geoworkbench.domain.models import (\n",
    '''from geoworkbench.domain.gas_conditioning_qc import (
    GasComponentConditioningQc,
    GasConditioningQcInterval,
    GasConditioningQcSummary,
)
from geoworkbench.domain.models import (
''',
)

replace_once(
    "tests/test_data_inspector_dialog.py",
    '''        "Curves",
        "Import diagnostics",
''',
    '''        "Curves",
        "Gas conditioning QC",
        "Import diagnostics",
''',
)

append_once(
    "tests/test_data_inspector_dialog.py",
    "test_data_inspector_dialog_renders_persisted_gas_conditioning_qc",
    '''def test_data_inspector_dialog_renders_persisted_gas_conditioning_qc(qapp) -> None:
    controller = make_controller()
    dataset = controller.session.current_dataset
    assert dataset is not None
    dataset.gas_conditioning_qc = GasConditioningQcSummary(
        nominal_depth_step=1.0,
        affected_depth_row_count=2,
        interpolated_component_sample_count=2,
        components=(
            GasComponentConditioningQc(
                mnemonic="C1",
                interpolated_sample_count=2,
                interpolated_intervals=(GasConditioningQcInterval(1.0, 2.0, 2),),
                max_gap=4.0,
            ),
        ),
    )

    dialog = DataInspectorDialog(controller, language=AppLanguage.EN)
    summary = dialog.findChild(QPlainTextEdit, "gas-conditioning-qc-summary")
    table = dialog.findChild(QTableWidget, "gas-conditioning-qc-table")

    assert summary is not None
    assert "Nominal depth step: 1" in summary.toPlainText()
    assert "Affected depth rows: 2" in summary.toPlainText()
    assert "Restored component samples: 2" in summary.toPlainText()
    assert table is not None and table.rowCount() == 1
    assert table.item(0, 0).text() == "C1"
    assert table.item(0, 1).text() == "2"
    assert table.item(0, 2).text() == "4"
    assert table.item(0, 3).text() == "1–2 (2)"
    dialog.close()
''',
)

translations = {
    "en": {
        "data.gas_qc": "Gas conditioning QC",
        "data.gas_qc_none": "No saved gas-conditioning QC provenance for this dataset.",
        "data.gas_qc_nominal_step": "Nominal depth step",
        "data.gas_qc_affected_rows": "Affected depth rows",
        "data.gas_qc_restored_samples": "Restored component samples",
        "data.gas_qc_component": "Component",
        "data.gas_qc_restored_points": "Restored points",
        "data.gas_qc_max_gap": "Max interpolation gap",
        "data.gas_qc_ranges": "Restored depth ranges",
    },
    "ru": {
        "data.gas_qc": "QC кондиционирования газа",
        "data.gas_qc_none": "Для этого набора данных нет сохранённого QC кондиционирования газа.",
        "data.gas_qc_nominal_step": "Номинальный шаг глубины",
        "data.gas_qc_affected_rows": "Затронутые строки глубины",
        "data.gas_qc_restored_samples": "Восстановленные значения компонентов",
        "data.gas_qc_component": "Компонент",
        "data.gas_qc_restored_points": "Восстановленные точки",
        "data.gas_qc_max_gap": "Максимальный интервал интерполяции",
        "data.gas_qc_ranges": "Восстановленные диапазоны глубины",
    },
    "kk": {
        "data.gas_qc": "Газды кондициялау QC",
        "data.gas_qc_none": "Бұл деректер жиыны үшін газды кондициялау QC деректері сақталмаған.",
        "data.gas_qc_nominal_step": "Тереңдіктің номинал қадамы",
        "data.gas_qc_affected_rows": "Өзгерген тереңдік жолдары",
        "data.gas_qc_restored_samples": "Қалпына келтірілген компонент мәндері",
        "data.gas_qc_component": "Компонент",
        "data.gas_qc_restored_points": "Қалпына келтірілген нүктелер",
        "data.gas_qc_max_gap": "Интерполяцияның ең үлкен аралығы",
        "data.gas_qc_ranges": "Қалпына келтірілген тереңдік аралықтары",
    },
}
for language, values in translations.items():
    path = Path(f"src/geoworkbench/resources/i18n/{language}.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(values)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

replace_once(
    "docs/GAS_CONDITIONING_QC.md",
    '''## Remaining GAS-06 work

The domain, persistence and calculation-session slices are implemented. A later isolated branch must expose the persisted QC summary in the operator UI/reporting path. GAS-06 should be marked complete in the canonical project plan only after that UI slice and its acceptance tests are green and merged.
''',
    '''## Operator visibility

Data Inspector exposes the persisted summary without recalculating conditioning. The read-only QC tab shows nominal depth step, affected depth rows, total restored component samples and one row per gas component with restored-point count, effective max-gap and inclusive restored depth ranges.

Datasets without saved provenance show an explicit localized empty-state message instead of inferring historical QC from derived curves.

## Completion gate

The domain, persistence, calculation-session and operator-visibility slices are implemented. GAS-06 remains open in the canonical project plan until this UI slice and its acceptance tests pass the complete release gate and the branch is ready to merge.
''',
)

replace_once(
    "docs/PROJECT_PLAN.md",
    "- пакет `0.7.93`; project `v23`; form `v16`; tablet layout `v24`;",
    "- пакет `0.7.93`; project `v24`; form `v16`; tablet layout `v24`;",
)

replace_once(
    "docs/CHANGELOG.md",
    "## Unreleased\n\n",
    '''## Unreleased

- Data Inspector получил read-only QC кондиционирования газа: оператор видит номинальный шаг,
  число затронутых depth rows, суммарное количество восстановленных компонентных значений и
  по каждому C1–C5 каналу — число точек, фактический max-gap и сохранённые диапазоны глубин.
  Отображение читает typed `Dataset.gas_conditioning_qc` и ничего не пересчитывает; отсутствие
  исторического provenance показывается явно. Подписи синхронизированы для RU/KK/EN.
''',
)

# The patch mechanism must not survive in the feature branch tree.
for temporary in (
    Path(".github/scripts/gas06_ui_patch.py"),
    Path(".github/workflows/gas06-ui-patch.yml"),
):
    temporary.unlink(missing_ok=True)
