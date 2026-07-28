from __future__ import annotations

from geoworkbench.domain.acquisition import AcquisitionSession, AcquisitionSessionState
from geoworkbench.domain.models import Well
from geoworkbench.services.wits0_import_review import (
    Wits0ChannelKey,
    Wits0CustomProfile,
    Wits0ImportChannelReview,
    Wits0ImportReview,
    Wits0ImportReviewCommit,
    Wits0IndexCandidate,
    acquisition_schema_digest,
)


def open_wits0_sessions(well: Well) -> tuple[AcquisitionSession, ...]:
    sessions = [
        session
        for session in well.acquisition_sessions.values()
        if session.state is AcquisitionSessionState.OPEN
        and any(
            curve.metadata.provenance.startswith("wits0:")
            for curve in session.dataset_schema.curves
        )
    ]
    return tuple(sorted(sessions, key=lambda item: item.session_id))


def restore_wits0_import_review_commit(
    session: AcquisitionSession,
    custom_profile: Wits0CustomProfile,
) -> Wits0ImportReviewCommit:
    """Rebuild the immutable normalizer contract from persisted schema + mapping profile.

    Discovery sample statistics are deliberately not reconstructed.  They are not required by
    normalization and would be misleading after a process restart.  The persisted immutable
    schema and versioned custom profile remain the authoritative recovery inputs.
    """

    if session.state is not AcquisitionSessionState.OPEN:
        raise ValueError("Only an open WITS0 acquisition session can be recovered")
    schema = session.dataset_schema
    index = next(item for item in schema.indexes if item.index_id == schema.active_index_id)
    source_kind = (
        "header_datetime"
        if custom_profile.index_candidate_id == "header:datetime"
        else "field"
    )
    channel_key = None
    if source_kind == "field":
        prefix = "field:"
        if not custom_profile.index_candidate_id.startswith(prefix):
            raise ValueError("Custom WITS0 profile contains an invalid field index candidate")
        channel_key = Wits0ChannelKey.parse(
            custom_profile.index_candidate_id.removeprefix(prefix)
        )
    selected_index = Wits0IndexCandidate(
        candidate_id=custom_profile.index_candidate_id,
        source_kind=source_kind,
        mnemonic=custom_profile.index_mnemonic,
        role=index.role,
        index_type=index.index_type,
        source_uom=(
            next(
                (
                    item.source_uom
                    for item in custom_profile.channels
                    if item.key == channel_key
                ),
                None,
            )
            if channel_key is not None
            else None
        ),
        canonical_uom=index.unit,
        confidence=index.confidence,
        observation_count=0,
        evidence=("Recovered from persisted AcquisitionDatasetSchema",),
        channel_key=channel_key,
    )
    curve_by_source = {
        curve.metadata.provenance.removeprefix("wits0:"): curve
        for curve in schema.curves
        if curve.metadata.provenance.startswith("wits0:")
    }
    channel_reviews: list[Wits0ImportChannelReview] = []
    enabled_sources: set[str] = set()
    for mapping in custom_profile.channels:
        source_id = mapping.key.source_id
        curve = curve_by_source.get(source_id)
        import_enabled = mapping.import_enabled and mapping.key != channel_key
        if import_enabled:
            if curve is None:
                raise ValueError(
                    f"Persisted WITS0 schema is missing enabled channel {source_id}"
                )
            enabled_sources.add(source_id)
        channel_reviews.append(
            Wits0ImportChannelReview(
                key=mapping.key,
                source_mnemonic=mapping.canonical_mnemonic,
                source_name=(
                    curve.metadata.description
                    if curve is not None and curve.metadata.description
                    else mapping.canonical_mnemonic
                ),
                value_kind="float",
                import_enabled=import_enabled,
                canonical_mnemonic=mapping.canonical_mnemonic,
                canonical_kind=mapping.canonical_kind,
                quantity_class=mapping.quantity_class,
                source_uom=mapping.source_uom,
                canonical_uom=mapping.canonical_uom,
                confidence=1.0,
                observed_count=0,
                valid_count=0,
                null_count=0,
                samples=(),
                issues=(),
            )
        )
    unknown_schema_sources = set(curve_by_source).difference(enabled_sources)
    if unknown_schema_sources:
        raise ValueError(
            "Persisted WITS0 schema contains channels absent from the custom profile: "
            + ", ".join(sorted(unknown_schema_sources))
        )
    review = Wits0ImportReview(
        discovery_fingerprint=custom_profile.discovery_fingerprint,
        selected_index=selected_index,
        index_candidates=(selected_index,),
        channels=tuple(channel_reviews),
        issues=(),
        schema_preview=schema,
    )
    return Wits0ImportReviewCommit(
        review=review,
        schema=schema,
        custom_profile=custom_profile,
        schema_digest=acquisition_schema_digest(schema),
    )
