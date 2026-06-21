"""Tests for settings API security and file parser service."""

import pytest
from app.services.file_parser import file_parser


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# --- Settings: test-llm requires admin ---

@pytest.mark.asyncio
async def test_test_llm_requires_admin(async_client):
    admin_headers = await _login(async_client)
    # Create non-admin user
    await async_client.post("/api/admin/users", json={
        "username": "nonadmin", "email": "na@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=admin_headers)

    nonadmin_headers = await _login(async_client, "nonadmin", "pass123")
    resp = await async_client.post("/api/settings/test-llm", json={
        "base_url": "http://localhost:1234",
        "api_key": "test",
        "model": "test",
    }, headers=nonadmin_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_test_llm_requires_auth(async_client):
    resp = await async_client.post("/api/settings/test-llm", json={
        "base_url": "http://localhost:1234",
        "api_key": "test",
        "model": "test",
    })
    assert resp.status_code == 401


# --- File Parser: Markdown ---

@pytest.mark.asyncio
async def test_parse_markdown():
    content = b"# Hello\n\nThis is **bold** text.\n\n- Item 1\n- Item 2"
    result = await file_parser.parse(content, "test.md")
    assert "Hello" in result
    assert "bold" in result


@pytest.mark.asyncio
async def test_parse_markdown_empty():
    content = b""
    result = await file_parser.parse(content, "empty.md")
    assert result == "" or result is not None  # Should not crash


# --- File Parser: Plain Text ---

@pytest.mark.asyncio
async def test_parse_plain_text():
    content = b"Just plain text content"
    result = await file_parser.parse(content, "notes.txt")
    assert "plain text" in result


# --- File Parser: LaTeX ---

@pytest.mark.asyncio
async def test_parse_latex():
    content = b"\\documentclass{article}\n\\begin{document}\nHello LaTeX\n\\end{document}"
    result = await file_parser.parse(content, "paper.tex")
    assert "Hello LaTeX" in result


@pytest.mark.asyncio
async def test_parse_latex_strips_commands():
    content = b"\\section{Title}\n\\textbf{Bold text}\n\\emph{Emphasized}"
    result = await file_parser.parse(content, "doc.tex")
    assert "Title" in result
    assert "Bold text" in result
    assert "Emphasized" in result


# --- File Parser: Type Detection ---

def test_detect_type_markdown():
    assert file_parser.detect_type("readme.md") == "md"


def test_detect_type_text():
    assert file_parser.detect_type("notes.txt") == "txt"


def test_detect_type_latex():
    assert file_parser.detect_type("paper.tex") == "tex"
    assert file_parser.detect_type("thesis.latex") == "tex"


def test_detect_type_docx():
    assert file_parser.detect_type("report.docx") == "docx"


def test_detect_type_pdf():
    assert file_parser.detect_type("manual.pdf") == "pdf"


def test_detect_type_unknown():
    assert file_parser.detect_type("data.xyz") == "xyz"


# --- File Parser: Unsupported Formats ---

@pytest.mark.asyncio
async def test_parse_unsupported_raises():
    content = b"some binary content"
    with pytest.raises(ValueError):
        await file_parser.parse(content, "file.xyz")


# --- Auth: Refresh Token Validation ---

@pytest.mark.asyncio
async def test_refresh_token_disabled_user(async_client):
    """After admin disables a user, their refresh token should be rejected."""
    admin_headers = await _login(async_client)

    # Create a user
    await async_client.post("/api/admin/users", json={
        "username": "refreshtest", "email": "rt@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=admin_headers)

    # Login and get tokens
    login = await async_client.post("/api/auth/login", json={
        "username": "refreshtest", "password": "pass123",
    })
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    # Disable the user
    users = await async_client.get("/api/admin/users?search=refreshtest", headers=admin_headers)
    uid = users.json()["users"][0]["id"]
    await async_client.put(f"/api/admin/users/{uid}", json={
        "is_active": False,
    }, headers=admin_headers)

    # Try to refresh - should fail
    resp = await async_client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert resp.status_code in (401, 403)
