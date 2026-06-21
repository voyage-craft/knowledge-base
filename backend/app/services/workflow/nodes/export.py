"""Export node processor - export document to various formats.

Node types:
- export: Export document to specified format (markdown, html, latex, pdf, docx)
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.models.document import Document

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("export")
class ExportProcessor(NodeProcessor):
    """Export document to specified format."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})
        output_format = config.get("format", "markdown")
        template_id = config.get("template_id")
        theme_id = config.get("theme_id")

        # Get document content
        content_json = context.document.get("content_json")
        title = context.document.get("title", "Untitled")

        try:
            if output_format == "latex":
                from app.services.content_converter import tiptap_to_latex
                content = tiptap_to_latex(content_json, title)
                return NodeResult(
                    output_data={"format": "latex", "content": content},
                    actions=[f"导出LaTeX"],
                )

            elif output_format == "html":
                from app.services.content_converter import tiptap_to_html
                html_content = tiptap_to_html(content_json)
                return NodeResult(
                    output_data={"format": "html", "content": html_content},
                    actions=["导出HTML"],
                )

            elif output_format == "docx":
                from app.services.content_converter import tiptap_to_docx
                docx_doc = tiptap_to_docx(content_json, title)
                import io
                buffer = io.BytesIO()
                docx_doc.save(buffer)
                buffer.seek(0)
                return NodeResult(
                    output_data={"format": "docx", "content": buffer.getvalue()},
                    actions=["导出DOCX"],
                )

            elif output_format == "markdown":
                from app.services.content_converter import tiptap_to_html, html_to_markdown
                html_content = tiptap_to_html(content_json)
                md_content = f"# {title}\n\n{html_to_markdown(html_content)}"
                return NodeResult(
                    output_data={"format": "markdown", "content": md_content},
                    actions=["导出Markdown"],
                )

            elif output_format == "pdf":
                # PDF generation requires LaTeX compilation
                from app.services.content_converter import tiptap_to_latex
                latex_content = tiptap_to_latex(content_json, title)

                # Store LaTeX for later PDF compilation
                context.accumulated_data.setdefault("exports", []).append({
                    "format": "pdf",
                    "latex": latex_content,
                    "title": title,
                })
                return NodeResult(
                    output_data={"format": "pdf", "latex": latex_content},
                    actions=["准备PDF导出"],
                )

            else:
                return NodeResult(error=f"不支持的导出格式: {output_format}")

        except Exception as e:
            logger.error("Export failed for format %s: %s", output_format, e)
            return NodeResult(error=f"导出失败: {e}")
