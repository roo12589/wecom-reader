"""Local media directory resolution and file.db attachment lookups."""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional

MEDIA_SUBDIRS = ("Image", "File", "Video", "Voice")


def _has_media_subdir(path: str) -> bool:
    return any(os.path.isdir(os.path.join(path, name)) for name in MEDIA_SUBDIRS)


def resolve_media_dir(db_dir: str) -> Optional[str]:
    """Locate the directory that directly contains Image/File/Video/Voice.

    Search order:
      1. ``db_dir`` itself
      2. ``db_dir/Cache``
      3. ``db_dir``'s parent ``/Cache``
      4. ``db_dir``'s parent

    Returns ``None`` when none of the candidates contains media subdirectories.
    """
    if not db_dir:
        return None

    base = os.path.abspath(os.path.expanduser(db_dir))
    candidates = [
        base,
        os.path.join(base, "Cache"),
        os.path.join(os.path.dirname(base), "Cache"),
        os.path.dirname(base),
    ]

    for candidate in candidates:
        if candidate and _has_media_subdir(candidate):
            return candidate
    return None


def guess_media_kind(name: str, message_type: int = 0, extension_type: int = 0) -> str:
    """Infer the media kind from file.db metadata and the file extension."""
    extension = os.path.splitext(name or "")[1].lower()

    if message_type == 1 or extension_type == 4:
        return "image"
    if message_type == 2 or extension in (".silk", ".slk"):
        return "voice"
    if message_type == 3 or extension in (".mp4", ".mov"):
        return "video"
    return "file"


class MediaCatalog:
    """Lazy, thread-safe catalog of locally cached WeCom media files."""

    def __init__(self, media_dir: str, file_db_path: str):
        self.media_dir = os.path.abspath(os.path.expanduser(media_dir)) if media_dir else ""
        self.file_db_path = os.path.abspath(os.path.expanduser(file_db_path)) if file_db_path else ""

        self._lock = threading.Lock()
        self._index: Optional[dict[str, str]] = None
        self._file_cache: dict[int, list[dict]] = {}

    # -- indexing -----------------------------------------------------

    def _scan(self) -> dict[str, str]:
        index: dict[str, str] = {}
        if not self.media_dir or not os.path.isdir(self.media_dir):
            return index

        for subdir in MEDIA_SUBDIRS:
            root = os.path.join(self.media_dir, subdir)
            if not os.path.isdir(root):
                continue
            for dirpath, _dirnames, filenames in os.walk(root):
                for filename in filenames:
                    key = filename.lower()
                    # Keep any one of the duplicates; first one wins.
                    index.setdefault(key, os.path.join(dirpath, filename))
        return index

    def _ensure_index(self) -> None:
        if self._index is not None:
            return
        with self._lock:
            if self._index is None:
                self._index = self._scan()

    def refresh(self) -> None:
        """Rebuild the filename index and clear the per-message query cache."""
        with self._lock:
            self._index = self._scan()
            self._file_cache.clear()

    # -- lookup -------------------------------------------------------

    def find_file(self, name: str) -> Optional[str]:
        """Look up a cached media file by filename (case-insensitive).

        Only paths already present in the scanned index are returned; the
        method never accepts or resolves an arbitrary caller-supplied path.
        """
        if not name:
            return None

        basename = os.path.basename(str(name).replace("\\", "/")).strip()
        if not basename:
            return None

        self._ensure_index()
        index = self._index or {}
        path = index.get(basename.lower())
        if path and os.path.isfile(path):
            return path
        return None

    def media_type_dir(self) -> Optional[str]:
        """Return the media root directory when it exists."""
        if self.media_dir and os.path.isdir(self.media_dir):
            return self.media_dir
        return None

    # -- file.db ------------------------------------------------------

    def _query_file_rows(self, message_id: int) -> list[sqlite3.Row]:
        if not self.file_db_path or not os.path.isfile(self.file_db_path):
            return []

        conn = sqlite3.connect(self.file_db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT origin, message_id, file_index, message_type, extension_type, "
                "server_id, name, size, md5 "
                "FROM file_table4 WHERE message_id = ? "
                "ORDER BY file_index, origin",
                (int(message_id),),
            ).fetchall()
            return list(rows)
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    def get_files_for_message(self, message_id: int) -> list[dict]:
        """Return attachment metadata rows for *message_id* from file.db.

        Each item contains ``message_id, index, name, size, md5, server_id,
        message_type, extension_type, kind, path, exists``.
        """
        if message_id is None:
            return []

        try:
            key = int(message_id)
        except (TypeError, ValueError):
            return []

        self._ensure_index()

        with self._lock:
            cached = self._file_cache.get(key)
            if cached is not None:
                return [dict(item) for item in cached]

        rows = self._query_file_rows(key)
        files: list[dict] = []
        for row in rows:
            name = row["name"] or ""
            kind = guess_media_kind(name, row["message_type"] or 0, row["extension_type"] or 0)
            path = self.find_file(name)
            files.append({
                "message_id": row["message_id"],
                "index": row["file_index"] or 0,
                "name": name,
                "size": row["size"] or 0,
                "md5": row["md5"] or "",
                "server_id": row["server_id"] or "",
                "message_type": row["message_type"] or 0,
                "extension_type": row["extension_type"] or 0,
                "kind": kind,
                "path": path,
                "exists": bool(path),
            })

        with self._lock:
            self._file_cache[key] = files
        return [dict(item) for item in files]

    def get_file_by_index(self, message_id: int, index: int) -> Optional[dict]:
        """Return the *index*-th attachment for a message, or ``None``."""
        files = self.get_files_for_message(message_id)
        try:
            position = int(index)
        except (TypeError, ValueError):
            return None
        if position < 0 or position >= len(files):
            return None
        return dict(files[position])
