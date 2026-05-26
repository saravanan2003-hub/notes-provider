from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .auth import resolve_user
from .models import CreateNoteRequest, UpdateNoteRequest
from .store import notes_store

router = APIRouter(prefix="/notes", tags=["notes"])


def _current_user(request: Request) -> Tuple[str, str]:
    return resolve_user(request)


@router.post("", status_code=201)
async def create_note(
    body: CreateNoteRequest,
    user: Tuple[str, str] = Depends(_current_user),
):
    note = notes_store.create(user[0], body.title, body.body)
    return note.model_dump(mode="json")


@router.get("")
async def list_notes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Tuple[str, str] = Depends(_current_user),
):
    notes, total = notes_store.list(user[0], limit=limit, offset=offset)
    return {"notes": [n.model_dump(mode="json") for n in notes], "total": total}


@router.get("/{note_id}")
async def get_note(
    note_id: str,
    user: Tuple[str, str] = Depends(_current_user),
):
    note = notes_store.get(user[0], note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note not found: {note_id}")
    return note.model_dump(mode="json")


@router.put("/{note_id}")
async def update_note(
    note_id: str,
    body: UpdateNoteRequest,
    user: Tuple[str, str] = Depends(_current_user),
):
    note = notes_store.update(user[0], note_id, title=body.title, body=body.body)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note not found: {note_id}")
    return note.model_dump(mode="json")


@router.delete("/{note_id}", status_code=200)
async def delete_note(
    note_id: str,
    user: Tuple[str, str] = Depends(_current_user),
):
    deleted = notes_store.delete(user[0], note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Note not found: {note_id}")
    return {"deleted": True, "id": note_id}
