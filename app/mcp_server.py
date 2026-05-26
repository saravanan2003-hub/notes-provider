import os
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS

from .auth import get_current_user
from .store import notes_store

_allowed_hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "*").split(",") if h.strip()]
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection="*" not in _allowed_hosts,
    allowed_hosts=[] if "*" in _allowed_hosts else _allowed_hosts,
    allowed_origins=[] if "*" in _allowed_hosts else _allowed_hosts,
)

mcp = FastMCP("notes-provider", streamable_http_path="/", transport_security=_transport_security)


@mcp.tool()
def create_note(title: str, body: str) -> dict:
    """Create a new note. Returns the created note with its id."""
    user_id, _ = get_current_user()
    note = notes_store.create(user_id, title, body)
    return note.model_dump(mode="json")


@mcp.tool()
def get_note(id: str) -> dict:
    """Retrieve a note by id."""
    user_id, _ = get_current_user()
    note = notes_store.get(user_id, id)
    if note is None:
        raise McpError(ErrorData(code=INVALID_PARAMS, message=f"Note not found: {id}"))
    return note.model_dump(mode="json")


@mcp.tool()
def list_notes(limit: int = 20, offset: int = 0) -> dict:
    """List notes for the authenticated user."""
    user_id, _ = get_current_user()
    notes, total = notes_store.list(user_id, limit=limit, offset=offset)
    return {"notes": [n.model_dump(mode="json") for n in notes], "total": total}


@mcp.tool()
def update_note(id: str, title: Optional[str] = None, body: Optional[str] = None) -> dict:
    """Update a note's title and/or body."""
    user_id, _ = get_current_user()
    note = notes_store.update(user_id, id, title=title, body=body)
    if note is None:
        raise McpError(ErrorData(code=INVALID_PARAMS, message=f"Note not found: {id}"))
    return note.model_dump(mode="json")


@mcp.tool()
def delete_note(id: str) -> dict:
    """Delete a note by id."""
    user_id, _ = get_current_user()
    deleted = notes_store.delete(user_id, id)
    if not deleted:
        raise McpError(ErrorData(code=INVALID_PARAMS, message=f"Note not found: {id}"))
    return {"deleted": True, "id": id}
