"""Normalized knowledge models shared by all knowledge sources."""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class KnowledgeDocument:
    """A source-neutral, complete document ready for export or normalization.

    This model deliberately contains no chunk, embedding, or vector-store fields.
    Those are derived artifacts and belong to later pipeline stages.
    """

    id: str
    title: str
    content: str
    source: str
    path: str
    url: str
    tags: Tuple[str, ...] = field(default_factory=tuple)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "path": self.path,
            "url": self.url,
        }
        for field_name, value in required.items():
            if not isinstance(value, str):
                raise TypeError("{} must be a string".format(field_name))

        if not self.id.strip():
            raise ValueError("id must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if self.created_at is not None and not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime or None")
        if self.updated_at is not None and not isinstance(self.updated_at, datetime):
            raise TypeError("updated_at must be a datetime or None")

        normalized_tags = tuple(
            str(tag).strip() for tag in self.tags if str(tag).strip()
        )
        object.__setattr__(self, "tags", normalized_tags)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation used by export tooling."""

        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "path": self.path,
            "url": self.url,
            "tags": list(self.tags),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": dict(self.metadata),
        }
