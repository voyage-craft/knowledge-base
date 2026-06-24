"""Workflow node processors package.

This package contains all built-in node processors for the workflow engine.
Import this module to register all processors.
"""

# Import all node processors to trigger registration
from app.services.workflow.nodes.source import SourceProcessor
from app.services.workflow.nodes.edit import (
    PolishProcessor, ExpandProcessor, CompressProcessor,
    TranslateZhProcessor, TranslateEnProcessor, FixProcessor
)
from app.services.workflow.nodes.analysis import (
    SummarizeProcessor, KeywordsProcessor, StandardizeProcessor
)
from app.services.workflow.nodes.tagging import AutoTagProcessor
from app.services.workflow.nodes.prompt import CustomPromptProcessor
from app.services.workflow.nodes.save import SaveProcessor
from app.services.workflow.nodes.export import ExportProcessor
from app.services.workflow.nodes.condition import ConditionProcessor
from app.services.workflow.nodes.format_convert import FormatConvertProcessor
from app.services.workflow.nodes.ai_analyze import AIAnalyzeProcessor
from app.services.workflow.nodes.loop import LoopProcessor
from app.services.workflow.nodes.approval import ApprovalProcessor
from app.services.workflow.nodes.rename import RenameProcessor
from app.services.workflow.nodes.set_metadata import SetMetadataProcessor
from app.services.workflow.nodes.embedding import EmbeddingProcessor

__all__ = [
    "SourceProcessor",
    "PolishProcessor", "ExpandProcessor", "CompressProcessor",
    "TranslateZhProcessor", "TranslateEnProcessor", "FixProcessor",
    "SummarizeProcessor", "KeywordsProcessor", "StandardizeProcessor",
    "AutoTagProcessor", "CustomPromptProcessor", "SaveProcessor",
    "ExportProcessor", "ConditionProcessor", "FormatConvertProcessor",
    "AIAnalyzeProcessor", "LoopProcessor", "ApprovalProcessor",
    "RenameProcessor", "SetMetadataProcessor", "EmbeddingProcessor",
]
