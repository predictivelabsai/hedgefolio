-- RAG schema for Hedgefolio: F13 filing documentation + future fund Q&A.
-- Uses a separate schema so the knowledge base stays decoupled from 13F data.

CREATE SCHEMA IF NOT EXISTS hedgefolio_rag;

CREATE TABLE IF NOT EXISTS hedgefolio_rag.documents (
    id           BIGSERIAL PRIMARY KEY,
    source       VARCHAR(200) NOT NULL,
    title        VARCHAR(400),
    doc_type     VARCHAR(50) NOT NULL DEFAULT 'reference',
    url          VARCHAR(500),
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source
    ON hedgefolio_rag.documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type
    ON hedgefolio_rag.documents(doc_type);

CREATE TABLE IF NOT EXISTS hedgefolio_rag.chunks (
    id           BIGSERIAL PRIMARY KEY,
    document_id  BIGINT NOT NULL REFERENCES hedgefolio_rag.documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    token_count  INTEGER,
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_document
    ON hedgefolio_rag.chunks(document_id, chunk_index);

-- Postgres full-text search: cheap + no extension requirements. Works as a
-- reliable baseline; a pgvector column can be added later if needed.
CREATE INDEX IF NOT EXISTS idx_chunks_fts
    ON hedgefolio_rag.chunks
    USING GIN (to_tsvector('english', content));
