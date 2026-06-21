"""MCP Prompts — reusable interaction templates for knowledge base operations."""

from mcp.server.fastmcp import FastMCP
from app.mcp.server import mcp


@mcp.prompt()
def review_document(document_id: int) -> str:
    """Generate a prompt for reviewing a knowledge base document."""
    return (
        f"Please review the knowledge base document (ID: {document_id}) for:\n"
        f"1. Accuracy of information\n"
        f"2. Completeness of coverage\n"
        f"3. Clarity and readability\n"
        f"4. Structural organization\n"
        f"5. Suggested improvements\n\n"
        f"Use the read_document tool to fetch the document, then provide your review."
    )


@mcp.prompt()
def summarize_topic(topic: str) -> str:
    """Generate a prompt for summarizing a topic across multiple documents."""
    return (
        f"I need a comprehensive summary of '{topic}' based on the knowledge base.\n\n"
        f"Steps:\n"
        f"1. Use search_documents to find relevant documents about '{topic}'\n"
        f"2. Read the most relevant documents\n"
        f"3. Synthesize a clear, structured summary\n"
        f"4. Highlight key points, agreements, and contradictions\n"
        f"5. List source document IDs for reference"
    )


@mcp.prompt()
def compare_documents(document_id_1: int, document_id_2: int) -> str:
    """Generate a prompt for comparing two documents."""
    return (
        f"Compare these two knowledge base documents:\n"
        f"- Document A (ID: {document_id_1})\n"
        f"- Document B (ID: {document_id_2})\n\n"
        f"Analysis required:\n"
        f"1. Content overlap and differences\n"
        f"2. Unique information in each document\n"
        f"3. Quality comparison (completeness, accuracy, clarity)\n"
        f"4. Recommendations: merge, keep separate, or archive one"
    )


@mcp.prompt()
def write_from_requirements(requirements: str) -> str:
    """Generate a prompt for creating a new document from requirements."""
    return (
        f"Create a new knowledge base document based on these requirements:\n\n"
        f"{requirements}\n\n"
        f"Steps:\n"
        f"1. Search existing documents for related content (avoid duplication)\n"
        f"2. Create a well-structured document with clear headings\n"
        f"3. Use create_document tool with status='draft' for human review\n"
        f"4. Add appropriate tags\n"
        f"5. Report the created document ID"
    )


@mcp.prompt()
def organize_knowledge_base() -> str:
    """Generate a prompt for organizing and cleaning up the knowledge base."""
    return (
        "Analyze and organize the knowledge base:\n\n"
        "1. List all documents and identify duplicates or near-duplicates\n"
        "2. Check for documents without tags or folder assignment\n"
        "3. Suggest a folder structure based on content analysis\n"
        "4. Identify outdated documents that may need updating\n"
        "5. Recommend tag consolidation if there are similar tags\n\n"
        "Use list_documents, list_folders, and list_tags to gather information."
    )
