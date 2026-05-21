-- Migration: Add source column to rooms table
-- This distinguishes manually created rooms from match-created rooms.

ALTER TABLE rooms ADD COLUMN IF NOT EXISTS source VARCHAR(16) DEFAULT 'manual';
COMMENT ON COLUMN rooms.source IS 'Room creation source: manual or match';
