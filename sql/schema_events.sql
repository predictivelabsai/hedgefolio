-- Form 13D/13G SEC Events Database Schema
-- Schema: hedgefolio
-- Purpose: Store activist and passive stake accumulation events

-- ============================================================
-- SEC_EVENT TABLE
-- Core 13D/13G event data
-- ============================================================
CREATE TABLE IF NOT EXISTS hedgefolio.sec_event (
    event_id SERIAL PRIMARY KEY,
    accession_number VARCHAR(25) UNIQUE NOT NULL,
    filing_date DATE NOT NULL,
    form_type VARCHAR(10) NOT NULL,
    cik VARCHAR(10) NOT NULL,
    filer_name VARCHAR(200) NOT NULL,
    filer_address TEXT,
    target_cik VARCHAR(10),
    target_company_name VARCHAR(200) NOT NULL,
    target_ticker VARCHAR(20),
    stake_percentage NUMERIC(5,2),
    shares_owned BIGINT,
    shares_outstanding BIGINT,
    filing_status VARCHAR(20),
    amendment_number INTEGER,
    is_amendment BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sec_event_filing_date ON hedgefolio.sec_event(filing_date);
CREATE INDEX IF NOT EXISTS idx_sec_event_form_type ON hedgefolio.sec_event(form_type);
CREATE INDEX IF NOT EXISTS idx_sec_event_filer_name ON hedgefolio.sec_event(filer_name);
CREATE INDEX IF NOT EXISTS idx_sec_event_target_company ON hedgefolio.sec_event(target_company_name);
CREATE INDEX IF NOT EXISTS idx_sec_event_target_ticker ON hedgefolio.sec_event(target_ticker);
CREATE INDEX IF NOT EXISTS idx_sec_event_filing_date_form_type ON hedgefolio.sec_event(filing_date DESC, form_type);

-- ============================================================
-- SEC_EVENT_INTENT TABLE
-- 13D activist intent and strategy
-- ============================================================
CREATE TABLE IF NOT EXISTS hedgefolio.sec_event_intent (
    intent_id SERIAL PRIMARY KEY,
    accession_number VARCHAR(25) NOT NULL UNIQUE REFERENCES hedgefolio.sec_event(accession_number) ON DELETE CASCADE,
    intent_type VARCHAR(50),
    purpose_description TEXT,
    plans_or_proposals TEXT,
    background_of_filer TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sec_event_intent_accession ON hedgefolio.sec_event_intent(accession_number);

-- ============================================================
-- SEC_EVENT_AMENDMENT TABLE
-- Amendment history for 13D/13G filings
-- ============================================================
CREATE TABLE IF NOT EXISTS hedgefolio.sec_event_amendment (
    amendment_id SERIAL PRIMARY KEY,
    parent_accession_number VARCHAR(25) NOT NULL REFERENCES hedgefolio.sec_event(accession_number) ON DELETE CASCADE,
    amendment_accession_number VARCHAR(25) NOT NULL UNIQUE,
    amendment_date DATE NOT NULL,
    amendment_number INTEGER,
    amendment_description TEXT,
    previous_stake_percentage NUMERIC(5,2),
    new_stake_percentage NUMERIC(5,2),
    previous_shares BIGINT,
    new_shares BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sec_event_amendment_parent ON hedgefolio.sec_event_amendment(parent_accession_number);
CREATE INDEX IF NOT EXISTS idx_sec_event_amendment_date ON hedgefolio.sec_event_amendment(amendment_date);
CREATE INDEX IF NOT EXISTS idx_sec_event_amendment_parent_date ON hedgefolio.sec_event_amendment(parent_accession_number, amendment_date);

-- ============================================================
-- SEC_EVENT_GROUP_MEMBER TABLE
-- Group members for group 13D/13G filings
-- ============================================================
CREATE TABLE IF NOT EXISTS hedgefolio.sec_event_group_member (
    member_id SERIAL PRIMARY KEY,
    accession_number VARCHAR(25) NOT NULL REFERENCES hedgefolio.sec_event(accession_number) ON DELETE CASCADE,
    member_name VARCHAR(200) NOT NULL,
    member_cik VARCHAR(10),
    member_address TEXT,
    member_relationship VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sec_event_group_member_accession ON hedgefolio.sec_event_group_member(accession_number);

-- ============================================================
-- VIEWS
-- ============================================================

-- View: Recent activist campaigns with intent
CREATE OR REPLACE VIEW hedgefolio.v_recent_activist_campaigns AS
SELECT 
    se.event_id,
    se.accession_number,
    se.filing_date,
    se.filer_name,
    se.target_company_name,
    se.target_ticker,
    se.stake_percentage,
    se.shares_owned,
    sei.intent_type,
    sei.purpose_description,
    sei.plans_or_proposals
FROM hedgefolio.sec_event se
LEFT JOIN hedgefolio.sec_event_intent sei ON se.accession_number = sei.accession_number
WHERE se.form_type = '13D'
ORDER BY se.filing_date DESC;

-- View: Stake accumulation timeline
CREATE OR REPLACE VIEW hedgefolio.v_stake_timeline AS
SELECT 
    se.accession_number,
    se.filing_date,
    se.filer_name,
    se.target_company_name,
    se.stake_percentage,
    se.shares_owned,
    'Initial' AS event_type
FROM hedgefolio.sec_event se
WHERE se.is_amendment = FALSE
UNION ALL
SELECT 
    sea.amendment_accession_number,
    sea.amendment_date,
    se.filer_name,
    se.target_company_name,
    sea.new_stake_percentage,
    sea.new_shares,
    'Amendment' AS event_type
FROM hedgefolio.sec_event_amendment sea
JOIN hedgefolio.sec_event se ON sea.parent_accession_number = se.accession_number
ORDER BY filing_date DESC;

-- View: Top activist filers by activity
CREATE OR REPLACE VIEW hedgefolio.v_top_activist_filers AS
SELECT 
    filer_name,
    COUNT(*) as total_filings,
    COUNT(DISTINCT target_company_name) as unique_targets,
    AVG(stake_percentage) as avg_stake,
    MAX(filing_date) as latest_filing
FROM hedgefolio.sec_event
WHERE form_type = '13D'
GROUP BY filer_name
ORDER BY total_filings DESC;
