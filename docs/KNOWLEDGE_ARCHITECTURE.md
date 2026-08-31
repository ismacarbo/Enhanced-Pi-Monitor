# Knowledge and future RAG architecture

Wiki.js is the canonical, human-editable source of knowledge. JSONL exports, chunks, embeddings, and a future vector database are disposable derived indexes: they must be reproducible from Wiki.js and must never become the only copy of a page.

## Planned progression

1. **Wiki.js personal knowledge base** — edit, organize, tag, search, and back up source pages.
2. **Wiki.js extraction/export** — read pages through the authenticated GraphQL API and emit normalized JSONL.
3. **Document normalization** — normalize Markdown, links, dates, source metadata, and optional attachments without losing source identity.
4. **Chunking** — split documents with deterministic chunk IDs and useful heading/path context.
5. **Local embedding generation** — embed chunks on local hardware; the model and version become index metadata.
6. **Vector database** — store derived vectors and chunk metadata, with deletion/update reconciliation.
7. **Retrieval service** — filter, retrieve, rerank, and cite source documents.
8. **Local LLM personal assistant** — build grounded prompts for a local model running on the RTX 2070.

```text
Wiki.js (canonical source)
        |
        v
KnowledgeSource
        |
        v
Normalizer
        |
        v
Chunker
        |
        v
Embedding Model
        |
        v
Vector Store (derived index)
        |
        v
Retriever
        |
        v
Context Builder
        |
        v
Local LLM
        |
        v
Personal Assistant
```

No chunker, embedding model, vector store, agent, or chat endpoint is part of the current implementation.

## Current source boundary

`PiMonitor/knowledge/sources/base.py` defines the contract:

- `list_documents()` returns complete readable documents.
- `get_document(id)` retrieves one document by stable source ID.
- `get_updated_documents(since)` supports future incremental indexing.

`PiMonitor/knowledge/models.py` defines `KnowledgeDocument` with:

- stable ID, title, source content, and source name;
- canonical page path and URL;
- native source tags;
- creation/update timestamps;
- source-specific metadata that remains JSON-serializable.

`PiMonitor/knowledge/sources/wikijs.py` is the first implementation. It uses Wiki.js 2.x GraphQL `pages.list` for metadata and `pages.single` for source content. IDs are namespaced as `wikijs:<page-id>` so later sources cannot collide. The API adapter knows nothing about a future embedding or vector-store library.

## Export contract

`scripts/export_wiki_knowledge.py` emits UTF-8 JSONL with one complete document per line:

```json
{"id":"wikijs:42","title":"ARES Overview","content":"# ARES","source":"wikijs","path":"Projects/ARES/Overview","url":"https://wiki.example.invalid/Projects/ARES/Overview","tags":["project:ares"],"created_at":"2026-08-01T10:00:00+00:00","updated_at":"2026-08-29T11:30:00+00:00","metadata":{"wikijs_page_id":42,"locale":"en","description":"Robot documentation","content_type":"markdown"}}
```

The export intentionally keeps raw Markdown. A later normalizer should preserve headings, code blocks, links, and provenance. Chunk IDs should be deterministic from the source ID, source revision/update time, and chunking algorithm version.

Incremental exports use `updatedAt`. A production ingestion service must also reconcile deletions: compare the complete current ID set with indexed source IDs and remove derived chunks whose source page no longer exists.

## Future component boundaries

Keep each later stage replaceable:

- normalizers consume `KnowledgeDocument` and produce normalized documents;
- chunkers consume normalized documents and emit chunks with source provenance;
- embedding providers accept plain text batches and record model/version metadata;
- vector stores implement storage/search without becoming a source of truth;
- retrieval returns source URLs, page IDs, timestamps, paths, tags, and relevant text;
- context building enforces token limits and citation formatting independently of the LLM runtime.

This allows a local embedding model or vector database to change without rewriting the Wiki.js client or losing knowledge.

## Security and operations

- Use a dedicated, read-oriented Wiki.js API key for extraction.
- Keep the key only in the backend/export process environment.
- Never include the key in templates, JavaScript, exported metadata, logs, or Git.
- Back up PostgreSQL independently of any vector index.
- Treat generated exports as sensitive if the Wiki contains private material.
- Rebuild the derived index after changing normalizers, chunkers, or embedding models.
