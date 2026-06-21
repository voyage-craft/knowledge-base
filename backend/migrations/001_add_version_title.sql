-- Migration: Add version history support
-- Run this SQL against the SQLite database: data/knowledge.db

-- Add title column to document_versions
ALTER TABLE document_versions ADD COLUMN title VARCHAR(500);

-- Add index on document_id for faster version lookups
CREATE INDEX IF NOT EXISTS ix_document_versions_document_id ON document_versions(document_id);
