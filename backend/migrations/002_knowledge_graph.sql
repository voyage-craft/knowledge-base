-- Migration 002: Knowledge Graph tables
-- Create graph_nodes table
CREATE TABLE IF NOT EXISTS graph_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    node_type VARCHAR(20) NOT NULL,
    label VARCHAR(500) NOT NULL,
    description TEXT,
    document_id INTEGER REFERENCES documents(id),
    metadata_json JSON,
    embedding_text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_graph_nodes_user_id ON graph_nodes(user_id);
CREATE INDEX IF NOT EXISTS ix_graph_nodes_document_id ON graph_nodes(document_id);
CREATE INDEX IF NOT EXISTS ix_graph_nodes_user_type_label ON graph_nodes(user_id, node_type, label);

-- Create graph_edges table
CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    source_id INTEGER NOT NULL REFERENCES graph_nodes(id),
    target_id INTEGER NOT NULL REFERENCES graph_nodes(id),
    edge_type VARCHAR(50) NOT NULL,
    weight REAL DEFAULT 1.0,
    description VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_graph_edges_user_id ON graph_edges(user_id);
CREATE INDEX IF NOT EXISTS ix_graph_edges_source_id ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS ix_graph_edges_target_id ON graph_edges(target_id);
CREATE INDEX IF NOT EXISTS ix_graph_edges_source_target ON graph_edges(source_id, target_id);
