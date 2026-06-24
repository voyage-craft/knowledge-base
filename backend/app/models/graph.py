from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from app.core.database import Base


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (
        Index("ix_graph_nodes_user_type_label", "user_id", "node_type", "label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    node_type = Column(String(20), nullable=False)  # "document" | "entity" | "concept"
    label = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)  # only for document type
    metadata_json = Column(JSON, nullable=True)  # {entity_type, aliases, ...}
    embedding_text = Column(Text, nullable=True)  # text for similarity computation
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        Index("ix_graph_edges_source_target", "source_id", "target_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("graph_nodes.id"), nullable=False, index=True)
    edge_type = Column(String(50), nullable=False)  # "references"|"related_to"|"contains_entity"|"similar_topic"|"depends_on"
    weight = Column(Float, default=1.0)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
