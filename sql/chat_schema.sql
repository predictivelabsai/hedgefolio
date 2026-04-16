-- Chat persistence schema for Hedgefolio AG-UI.
-- Runs inside the hedgefolio schema alongside the existing 13F tables.

CREATE SCHEMA IF NOT EXISTS hedgefolio;

CREATE TABLE IF NOT EXISTS hedgefolio.chat_conversations (
    thread_id   UUID PRIMARY KEY,
    user_id     VARCHAR(64),
    title       VARCHAR(200) DEFAULT 'New chat',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_user
    ON hedgefolio.chat_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated
    ON hedgefolio.chat_conversations(updated_at DESC);

CREATE TABLE IF NOT EXISTS hedgefolio.chat_messages (
    id          BIGSERIAL PRIMARY KEY,
    thread_id   UUID NOT NULL REFERENCES hedgefolio.chat_conversations(thread_id) ON DELETE CASCADE,
    message_id  UUID NOT NULL,
    role        VARCHAR(20) NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread
    ON hedgefolio.chat_messages(thread_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_messages_message_id
    ON hedgefolio.chat_messages(message_id);
