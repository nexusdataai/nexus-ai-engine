"""Versioned in-memory store for Journey DSL definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml

from nexus_ai_engine.contracts.journey_dsl import JourneyDefinition


class JourneyVersionConflictError(ValueError):
    """Raised when mutating a published journey version."""


@dataclass
class JourneyVersionRecord:
    definition: JourneyDefinition
    published: bool
    created_at: datetime


@dataclass
class DslJourneyStore:
    """In-memory journey DSL repository with monotonic versioning."""

    _versions: dict[str, dict[int, JourneyVersionRecord]] = field(default_factory=dict)
    _latest: dict[str, int] = field(default_factory=dict)

    def create(
        self,
        definition: JourneyDefinition,
        *,
        publish: bool = True,
    ) -> JourneyDefinition:
        journey_id = definition.metadata.id
        version = definition.metadata.version
        bucket = self._versions.setdefault(journey_id, {})

        if version in bucket and bucket[version].published:
            raise JourneyVersionConflictError(
                f"journey {journey_id} version {version} is immutable"
            )

        now = datetime.now(timezone.utc)
        bucket[version] = JourneyVersionRecord(
            definition=definition,
            published=publish,
            created_at=now,
        )
        self._latest[journey_id] = max(self._latest.get(journey_id, 0), version)
        return definition

    def get(self, journey_id: str, version: int | None = None) -> JourneyDefinition | None:
        bucket = self._versions.get(journey_id)
        if not bucket:
            return None
        ver = version if version is not None else self._latest.get(journey_id)
        if ver is None:
            return None
        rec = bucket.get(ver)
        return rec.definition if rec else None

    def list_journey_ids(self) -> list[str]:
        return sorted(self._versions.keys())

    def list_versions(self, journey_id: str) -> list[int]:
        bucket = self._versions.get(journey_id, {})
        return sorted(bucket.keys())

    def list_all(self) -> list[JourneyDefinition]:
        out: list[JourneyDefinition] = []
        for jid in self.list_journey_ids():
            latest = self.get(jid)
            if latest:
                out.append(latest)
        return out

    def delete(self, journey_id: str) -> bool:
        if journey_id not in self._versions:
            return False
        del self._versions[journey_id]
        self._latest.pop(journey_id, None)
        return True

    def export_yaml(self, journey_id: str, version: int | None = None) -> str:
        definition = self.get(journey_id, version)
        if not definition:
            raise KeyError(journey_id)
        payload = definition.model_dump(by_alias=True, mode="json")
        return yaml.safe_dump(payload, sort_keys=False)

    def clone(self, journey_id: str, *, new_id: str, new_version: int = 1) -> JourneyDefinition:
        source = self.get(journey_id)
        if not source:
            raise KeyError(journey_id)
        data = source.model_dump(by_alias=True)
        data["metadata"]["id"] = new_id
        data["metadata"]["version"] = new_version
        clone_def = JourneyDefinition.model_validate(data)
        return self.create(clone_def)
