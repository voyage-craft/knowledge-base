"""Format conversion node processor - convert between document formats.

Node types:
- format_convert: Convert document content to specified format

Config:
- output_format: Target format (latex, html, docx, markdown)
- template_id: Optional template ID for rendering
- theme_id: Optional theme ID for styling
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("format_convert")
class FormatConvertProcessor(NodeProcessor):
    """Convert document content to specified format."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})
        output_format = config.get("output_format", "latex")
        template_id = config.get("template_id")
        theme_id = config.get("theme_id")

        content_json = context.document.get("content_json")
        title = context.document.get("title", "Untitled")

        try:
            if output_format == "latex":
                from app.services.content_converter import tiptap_to_latex
                content = tiptap_to_latex(content_json, title)

                # Store in accumulated data for later use
                context.accumulated_data["latex_content"] = content

                return NodeResult(
                    output_data={"format": "latex", "content": content},
                    actions=["转换为LaTeX"],
                )

            elif output_format == "html":
                from app.services.content_converter import tiptap_to_html
                content = tiptap_to_html(content_json)

                context.accumulated_data["html_content"] = content

                return NodeResult(
                    output_data={"format": "html", "content": content},
                    actions=["转换为HTML"],
                )

            elif output_format == "docx":
                from app.services.content_converter import tiptap_to_docx
                import io
                docx_doc = tiptap_to_docx(content_json, title)
                buffer = io.BytesIO()
                docx_doc.save(buffer)
                buffer.seek(0)
                content = buffer.getvalue()

                context.accumulated_data["docx_content"] = content

                return NodeResult(
                    output_data={"format": "docx", "content": content},
                    actions=["转换为DOCX"],
                )

            elif output_format == "markdown":
                from app.services.content_converter import tiptap_to_html, html_to_markdown
                html_content = tiptap_to_html(content_json)
                content = f"# {title}\n\n{html_to_markdown(html_content)}"

                context.accumulated_data["markdown_content"] = content

                return NodeResult(
                    output_data={"format": "markdown", "content": content},
                    actions=["转换为Markdown"],
                )

            else:
                return NodeResult(error=f"不支持的格式: {output_format}")

        except Exception as e:
            logger.error("Format conversion failed for %s: %s", output_format, e)
            return NodeResult(error=f"格式转换失败: {e}")
