-- Form 13F SEC Filings Database Schema
-- Schema: hedgefolio

-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS infotable CASCADE;
DROP TABLE IF EXISTS othermanager2 CASCADE;
DROP TABLE IF EXISTS othermanager CASCADE;
DROP TABLE IF EXISTS signature CASCADE;
DROP TABLE IF EXISTS summarypage CASCADE;
DROP TABLE IF EXISTS coverpage CASCADE;
DROP TABLE IF EXISTS submission CASCADE;
DROP TABLE IF EXISTS company_ticker CASCADE;

-- ============================================================
-- SUBMISSION TABLE
-- Core submission info for each 13F filing
-- ============================================================
CREATE TABLE submission (
    accession_number VARCHAR(25) PRIMARY KEY,
    filing_date DATE NOT NULL,
    submission_type VARCHAR(10) NOT NULL,
    cik VARCHAR(10) NOT NULL,
    period_of_report DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_submission_cik ON submission(cik);
CREATE INDEX idx_submission_filing_date ON submission(filing_date);
CREATE INDEX idx_submission_period_of_report ON submission(period_of_report);

-- ============================================================
-- COVERPAGE TABLE
-- Cover page details including filing manager info
-- ============================================================
CREATE TABLE coverpage (
    accession_number VARCHAR(25) PRIMARY KEY REFERENCES submission(accession_number) ON DELETE CASCADE,
    report_calendar_or_quarter DATE NOT NULL,
    is_amendment VARCHAR(1),
    amendment_no INTEGER,
    amendment_type VARCHAR(20),
    conf_denied_expired VARCHAR(1),
    date_denied_expired DATE,
    date_reported DATE,
    reason_for_nonconfidentiality VARCHAR(40),
    filingmanager_name VARCHAR(150) NOT NULL,
    filingmanager_street1 VARCHAR(40),
    filingmanager_street2 VARCHAR(40),
    filingmanager_city VARCHAR(30),
    filingmanager_stateorcountry VARCHAR(2),
    filingmanager_zipcode VARCHAR(10),
    report_type VARCHAR(30) NOT NULL,
    form13f_filenumber VARCHAR(17),
    crd_number VARCHAR(9),
    sec_filenumber VARCHAR(17),
    provide_info_for_instruction5 VARCHAR(1) NOT NULL,
    additional_information TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_coverpage_filingmanager_name ON coverpage(filingmanager_name);
CREATE INDEX idx_coverpage_report_calendar ON coverpage(report_calendar_or_quarter);

-- ============================================================
-- SUMMARYPAGE TABLE
-- Summary statistics for each filing
-- ============================================================
CREATE TABLE summarypage (
    accession_number VARCHAR(25) PRIMARY KEY REFERENCES submission(accession_number) ON DELETE CASCADE,
    other_included_managers_count INTEGER,
    table_entry_total INTEGER,
    table_value_total BIGINT,
    is_confidential_omitted VARCHAR(1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_summarypage_table_value_total ON summarypage(table_value_total);

-- ============================================================
-- SIGNATURE TABLE
-- Signatory information for each filing
-- ============================================================
CREATE TABLE signature (
    accession_number VARCHAR(25) PRIMARY KEY REFERENCES submission(accession_number) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    title VARCHAR(60) NOT NULL,
    phone VARCHAR(20),
    signature VARCHAR(150) NOT NULL,
    city VARCHAR(30) NOT NULL,
    stateorcountry VARCHAR(2) NOT NULL,
    signature_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- OTHERMANAGER TABLE
-- Other managers included in the filing (from OTHERMANAGER.tsv)
-- ============================================================
CREATE TABLE othermanager (
    accession_number VARCHAR(25) NOT NULL REFERENCES submission(accession_number) ON DELETE CASCADE,
    othermanager_sk BIGINT NOT NULL,
    cik VARCHAR(10),
    form13f_filenumber VARCHAR(17),
    crd_number VARCHAR(9),
    sec_filenumber VARCHAR(17),
    name VARCHAR(150) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (accession_number, othermanager_sk)
);

CREATE INDEX idx_othermanager_cik ON othermanager(cik);
CREATE INDEX idx_othermanager_name ON othermanager(name);

-- ============================================================
-- OTHERMANAGER2 TABLE
-- Additional other managers with sequence numbers (from OTHERMANAGER2.tsv)
-- ============================================================
CREATE TABLE othermanager2 (
    accession_number VARCHAR(25) NOT NULL REFERENCES submission(accession_number) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    cik VARCHAR(10),
    form13f_filenumber VARCHAR(17),
    crd_number VARCHAR(9),
    sec_filenumber VARCHAR(17),
    name VARCHAR(150) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (accession_number, sequence_number)
);

CREATE INDEX idx_othermanager2_cik ON othermanager2(cik);
CREATE INDEX idx_othermanager2_name ON othermanager2(name);

-- ============================================================
-- INFOTABLE TABLE
-- Holdings data - the main data table with securities positions
-- ============================================================
CREATE TABLE infotable (
    accession_number VARCHAR(25) NOT NULL REFERENCES submission(accession_number) ON DELETE CASCADE,
    infotable_sk BIGINT NOT NULL,
    name_of_issuer VARCHAR(200) NOT NULL,
    title_of_class VARCHAR(150) NOT NULL,
    cusip VARCHAR(9) NOT NULL,
    figi VARCHAR(12),
    value BIGINT NOT NULL,
    ssh_prn_amt BIGINT NOT NULL,
    ssh_prn_amt_type VARCHAR(10) NOT NULL,
    put_call VARCHAR(10),
    investment_discretion VARCHAR(10) NOT NULL,
    other_manager VARCHAR(100),
    voting_auth_sole BIGINT NOT NULL,
    voting_auth_shared BIGINT NOT NULL,
    voting_auth_none BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (accession_number, infotable_sk)
);

CREATE INDEX idx_infotable_cusip ON infotable(cusip);
CREATE INDEX idx_infotable_name_of_issuer ON infotable(name_of_issuer);
CREATE INDEX idx_infotable_value ON infotable(value);
CREATE INDEX idx_infotable_accession ON infotable(accession_number);

-- ============================================================
-- COMPANY_TICKER TABLE
-- Mapping of company names to ticker symbols
-- ============================================================
CREATE TABLE company_ticker (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    sector VARCHAR(100),
    source VARCHAR(50),
    last_updated DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_company_ticker_name_ticker ON company_ticker(company_name, ticker);
CREATE INDEX idx_company_ticker_ticker ON company_ticker(ticker);
CREATE INDEX idx_company_ticker_sector ON company_ticker(sector);

-- ============================================================
-- USERS TABLE
-- Email subscribers for notifications
-- ============================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    subscription_status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription_status ON users(subscription_status);

-- ============================================================
-- VIEWS
-- ============================================================

-- View: Complete filing information with manager details
CREATE OR REPLACE VIEW v_filing_summary AS
SELECT 
    s.accession_number,
    s.filing_date,
    s.submission_type,
    s.cik,
    s.period_of_report,
    c.filingmanager_name,
    c.filingmanager_city,
    c.filingmanager_stateorcountry,
    c.report_type,
    c.is_amendment,
    c.amendment_no,
    sp.table_entry_total,
    sp.table_value_total,
    sp.other_included_managers_count
FROM submission s
JOIN coverpage c ON s.accession_number = c.accession_number
LEFT JOIN summarypage sp ON s.accession_number = sp.accession_number;

-- View: Holdings with company ticker information
CREATE OR REPLACE VIEW v_holdings_with_ticker AS
SELECT 
    i.accession_number,
    s.filing_date,
    s.period_of_report,
    c.filingmanager_name,
    i.name_of_issuer,
    i.title_of_class,
    i.cusip,
    ct.ticker,
    ct.sector,
    i.value,
    i.ssh_prn_amt,
    i.ssh_prn_amt_type,
    i.put_call,
    i.investment_discretion,
    i.voting_auth_sole,
    i.voting_auth_shared,
    i.voting_auth_none
FROM infotable i
JOIN submission s ON i.accession_number = s.accession_number
JOIN coverpage c ON i.accession_number = c.accession_number
LEFT JOIN company_ticker ct ON UPPER(i.name_of_issuer) = UPPER(ct.company_name);

-- View: Top holdings by value per filing
CREATE OR REPLACE VIEW v_top_holdings AS
SELECT 
    i.accession_number,
    c.filingmanager_name,
    i.name_of_issuer,
    i.cusip,
    i.value,
    i.ssh_prn_amt,
    RANK() OVER (PARTITION BY i.accession_number ORDER BY i.value DESC) as value_rank
FROM infotable i
JOIN coverpage c ON i.accession_number = c.accession_number;

