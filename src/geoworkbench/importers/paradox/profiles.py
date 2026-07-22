from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from .models import (
    ChannelMapping,
    DatasetClassification,
    DuplicateDepthPolicy,
    ParadoxImportPlan,
    ParadoxTable,
)


@dataclass(frozen=True, slots=True)
class ImportProfile:
    name: str
    schema_signature: str
    plan: ParadoxImportPlan


def schema_signature(table: ParadoxTable) -> str:
    payload = "\n".join(
        f"{field.ordinal}|{field.name}|{field.type_code}|{field.size}" for field in table.fields
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def save_profile(profile: ImportProfile, target: str | Path) -> Path:
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    plan = profile.plan
    payload = {
        "version": 1,
        "name": profile.name,
        "schema_signature": profile.schema_signature,
        "plan": {
            "classification": plan.classification.value,
            "depth_field": plan.depth_field,
            "time_field": plan.time_field,
            "active_role": plan.active_role,
            "null_value": plan.null_value,
            "sort_by_index": plan.sort_by_index,
            "profile_name": plan.profile_name,
            "duplicate_depth_policy": plan.duplicate_depth_policy.value,
            "drop_empty_channels": plan.drop_empty_channels,
            "language": plan.language,
            "mappings": [asdict(mapping) for mapping in plan.mappings],
        },
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_profile(path: str | Path) -> ImportProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_plan = payload["plan"]
    plan = ParadoxImportPlan(
        classification=DatasetClassification(raw_plan["classification"]),
        depth_field=raw_plan.get("depth_field"),
        time_field=raw_plan.get("time_field"),
        active_role=raw_plan.get("active_role", "auto"),
        null_value=float(raw_plan.get("null_value", -999.25)),
        sort_by_index=bool(raw_plan.get("sort_by_index", False)),
        profile_name=raw_plan.get("profile_name"),
        mappings=tuple(ChannelMapping(**item) for item in raw_plan.get("mappings", [])),
        duplicate_depth_policy=DuplicateDepthPolicy(
            raw_plan.get("duplicate_depth_policy", DuplicateDepthPolicy.KEEP_ALL.value)
        ),
        drop_empty_channels=bool(raw_plan.get("drop_empty_channels", False)),
        language=str(raw_plan.get("language", "ru")),
    )
    return ImportProfile(str(payload["name"]), str(payload["schema_signature"]), plan)
