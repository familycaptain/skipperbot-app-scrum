-- =============================================================================
-- Scrum app — 001_initial.sql
-- =============================================================================
-- Creates the app_scrum schema and the scrum_items table.
--
-- The platform's app_platform/migrator.py invokes this with
-- search_path = app_scrum, public already set within its transaction, so
-- unqualified table names resolve into the scrum app's schema. The
-- CREATE SCHEMA + SET search_path + BEGIN/COMMIT lines at the top are a
-- defensive belt-and-suspenders so this file also applies cleanly if run
-- by hand:
--     psql -d skipperbot -f apps/scrum/migrations/001_initial.sql
--
-- The whole migration runs in a single transaction so search_path changes
-- stick for every statement, and a failure rolls back cleanly.
--
-- Idempotent. Re-running is a no-op.

BEGIN;

CREATE SCHEMA IF NOT EXISTS app_scrum;
SET LOCAL search_path TO app_scrum, public;

-- =============================================================================
-- scrum_items — one daily PM-digest item per person, optionally answered
-- =============================================================================

CREATE TABLE IF NOT EXISTS scrum_items (
    id                  text NOT NULL,
    report_date         date NOT NULL,
    person              text NOT NULL,
    item_type           text NOT NULL,
    title               text NOT NULL,
    detail              text,
    source_entity_id    text,
    source_entity_type  text,
    project_name        text,
    severity            text,
    response            text,
    responded_at        timestamp with time zone,
    created_at          timestamp with time zone NOT NULL DEFAULT now()
);

DO $$ BEGIN
    ALTER TABLE scrum_items
        ADD CONSTRAINT scrum_items_pkey PRIMARY KEY (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
    WHEN invalid_table_definition THEN NULL;
    WHEN duplicate_table THEN NULL;
END $$;

-- Admin view across all users for a date.
CREATE INDEX IF NOT EXISTS idx_scrum_items_report_date
    ON scrum_items (report_date);

-- Primary query pattern: a person's items for a date / recent range.
CREATE INDEX IF NOT EXISTS idx_scrum_items_person_report_date
    ON scrum_items (person, report_date);

COMMIT;
