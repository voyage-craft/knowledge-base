-- Migration 003: Batch Import tables
-- Create import_batches table
CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_files INTEGER NOT NULL DEFAULT 0,
    processed_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_import_batches_user_id ON import_batches(user_id);

-- Create import_files table
CREATE TABLE IF NOT EXISTS import_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES import_batches(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    raw_text TEXT,
    ai_analysis JSON,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    imported_document_id INTEGER REFERENCES documents(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_import_files_batch_id ON import_files(batch_id);
