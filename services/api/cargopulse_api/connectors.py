"""Versioned ingestion boundary. No live credential or network capability exists."""

from dataclasses import dataclass
from typing import Protocol

from cargopulse_contracts import ScenarioSnapshot


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    mode: str
    evidence_tier: str
    enabled: bool
    ontology_version: str | None = None
    api_version: str | None = None


class IngestAdapter(Protocol):
    def describe_source(self) -> SourceDescriptor: ...
    def normalise(self, raw: dict) -> ScenarioSnapshot: ...


class SyntheticReferenceAdapter:
    def describe_source(self):
        return SourceDescriptor(
            "synthetic-reference-v1", "REFERENCE_IMPORT", "TEAM_SYNTHETIC_UNVERIFIED", True
        )

    def normalise(self, raw):
        return ScenarioSnapshot.model_validate(raw)


class OneRecordAdapter:
    """Disabled mapping skeleton, not an implementation of an authorised provider contract."""

    def describe_source(self):
        return SourceDescriptor(
            "one-record-unconfigured",
            "DISABLED_UNAUTHORISED",
            "LIVE_AUTHORISED",
            False,
            "3.3.0",
            "2.3.0",
        )

    def normalise(self, raw):
        raise PermissionError(
            "ONE Record adapter is disabled pending an authorised mapping contract"
        )

    def fetch_since(self, cursor=None):
        raise PermissionError("No live network adapter or credential is available")
