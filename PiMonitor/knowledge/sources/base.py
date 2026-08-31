"""Interfaces implemented by human-editable knowledge systems."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from ..models import KnowledgeDocument


class KnowledgeSourceNotConfigured(RuntimeError):
    """Raised when a knowledge source is used before credentials are configured."""


class KnowledgeSource(ABC):
    """Source-neutral contract consumed by future ingestion pipelines."""

    @abstractmethod
    def list_documents(self) -> List[KnowledgeDocument]:
        """Return all documents currently visible to this source."""

    @abstractmethod
    def get_document(self, document_id: str) -> KnowledgeDocument:
        """Return one complete document by its stable source identifier."""

    @abstractmethod
    def get_updated_documents(self, since: datetime) -> List[KnowledgeDocument]:
        """Return complete documents updated at or after ``since``."""
