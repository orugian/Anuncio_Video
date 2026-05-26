-- Sync migration for repositories created before approval/feedback features.
-- Apply manually in Supabase SQL editor or migration workflow.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'job_status'
          AND e.enumlabel = 'awaiting_approval'
    ) THEN
        ALTER TYPE job_status ADD VALUE 'awaiting_approval';
    END IF;
END $$;

ALTER TABLE marketing_scripts
ADD COLUMN IF NOT EXISTS feedback_history JSONB NOT NULL DEFAULT '[]'::jsonb;
