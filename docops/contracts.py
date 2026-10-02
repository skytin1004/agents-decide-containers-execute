"""The model proposes actions; this boundary decides what may be queued."""
from dataclasses import dataclass
import hashlib
import json
import re

ALLOWED_ACTIONS = frozenset({"check_links", "check_translation_drift"})
REPOSITORY_ID = "docs-fixture-v1"
REQUEST_PATTERN = re.compile(r"docops-[a-z0-9][a-z0-9-]{0,55}\Z")


class InvalidRequest(ValueError):
    pass


class RequestConflict(ValueError):
    pass


@dataclass(frozen=True)
class WorkRequest:
    request_id: str
    repository_id: str
    actions: tuple[str, ...]
    schema_version: int = 1

    @classmethod
    def parse(cls, data: dict) -> "WorkRequest":
        fields = {"request_id", "repository_id", "actions", "schema_version"}
        if not isinstance(data, dict) or set(data) != fields:
            raise InvalidRequest("Exactly request_id, repository_id, actions and schema_version are required")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise InvalidRequest("Unsupported schema_version")
        rid = data["request_id"]
        if not isinstance(rid, str) or not REQUEST_PATTERN.fullmatch(rid):
            raise InvalidRequest("request_id must match docops-[a-z0-9-] and fit within 63 characters")
        if data["repository_id"] != REPOSITORY_ID:
            raise InvalidRequest("Only the immutable docs-fixture-v1 repository is allowed")
        actions = data["actions"]
        if not isinstance(actions, list) or len(actions) > 2:
            raise InvalidRequest("actions must be an array of zero, one or two allowed actions")
        if any(not isinstance(a, str) or a not in ALLOWED_ACTIONS for a in actions):
            raise InvalidRequest("Unknown action; shell commands and arbitrary paths are not accepted")
        if len(set(actions)) != len(actions):
            raise InvalidRequest("Duplicate actions are not accepted")
        return cls(rid, REPOSITORY_ID, tuple(sorted(actions)))

    def as_dict(self) -> dict:
        return {"schema_version": 1, "request_id": self.request_id,
                "repository_id": self.repository_id, "actions": list(self.actions)}

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()
