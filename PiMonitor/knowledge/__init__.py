"""Framework-independent knowledge-source interfaces for future RAG work."""

from .models import KnowledgeDocument
from .sources.base import KnowledgeSource, KnowledgeSourceNotConfigured

__all__ = ["KnowledgeDocument", "KnowledgeSource", "KnowledgeSourceNotConfigured"]
