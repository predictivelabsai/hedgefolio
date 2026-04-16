-- Activist / beneficial-ownership filings tracker.
-- Covers Schedule 13D, 13D/A (amendments), 13G and 13G/A.
-- 13D means the filer intends to influence management → classic "activist".
-- 13G means passive >5% holder.

CREATE SCHEMA IF NOT EXISTS hedgefolio;

CREATE TABLE IF NOT EXISTS hedgefolio.activist_filing (
    accession_number VARCHAR(25) PRIMARY KEY,
    form_type        VARCHAR(20) NOT NULL,     -- SC 13D, SC 13D/A, SC 13G, SC 13G/A
    is_amendment     BOOLEAN NOT NULL DEFAULT FALSE,
    is_activist      BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE for 13D variants
    filer_cik        VARCHAR(10) NOT NULL,
    filer_name       VARCHAR(250) NOT NULL,
    filing_date      DATE NOT NULL,
    subject_cik      VARCHAR(10),
    subject_name     VARCHAR(250),
    subject_ticker   VARCHAR(20),
    filing_url       VARCHAR(500),
    index_path       VARCHAR(500),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activist_filing_date
    ON hedgefolio.activist_filing (filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_activist_filing_form
    ON hedgefolio.activist_filing (form_type);
CREATE INDEX IF NOT EXISTS idx_activist_filing_filer
    ON hedgefolio.activist_filing (filer_cik);
CREATE INDEX IF NOT EXISTS idx_activist_filing_subject
    ON hedgefolio.activist_filing (subject_cik);
CREATE INDEX IF NOT EXISTS idx_activist_filing_is_activist
    ON hedgefolio.activist_filing (is_activist, filing_date DESC);
