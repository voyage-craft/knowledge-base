"""Multi-format file parser for batch import."""

import re
import logging

logger = logging.getLogger(__name__)


class FileParser:
    """Parse various file formats to plain text for AI analysis."""

    SUPPORTED_TYPES = {"md", "docx", "pdf", "txt", "tex"}

    @staticmethod
    def detect_type(filename: str) -> str:
        """Detect file type from extension."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "markdown":
            return "md"
        if ext == "latex":
            return "tex"
        return ext

    @staticmethod
    async def parse(file_bytes: bytes, filename: str) -> str:
        """Parse file bytes to plain text based on file type."""
        file_type = FileParser.detect_type(filename)

        if file_type == "md":
            return file_bytes.decode("utf-8", errors="replace")

        elif file_type == "txt":
            return file_bytes.decode("utf-8", errors="replace")

        elif file_type == "tex":
            raw = file_bytes.decode("utf-8", errors="replace")
            try:
                from app.services.content_converter import latex_to_tiptap
                return latex_to_tiptap(raw)
            except Exception:
                return FileParser._strip_latex(raw)

        elif file_type == "docx":
            return await FileParser._parse_docx(file_bytes)

        elif file_type == "pdf":
            return await FileParser._parse_pdf(file_bytes)

        else:
            raise ValueError(f"不支持的文件格式: {file_type}")

    @staticmethod
    def _strip_latex(text: str) -> str:
        """Basic LaTeX to plain text conversion — strip commands, keep content."""
        # Remove comments
        text = re.sub(r"%.*$", "", text, flags=re.MULTILINE)
        # Remove \command{...} but keep the content
        text = re.sub(r"\\(?:section|subsection|subsubsection|chapter|title|textbf|textit|emph|underline)\{([^}]*)\}", r"\1", text)
        # Remove \begin{...} / \end{...}
        text = re.sub(r"\\(?:begin|end)\{[^}]*\}", "", text)
        # Remove common commands but keep arguments
        text = re.sub(r"\\(?:label|ref|cite|usepackage|documentclass|input|include|newcommand|renewcommand|setlength|geometry|bibliography|bibliographystyle|maketitle|tableofcontents)(?:\[[^\]]*\])?\{[^}]*\}", "", text)
        # Remove remaining backslash commands
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])*\{([^}]*)\}", r"\1", text)
        # Remove braces
        text = text.replace("{", "").replace("}", "")
        # Remove math delimiters but keep content
        text = re.sub(r"\$\$(.*?)\$\$", r" \1 ", text, flags=re.DOTALL)
        text = re.sub(r"\$(.*?)\$", r"\1", text, flags=re.DOTALL)
        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    async def _parse_docx(file_bytes: bytes) -> dict:
        """Parse DOCX to TipTap JSON, preserving headings, bold/italic, lists, tables."""
        try:
            from app.services.content_converter import docx_to_tiptap
            return docx_to_tiptap(file_bytes)
        except Exception as e:
            logger.error("Failed to parse docx: %s", e)
            raise ValueError(f"DOCX解析失败: {e}")

    @staticmethod
    async def _parse_pdf(file_bytes: bytes) -> dict:
        """Parse PDF to TipTap JSON with heading detection based on font size."""
        try:
            import io
            import pdfplumber

            content_nodes: list[dict] = []

            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    # Get character-level data for font size analysis
                    chars = page.chars or []
                    if not chars:
                        # Fallback to plain text
                        page_text = page.extract_text()
                        if page_text:
                            for para in page_text.strip().split("\n\n"):
                                if para.strip():
                                    content_nodes.append({
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": para.strip()}],
                                    })
                        continue

                    # Group chars into lines by y-coordinate
                    lines_by_y: dict[float, list] = {}
                    for char in chars:
                        y = round(char.get("top", 0), 1)
                        if y not in lines_by_y:
                            lines_by_y[y] = []
                        lines_by_y[y].append(char)

                    # Calculate median font size for body text
                    sizes = [c.get("size", 12) for c in chars if c.get("size")]
                    median_size = sorted(sizes)[len(sizes) // 2] if sizes else 12

                    for y in sorted(lines_by_y.keys()):
                        line_chars = lines_by_y[y]
                        text = "".join(c.get("text", "") for c in line_chars).strip()
                        if not text:
                            continue

                        # Get line font size (use the most common size in this line)
                        line_sizes = [c.get("size", 12) for c in line_chars if c.get("size")]
                        line_size = max(set(line_sizes), key=line_sizes.count) if line_sizes else median_size

                        # Detect headings by font size
                        if line_size > median_size * 1.5:
                            content_nodes.append({
                                "type": "heading",
                                "attrs": {"level": 1},
                                "content": [{"type": "text", "text": text}],
                            })
                        elif line_size > median_size * 1.2:
                            content_nodes.append({
                                "type": "heading",
                                "attrs": {"level": 2},
                                "content": [{"type": "text", "text": text}],
                            })
                        elif line_size > median_size * 1.05:
                            content_nodes.append({
                                "type": "heading",
                                "attrs": {"level": 3},
                                "content": [{"type": "text", "text": text}],
                            })
                        else:
                            content_nodes.append({
                                "type": "paragraph",
                                "content": [{"type": "text", "text": text}],
                            })

            return {"type": "doc", "content": content_nodes if content_nodes else [{"type": "paragraph"}]}
        except ImportError:
            raise ValueError("PDF解析需要 pdfplumber，请安装: pip install pdfplumber")
        except Exception as e:
            logger.error("Failed to parse pdf: %s", e)
            raise ValueError(f"PDF解析失败: {e}")


file_parser = FileParser()
