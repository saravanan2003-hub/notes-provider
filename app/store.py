from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from .models import Note


class NotesStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Note]] = {}

    def _user_store(self, user_id: str) -> dict[str, Note]:
        if user_id not in self._data:
            self._data[user_id] = {}
        return self._data[user_id]

    def create(self, user_id: str, title: str, body: str) -> Note:
        note = Note(
            id=str(uuid.uuid4()),
            title=title,
            body=body,
            created_at=datetime.now(timezone.utc),
        )
        self._user_store(user_id)[note.id] = note
        return note

    def get(self, user_id: str, note_id: str) -> Optional[Note]:
        return self._user_store(user_id).get(note_id)

    def list(self, user_id: str, limit: int = 20, offset: int = 0) -> tuple[list[Note], int]:
        notes = list(self._user_store(user_id).values())
        notes.sort(key=lambda n: n.created_at)
        return notes[offset : offset + limit], len(notes)

    def update(self, user_id: str, note_id: str, title: Optional[str], body: Optional[str]) -> Optional[Note]:
        store = self._user_store(user_id)
        note = store.get(note_id)
        if note is None:
            return None
        updated = note.model_copy(
            update={
                **({"title": title} if title is not None else {}),
                **({"body": body} if body is not None else {}),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        store[note_id] = updated
        return updated

    def delete(self, user_id: str, note_id: str) -> bool:
        store = self._user_store(user_id)
        if note_id not in store:
            return False
        del store[note_id]
        return True

    def all_for_user(self, user_id: str) -> list[Note]:
        return list(self._user_store(user_id).values())

    def clear_user(self, user_id: str) -> None:
        self._data.pop(user_id, None)


notes_store = NotesStore()
