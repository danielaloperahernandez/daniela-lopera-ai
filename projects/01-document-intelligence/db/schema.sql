-- Postgres schema for the Document Intelligence sink (Project 1).
-- Apply with:  psql "$DATABASE_URL" -f db/schema.sql

CREATE TABLE IF NOT EXISTS invoices (
    id            BIGSERIAL PRIMARY KEY,
    invoice_number TEXT,
    vendor_name   TEXT,
    customer_name TEXT,
    issue_date    DATE,
    due_date      DATE,
    currency      TEXT,
    subtotal      NUMERIC(14, 2),
    tax           NUMERIC(14, 2),
    total         NUMERIC(14, 2),
    source_file   TEXT,
    raw           JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices (vendor_name);
CREATE INDEX IF NOT EXISTS idx_invoices_issue_date ON invoices (issue_date);

-- Used by the Error Handler workflow.
CREATE TABLE IF NOT EXISTS error_log (
    id          BIGSERIAL PRIMARY KEY,
    workflow    TEXT,
    node        TEXT,
    message     TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
