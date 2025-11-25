-- Farm Assist Database Schema
-- PostgreSQL initialization script

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Raw scraped data
CREATE TABLE IF NOT EXISTS raw_pages (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    domain VARCHAR(100),
    scrape_timestamp TIMESTAMP DEFAULT NOW(),
    status_code INTEGER,
    page_title TEXT,
    raw_html TEXT,
    raw_text TEXT,
    links JSONB,  -- All outbound links found
    metadata JSONB  -- Headers, load time, etc.
);

CREATE INDEX idx_raw_pages_domain ON raw_pages(domain);
CREATE INDEX idx_raw_pages_scrape_timestamp ON raw_pages(scrape_timestamp);

-- Extracted program data
CREATE TABLE IF NOT EXISTS programs (
    id SERIAL PRIMARY KEY,
    program_code VARCHAR(50),
    program_name VARCHAR(200),
    source_url TEXT,
    last_updated TIMESTAMP DEFAULT NOW(),

    -- Structured fields (extracted via NLP/patterns)
    description TEXT,
    eligibility_raw TEXT,  -- Full eligibility text
    eligibility_parsed JSONB,  -- Structured rules

    -- Payment information
    payment_info_raw TEXT,
    payment_formula TEXT,
    payment_range_text VARCHAR(200),
    payment_min DECIMAL(12,2),
    payment_max DECIMAL(12,2),
    payment_unit VARCHAR(50),

    -- Important dates
    application_start DATE,
    application_end DATE,
    deadline_text TEXT,  -- Original deadline description

    -- Data quality
    confidence_score FLOAT DEFAULT 0.0,  -- 0-1 score on extraction quality
    extraction_warnings JSONB,  -- Issues found during parsing

    UNIQUE(program_code, source_url)
);

CREATE INDEX idx_programs_name ON programs(program_name);
CREATE INDEX idx_programs_confidence ON programs(confidence_score);
CREATE INDEX idx_programs_updated ON programs(last_updated);

-- PDF documents catalog
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    source_url TEXT UNIQUE,
    file_name VARCHAR(500),
    file_type VARCHAR(20),
    file_size_mb FLOAT,
    download_timestamp TIMESTAMP DEFAULT NOW(),
    local_path TEXT,  -- Local filesystem path

    -- Extraction status
    text_extracted BOOLEAN DEFAULT FALSE,
    tables_extracted BOOLEAN DEFAULT FALSE,
    extraction_method VARCHAR(50),  -- 'pdfplumber', 'ocr', 'camelot'
    page_count INTEGER,

    -- Content
    full_text TEXT,
    tables JSONB,
    metadata JSONB
);

CREATE INDEX idx_documents_type ON documents(file_type);
CREATE INDEX idx_documents_extracted ON documents(text_extracted, tables_extracted);

-- Historical payment data (from EWG/public records)
CREATE TABLE IF NOT EXISTS historical_payments (
    id SERIAL PRIMARY KEY,
    program_name VARCHAR(200),
    year INTEGER,
    state VARCHAR(2),
    county VARCHAR(100),
    recipient_count INTEGER,
    total_payments DECIMAL(15,2),
    average_payment DECIMAL(12,2),
    median_payment DECIMAL(12,2),
    max_payment DECIMAL(12,2),
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(program_name, year, state, county, source)
);

CREATE INDEX idx_historical_state_year ON historical_payments(state, year);
CREATE INDEX idx_historical_program ON historical_payments(program_name);

-- Track what we've found and what's missing
CREATE TABLE IF NOT EXISTS data_gaps (
    id SERIAL PRIMARY KEY,
    program_name VARCHAR(200),
    missing_field VARCHAR(100),
    field_importance VARCHAR(20),  -- 'critical', 'important', 'nice-to-have'
    possible_sources TEXT[],
    notes TEXT,
    identified_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_data_gaps_importance ON data_gaps(field_importance);
CREATE INDEX idx_data_gaps_program ON data_gaps(program_name);

-- Scraping metadata and job tracking
CREATE TABLE IF NOT EXISTS scrape_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(50),  -- 'discovery', 'extraction', 'pdf', 'api'
    status VARCHAR(20),  -- 'pending', 'running', 'completed', 'failed'
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    error_log JSONB,
    metadata JSONB
);

CREATE INDEX idx_scrape_jobs_status ON scrape_jobs(status);
CREATE INDEX idx_scrape_jobs_type ON scrape_jobs(job_type);

-- NASS QuickStats data cache
CREATE TABLE IF NOT EXISTS nass_data (
    id SERIAL PRIMARY KEY,
    state VARCHAR(2),
    county VARCHAR(100),
    year INTEGER,
    commodity VARCHAR(100),
    data_item VARCHAR(200),
    value DECIMAL(15,2),
    unit VARCHAR(50),
    source_desc VARCHAR(100),
    fetched_at TIMESTAMP DEFAULT NOW(),
    raw_response JSONB,

    UNIQUE(state, county, year, commodity, data_item)
);

CREATE INDEX idx_nass_state_year ON nass_data(state, year);
CREATE INDEX idx_nass_commodity ON nass_data(commodity);

-- Create views for common queries

-- Programs with complete data
CREATE OR REPLACE VIEW programs_complete AS
SELECT
    program_name,
    program_code,
    confidence_score,
    CASE WHEN payment_min IS NOT NULL THEN true ELSE false END as has_payments,
    CASE WHEN eligibility_parsed IS NOT NULL THEN true ELSE false END as has_eligibility,
    CASE WHEN application_end IS NOT NULL THEN true ELSE false END as has_deadline,
    source_url,
    last_updated
FROM programs
WHERE confidence_score > 0.7;

-- Data completeness summary
CREATE OR REPLACE VIEW data_completeness_summary AS
SELECT
    COUNT(*) as total_programs,
    COUNT(*) FILTER (WHERE payment_min IS NOT NULL) as programs_with_payments,
    COUNT(*) FILTER (WHERE eligibility_parsed IS NOT NULL) as programs_with_eligibility,
    COUNT(*) FILTER (WHERE application_end IS NOT NULL) as programs_with_deadlines,
    COUNT(*) FILTER (WHERE confidence_score > 0.8) as high_confidence,
    COUNT(*) FILTER (WHERE confidence_score < 0.5) as low_confidence,
    ROUND(AVG(confidence_score)::numeric, 3) as avg_confidence
FROM programs;

-- Insert initial metadata
INSERT INTO scrape_jobs (job_type, status, metadata)
VALUES ('system', 'completed', '{"action": "database_initialized", "version": "1.0"}')
ON CONFLICT DO NOTHING;

-- Grant permissions (optional, adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO farm_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO farm_user;
