"""Deterministic analysis input identity builder."""

from __future__ import annotations

from datetime import timezone
from hashlib import sha256
import json

from services.operation_analytics.contracts import AnalysisRevisionInput


class AnalysisRevisionBuilder:
    """Hash an already-frozen analysis context without selecting its as-of."""

    def build(self, input_data: AnalysisRevisionInput) -> str:
        payload = {
            "analysis_type": input_data.analysis_type,
            "entity_ids": sorted(input_data.entity_ids),
            "parameters": sorted(
                ([key, value] for key, value in input_data.parameters),
                key=lambda item: (item[0], item[1]),
            ),
            "analysis_as_of": input_data.analysis_as_of.astimezone(
                timezone.utc
            ).isoformat(),
            "snapshot_revision_ids": sorted(input_data.snapshot_revision_ids),
            "source_result_versions": sorted(
                ([identity, version] for identity, version in input_data.source_result_versions),
                key=lambda item: (item[0], item[1]),
            ),
            "rule_versions": sorted(input_data.rule_versions),
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{sha256(canonical).hexdigest()}"


__all__ = ["AnalysisRevisionBuilder"]
