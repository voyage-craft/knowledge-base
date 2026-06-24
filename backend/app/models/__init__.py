"""Import all models so Alembic auto-migration can discover them."""

from app.models.user import User  # noqa: F401
from app.models.document import Document, DocumentVersion, Folder, Tag, document_tags  # noqa: F401
from app.models.system_settings import SystemSetting  # noqa: F401
from app.models.graph import GraphNode, GraphEdge  # noqa: F401
from app.models.import_batch import ImportBatch, ImportFile  # noqa: F401
from app.models.document_chunk import DocumentChunk  # noqa: F401
from app.models.workflow import Workflow, WorkflowRun  # noqa: F401
from app.models.api_endpoint import ApiEndpoint, ApiRoutingRule  # noqa: F401
from app.models.plugin import PluginRecord  # noqa: F401
