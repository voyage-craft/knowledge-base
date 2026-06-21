"""
LaTeX compilation sandbox utilities.
Provides safe compilation of LaTeX documents with security constraints.

Requirements: TeX Live or MiKTeX installed and in PATH.
"""
import asyncio
import os
import re
import tempfile
from pathlib import Path

# Dangerous LaTeX commands that should be blocked
DANGEROUS_COMMANDS = re.compile(
    r'\\(input|include|write18|ShellEscape|immediate|openout|special|pdfoutput|pdffilemoddate|pdffilesize|pdfmdfivesum|pdfcreationdate|pdfmatch|pdfstrcmp|pdffiledump)\b',
    re.IGNORECASE
)

def validate_latex_content(content: str) -> tuple[bool, str]:
    """Validate LaTeX content for dangerous commands."""
    matches = DANGEROUS_COMMANDS.findall(content)
    if matches:
        return False, f"Dangerous LaTeX commands found: {', '.join(set(matches))}"
    return True, ""

async def safe_latex_compile(
    tex_content: str,
    output_dir: str | None = None,
    timeout: int = 120,
    engine: str = "xelatex",
) -> tuple[bool, str, str]:
    """
    Compile LaTeX content safely in a sandboxed environment.

    Args:
        tex_content: The LaTeX source to compile
        output_dir: Directory for output files (uses temp dir if None)
        timeout: Maximum compilation time in seconds
        engine: LaTeX engine to use (xelatex, pdflatex, lualatex)

    Returns:
        Tuple of (success, output_path, error_message)
    """
    # Validate content
    is_safe, error = validate_latex_content(tex_content)
    if not is_safe:
        return False, "", error

    # Create temp directory for compilation
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="latex_")

    tex_path = os.path.join(output_dir, "document.tex")

    # Write LaTeX source
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    # Set restricted environment
    env = os.environ.copy()
    env["openout_any"] = "p"  # Restrict file output
    env["TEXMFOUTPUT"] = output_dir

    try:
        proc = await asyncio.create_subprocess_exec(
            engine,
            "-interaction=nonstopmode",
            "-no-shell-escape",  # CRITICAL: disable shell escape
            "-halt-on-error",
            f"-output-directory={output_dir}",
            "document.tex",
            cwd=output_dir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        pdf_path = os.path.join(output_dir, "document.pdf")

        if proc.returncode == 0 and os.path.exists(pdf_path):
            return True, pdf_path, ""
        else:
            error_msg = stderr.decode("utf-8", errors="replace")[:500]
            return False, "", f"Compilation failed: {error_msg}"

    except asyncio.TimeoutError:
        proc.kill()
        return False, "", f"Compilation timed out after {timeout}s"
    except FileNotFoundError:
        return False, "", f"LaTeX engine '{engine}' not found. Install TeX Live or MiKTeX."
    except Exception as e:
        return False, "", f"Unexpected error: {str(e)}"
