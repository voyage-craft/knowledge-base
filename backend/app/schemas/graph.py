from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class GraphNodeResponse(BaseModel):
    id: int
    node_type: str
    label: str
    description: Optional[str] = None
    document_id: Optional[int] = None
    metadata_json: Optional[dict] = None

    class Config:
        from_attributes = True


class GraphEdgeResponse(BaseModel):
    id: int
    source_id: int
    target_id: int
    edge_type: str
    weight: float
    description: Optional[str] = None

    class Config:
        from_attributes = True


class GraphDataResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class DocumentGraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    document_node: Optional[GraphNodeResponse] = None


class BuildGraphResponse(BaseModel):
    message: str
    nodes_created: int
    edges_created: int
