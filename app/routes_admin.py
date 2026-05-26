from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .config import ADMIN_API_KEY
from .store import notes_store

router = APIRouter(prefix="/__admin", tags=["admin"])


def _require_admin_key(request: Request) -> None:
    key = request.headers.get("X-Admin-Key", "")
    if key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.get("/notes")
async def admin_list_notes(
    user_id: str = Query(...),
    _: None = Depends(_require_admin_key),
):
    notes = notes_store.all_for_user(user_id)
    return {"user_id": user_id, "notes": [n.model_dump() for n in notes]}


@router.delete("/notes")
async def admin_clear_notes(
    user_id: str = Query(...),
    _: None = Depends(_require_admin_key),
):
    notes_store.clear_user(user_id)
    return {"deleted": True, "user_id": user_id}
