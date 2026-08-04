from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


DOCUMENTATION_TERMS = {
    "docs/ru/MUD_GAS_INTERPRETATION.md": (
        "## Как находятся перспективные интервалы",
        ("кандидатные интервалы", "Для каждого кандидата"),
    ),
    "docs/kk/MUD_GAS_INTERPRETATION.md": (
        "## Перспективалы аралықтарды іздеу",
        ("кандидат аралық", "Әр кандидатқа"),
    ),
    "docs/en/MUD_GAS_INTERPRETATION.md": (
        "## Prospective interval detection",
        ("candidate intervals", "Candidate detection"),
    ),
    "docs/ru/NORMALIZED_GAS_INTERPRETATION.md": (
        "непрерывные перспективные интервалы",
        ("кандидатные интервалы", "Кандидатный интервал"),
    ),
    "docs/kk/NORMALIZED_GAS_INTERPRETATION.md": (
        "үздіксіз перспективалы аралықтар",
        ("кандидат аралық", "Кандидат аралық"),
    ),
    "docs/en/NORMALIZED_GAS_INTERPRETATION.md": (
        "continuous prospective intervals",
        ("candidate intervals", "A candidate interval"),
    ),
    "docs/MUD_GAS_FORMULAS.md": (
        "перспективных глубинных интервалов",
        ("глубинных кандидатов", "как кандидаты"),
    ),
    "docs/CHANGELOG.md": (
        "Интерпретация перспективных интервалов",
        ("Интерпретация кандидатных интервалов",),
    ),
}


def test_mud_gas_documentation_uses_prospective_interval_terms() -> None:
    for relative_path, (expected, stale_terms) in DOCUMENTATION_TERMS.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert expected in text, relative_path
        for stale in stale_terms:
            assert stale not in text, f"{relative_path}: {stale}"
