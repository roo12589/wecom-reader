"""Main WeComReader class — unified interface for WeCom chat data access."""

import mimetypes
import os
import re
import shutil
import sqlite3
import threading
from typing import Any, Optional
from urllib.parse import quote

from .crypto.decrypt import (
    decrypt_database,
    is_plain_sqlite,
    is_wxsqlite3_aes128_page1,
    verify_key,
)
from .crypto.key_extract import extract_key
from .db.contact import (
    build_avatar_file_map,
    build_user_info,
    build_user_map,
    build_user_names,
    detect_self_id,
    get_avatar_buffer,
    get_group_members,
    list_contacts,
)
from .db.media import MediaCatalog, guess_media_kind, resolve_media_dir
from .db.message import (
    MESSAGE_TABLES,
    get_message_count as db_get_message_count,
    query_messages as db_query_messages,
    search_messages as db_search_messages,
)
from .db.proto import decode_message
from .db.session import (
    get_session_count,
    get_session_detail,
    load_sessions,
)

_TYPE_LABELS = {
    "group": "群聊",
    "single": "单聊",
    "wechat": "微信",
    "app": "应用",
    "system": "系统",
    "external": "外部会话",
    "other": "其它",
}

_TYPE_ALIASES = {
    "r": "group",
    "r:": "group",
    "s": "single",
    "s:": "single",
    "m": "wechat",
    "m:": "wechat",
    "wechat_contact": "wechat",
    "o": "app",
    "o:": "app",
    "y": "system",
    "y:": "system",
}

_LEGACY_TYPE_PREFIXES = {
    "r": "R:",
    "r:": "R:",
    "s": "S:",
    "s:": "S:",
    "m": "M:",
    "m:": "M:",
    "o": "O:",
    "o:": "O:",
    "y": "Y:",
    "y:": "Y:",
}

# Internal identifiers must never be used as a display name or preview.
_RAW_ID_RE = re.compile(
    r"^(?:WN[0-9A-Za-z~._+\-]+|[0-9]+|[0-9a-fA-F]{32}|[RSMOY]:[0-9A-Za-z_:]+)$"
)

_SELECT_FIELDS = (
    "message_id",
    "conversation_id",
    "content_type",
    "content",
    "extra_content",
    "send_time",
    "sender_id",
    "sequence",
    "server_id",
    "flag",
    "from_app_id",
)

_AVATAR_MAX_BYTES = 2 * 1024 * 1024


def _connect_ro(db_path: str) -> sqlite3.Connection:
    """Open a decrypted database read-only (never creates sidecars)."""
    path = str(db_path)
    uri = "file:" + path.replace("\\", "/").replace("?", "%3F").replace("#", "%23")
    try:
        conn = sqlite3.connect(uri + "?mode=ro", uri=True)
    except sqlite3.Error:
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_raw_id(text: str) -> bool:
    return bool(text) and bool(_RAW_ID_RE.match(text.strip()))


def _sniff_mimetype(data: bytes) -> str:
    """Best-effort image mimetype detection from its magic bytes."""
    if not data:
        return "image/png"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    return "image/png"


def _guess_mimetype(name: str) -> str:
    ext = os.path.splitext(name or "")[1].lower()
    if ext in (".silk", ".slk"):
        return "application/octet-stream"
    if ext == ".amr":
        return "audio/amr"
    guessed = mimetypes.guess_type(name or "")[0] if name else None
    return guessed or "application/octet-stream"


class WeComReader:
    """Agent-reusable WeCom (企业微信) local chat reader.

    Usage:
        reader = WeComReader()           # auto-detect
        reader = WeComReader(db_dir=...) # explicit path

        # One-step init + decrypt
        reader.init()

        # Query
        sessions = reader.list_sessions()
        msgs = reader.get_messages("R:12345")
        results = reader.search_messages("keyword")
        contacts = reader.contacts()
    """

    def __init__(
        self,
        db_dir: Optional[str] = None,
        decrypted_dir: Optional[str] = None,
        key_map: Optional[dict] = None,
        process_names: Optional[list[str]] = None,
        media_dir: Optional[str] = None,
        self_id: Optional[int] = None,
    ):
        """Initialize reader.

        Args:
            db_dir: Path to WeCom Data directory (auto-detected if None).
            decrypted_dir: Path for decrypted DB output (default: ./wxwork_decrypted).
            key_map: Pre-extracted key map from extract_key(). If None, init() will extract.
            process_names: Client executable names to scan for the key. When
                None the client is auto-detected (WXWork.exe, or the renamed
                binary used by a private deployment, e.g. airchina.exe).
            media_dir: Directory containing Image/File/Video/Voice (auto-detected).
            self_id: Current account id (auto-detected from session.db when None).
        """
        self._db_dir = db_dir
        self._decrypted_dir = decrypted_dir or os.path.join(os.getcwd(), "wxwork_decrypted")
        self._key_map = key_map
        self._process_names = process_names
        self._media_dir = media_dir
        self._configured_self_id = _as_int(self_id)

        self._cache_lock = threading.RLock()
        self._caches_ready = False
        self._user_map: Optional[dict] = None

        self._user_names: dict[int, str] = {}
        self._user_info: dict[int, dict] = {}
        self._self_id: Optional[int] = None
        self._sessions: list[dict] = []
        self._sessions_by_id: dict[str, dict] = {}
        self._media_catalog: Optional[MediaCatalog] = None
        self._avatar_dir: Optional[str] = None
        self._avatar_db_path: Optional[str] = None
        self._user_avatar_map: dict[int, str] = {}
        self._member_cache: dict[str, dict] = {}
        self._preview_cache: dict[tuple, dict] = {}
        self._message_row_cache: dict[tuple, dict] = {}
        self._voice_texts: dict[str, str] = {}
        self._file_rows_cache: dict[int, list[dict]] = {}
        self._decoded_files_cache: dict[int, list[dict]] = {}
        self._avatar_bytes_cache: dict[tuple, tuple[Optional[bytes], str]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def db_dir(self) -> Optional[str]:
        return self._db_dir

    @property
    def decrypted_dir(self) -> str:
        return self._decrypted_dir

    @property
    def self_id(self) -> Optional[int]:
        self._ensure_caches()
        return self._self_id

    @property
    def media_dir(self) -> Optional[str]:
        if self._media_dir is None:
            self._media_dir = (
                resolve_media_dir(self._db_dir)
                or resolve_media_dir(self._decrypted_dir)
            )
        return self._media_dir

    @property
    def avatar_dir(self) -> Optional[str]:
        if self._avatar_dir is None:
            self._avatar_dir = self._detect_avatar_dir()
        return self._avatar_dir

    @property
    def session_db_path(self) -> Optional[str]:
        return self._get_db_path("session.db")

    @property
    def message_db_path(self) -> Optional[str]:
        return self._get_db_path("message.db")

    @property
    def file_db_path(self) -> Optional[str]:
        return self._get_db_path("file.db")

    @property
    def avatar_db_path(self) -> Optional[str]:
        return self._get_db_path("avatar_store_v3.db")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def invalidate_caches(self) -> None:
        """Drop every lazily built cache so the next call rebuilds them."""
        with self._cache_lock:
            self._user_map = None
            self._user_names = {}
            self._user_info = {}
            self._self_id = None
            self._sessions = []
            self._sessions_by_id = {}
            self._media_catalog = None
            self._avatar_dir = None
            self._avatar_db_path = None
            self._user_avatar_map = {}
            self._member_cache = {}
            self._preview_cache = {}
            self._message_row_cache = {}
            self._voice_texts = {}
            self._file_rows_cache = {}
            self._decoded_files_cache = {}
            self._avatar_bytes_cache = {}
            self._caches_ready = False

    def ensure_ready(self, timeout: int = 120) -> dict:
        """Decrypt on demand when session.db/message.db are missing."""
        try:
            has_session = self._get_db_path("session.db") is not None
            has_message = self._get_db_path("message.db") is not None
            if has_session and has_message:
                return {"ready": True}
            result = self.init(timeout=timeout, verbose=True)
            ready = bool(result.get("success")) or (
                self._get_db_path("session.db") is not None
                and self._get_db_path("message.db") is not None
            )
            result["ready"] = ready
            return result
        except Exception as exc:  # never break the web app
            return {"ready": False, "success": False, "error": str(exc)}

    def status(self) -> dict:
        """Check current status of decrypted data."""
        result = {
            "db_dir": self._db_dir,
            "decrypted_dir": self._decrypted_dir,
            "decrypted": os.path.isdir(self._decrypted_dir),
            "databases": {},
        }

        if os.path.isdir(self._decrypted_dir):
            for name in os.listdir(self._decrypted_dir):
                path = os.path.join(self._decrypted_dir, name)
                if name.endswith(".db") and os.path.isfile(path):
                    sz = os.path.getsize(path)
                    try:
                        conn = sqlite3.connect(path)
                        tables = [
                            r[0]
                            for r in conn.execute(
                                "SELECT name FROM sqlite_master WHERE type='table'"
                            ).fetchall()
                        ]
                        conn.close()
                    except Exception:
                        tables = []
                    result["databases"][name] = {
                        "size_mb": round(sz / 1024 / 1024, 1),
                        "tables": tables,
                    }

        try:
            self._ensure_caches()
            result["sessions"] = len(self._sessions)
            result["messages"] = self._total_message_count()
            result["self_id"] = self._self_id
            result["media_dir"] = self.media_dir
        except Exception:
            result.setdefault("sessions", 0)
            result.setdefault("messages", None)
            result.setdefault("self_id", None)
            result.setdefault("media_dir", self._media_dir)

        return result

    def init(
        self,
        timeout: int = 120,
        verbose: bool = False,
    ) -> dict:
        """Extract keys from the client process and decrypt all databases.

        Args:
            timeout: Max seconds for memory scan per process.
            verbose: Print progress.

        Returns:
            Dict with success status, key count, db count, etc.
        """
        # Extract keys
        if self._key_map is None:
            if verbose:
                print("[*] Extracting keys from client memory...")
            self._key_map = extract_key(
                db_dir=self._db_dir,
                timeout=timeout,
                verbose=verbose,
                process_names=self._process_names,
            )

        self._db_dir = self._key_map.get("_db_dir", self._db_dir)
        if not self._db_dir:
            raise RuntimeError("No db_dir found in key map")

        # Decrypt databases
        os.makedirs(self._decrypted_dir, exist_ok=True)
        success = 0
        copied = 0
        failed = 0

        for root, dirs, files in os.walk(self._db_dir):
            dirs[:] = [d for d in dirs if d not in ("-journal",)]
            for name in files:
                if not name.endswith(".db") or name.endswith("-wal") or name.endswith("-shm"):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, self._db_dir)
                out_path = os.path.join(self._decrypted_dir, rel)

                with open(path, "rb") as f:
                    page1 = f.read(4096)

                if is_plain_sqlite(page1):
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    shutil.copy2(path, out_path)
                    copied += 1
                    continue

                if not is_wxsqlite3_aes128_page1(page1):
                    failed += 1
                    continue

                # Find key for this DB
                salt_hex = page1[:16].hex()
                key_hex = self._key_map.get(salt_hex)
                if not key_hex:
                    # Try all keys
                    for k, v in self._key_map.items():
                        if k.startswith("_"):
                            continue
                        if verify_key(bytes.fromhex(v), page1):
                            key_hex = v
                            break

                if not key_hex:
                    failed += 1
                    continue

                try:
                    decrypt_database(path, out_path, bytes.fromhex(key_hex))
                    success += 1
                except Exception:
                    failed += 1

        # Data on disk may have changed: rebuild lazy caches.
        self._media_dir = (
            self._media_dir
            or resolve_media_dir(self._db_dir)
            or resolve_media_dir(self._decrypted_dir)
        )
        self.invalidate_caches()

        return {
            "success": success > 0,
            "decrypted": success,
            "copied": copied,
            "failed": failed,
            "decrypted_dir": self._decrypted_dir,
            "media_dir": self._media_dir,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_db_path(self, name: str) -> Optional[str]:
        """Get path to a decrypted database file."""
        if not os.path.isdir(self._decrypted_dir):
            return None
        path = os.path.join(self._decrypted_dir, name)
        return path if os.path.isfile(path) else None

    def _find_avatar_dir(self, root: Optional[str]) -> Optional[str]:
        """Locate an ``Avator``/``Avatar`` directory directly under *root*."""
        if not root or not os.path.isdir(root):
            return None
        base = os.path.basename(os.path.abspath(root)).lower()
        if base in ("avator", "avatar"):
            return os.path.abspath(root)
        try:
            for name in os.listdir(root):
                if name.lower() in ("avator", "avatar"):
                    candidate = os.path.join(root, name)
                    if os.path.isdir(candidate):
                        return candidate
        except OSError:
            return None
        return None

    def _detect_avatar_dir(self) -> Optional[str]:
        """Search for the avatar cache next to the media/db directories."""
        roots: list[str] = []
        for base in (self.media_dir, self._db_dir, self._decrypted_dir):
            if not base:
                continue
            base = os.path.abspath(base)
            roots.extend([base, os.path.dirname(base)])
        seen: set[str] = set()
        for root in roots:
            if root in seen:
                continue
            seen.add(root)
            found = self._find_avatar_dir(root)
            if found:
                return found
        return None

    def _ensure_caches(self) -> None:
        """Build all lazy caches once (never raises)."""
        if self._caches_ready:
            return
        with self._cache_lock:
            if self._caches_ready:
                return
            try:
                self._build_caches()
            except Exception:
                pass
            finally:
                self._caches_ready = True

    def _build_caches(self) -> None:
        user_db = self._get_db_path("user.db")
        session_db = self._get_db_path("session.db")

        if user_db:
            try:
                self._user_names = build_user_names(user_db) or {}
            except Exception:
                self._user_names = {}
            try:
                self._user_info = build_user_info(user_db) or {}
            except Exception:
                self._user_info = {}
        else:
            self._user_names = {}
            self._user_info = {}

        if self._configured_self_id is not None:
            self._self_id = self._configured_self_id
        elif session_db:
            try:
                self._self_id = detect_self_id(session_db)
            except Exception:
                self._self_id = None

        if session_db:
            doc_db = self._get_db_path("tencent_doc_list.db")
            try:
                loaded = load_sessions(
                    session_db,
                    user_db,
                    doc_db,
                    self._self_id,
                )
                self._sessions = list(loaded.get("sessions") or [])
                if self._self_id is None:
                    self._self_id = loaded.get("self_id")
            except Exception:
                self._sessions = []

            # Sessions whose last_message_time is missing would otherwise keep
            # an arbitrary order; backfill from the latest message before the
            # global sort and the id lookup are built.
            try:
                previews = self._batch_previews(self._sessions)
            except Exception:
                previews = {}
            for item in self._sessions:
                if item.get("last_message_time"):
                    continue
                key = (item.get("id") or "", _as_int(item.get("last_message_id")))
                info = previews.get(key)
                if info and info.get("send_time"):
                    item["last_message_time"] = info["send_time"]
            self._sessions.sort(
                key=lambda item: item.get("last_message_time") or 0,
                reverse=True,
            )

            self._sessions_by_id = {
                str(item.get("id")): item for item in self._sessions if item.get("id")
            }
        else:
            self._sessions = []
            self._sessions_by_id = {}

        # Media catalog (needs both the media root and decrypted file.db).
        media_dir = self.media_dir
        file_db = self._get_db_path("file.db")
        if media_dir and file_db:
            try:
                self._media_catalog = MediaCatalog(media_dir, file_db)
            except Exception:
                self._media_catalog = None
        else:
            self._media_catalog = None

        # Voice transcriptions (msg_voice2text, keyed by message/server id).
        self._voice_texts = self._build_voice_texts()

        # Avatars.
        self._avatar_db_path = self._get_db_path("avatar_store_v3.db")
        self._avatar_dir = self._detect_avatar_dir()
        if user_db and self._avatar_dir:
            try:
                self._user_avatar_map = build_avatar_file_map(user_db, self._avatar_dir) or {}
            except Exception:
                self._user_avatar_map = {}
        else:
            self._user_avatar_map = {}

    def _build_voice_texts(self) -> dict[str, str]:
        """Map voice message ids / voice ids to their transcript text."""
        msg_db = self._get_db_path("message.db")
        if not msg_db:
            return {}
        texts: dict[str, str] = {}
        try:
            conn = _connect_ro(msg_db)
        except Exception:
            return texts
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='msg_voice2text'"
            ).fetchone()
            if exists is None:
                return texts
            rows = conn.execute("SELECT message_id, voice_id, text FROM msg_voice2text")
            for row in rows:
                text = str(row["text"] or "").strip()
                if not text:
                    continue
                for key in (row["message_id"], row["voice_id"]):
                    if key not in (None, "", 0, "0"):
                        texts[str(key)] = text
        except Exception:
            pass
        finally:
            conn.close()
        return texts

    def _ensure_user_map(self) -> None:
        """Lazy-load user map for sender name resolution (CLI compatibility)."""
        if self._user_map is not None:
            return
        user_db = self._get_db_path("user.db")
        if user_db:
            try:
                self._user_map = build_user_map(user_db)
            except Exception:
                self._user_map = {}
        else:
            self._user_map = {}

    def _session_member_names(self, conversation_id: str) -> list[str]:
        """Cached, clean display names of a conversation's members."""
        cid = str(conversation_id or "")
        entry = self._member_cache.get(cid)
        if entry is not None and "names" in entry:
            return entry["names"]

        names: list[str] = []
        members: list[dict] = []
        session_db = self._get_db_path("session.db")
        raw: dict[int, str] = {}
        if session_db and cid:
            try:
                raw = get_group_members(session_db, cid) or {}
            except Exception:
                raw = {}
        seen: set[str] = set()
        for uid, nick in raw.items():
            uid_int = _as_int(uid)
            if self._self_id is not None and uid_int == self._self_id:
                continue
            name = self._user_names.get(uid_int or 0) or ""
            if not name and nick and not _is_raw_id(nick):
                name = str(nick).strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
            if uid_int is not None:
                members.append({
                    "user_id": uid_int,
                    "name": name,
                    "nick_name": nick or "",
                })
        self._member_cache[cid] = {"names": names, "members": members}
        return names

    def _infer_session_type(self, conversation_id: str) -> str:
        cid = str(conversation_id or "")
        if cid == "FILEASSIST":
            return "single"
        if cid.startswith("R:"):
            return "group"
        if cid.startswith("S:"):
            return "single"
        if cid.startswith("M:"):
            return "wechat"
        if cid.startswith("O:"):
            return "app"
        if cid.startswith("Y:"):
            return "system"
        if cid.isdigit():
            return "single"
        return "other"

    def _session_summary(self, conversation_id: str) -> dict:
        """Compact session descriptor used inside message payloads."""
        cid = self.resolve_session_id(conversation_id)
        session = self._sessions_by_id.get(cid)
        if session:
            return {
                "id": session.get("id") or cid,
                "name": session.get("name") or "",
                "type": session.get("type") or self._infer_session_type(cid),
                "type_label": session.get("type_label")
                or _TYPE_LABELS.get(session.get("type") or "", session.get("type") or ""),
                "member_count": session.get("member_count") or 0,
            }
        stype = self._infer_session_type(cid)
        return {
            "id": cid,
            "name": "",
            "type": stype,
            "type_label": _TYPE_LABELS.get(stype, stype),
            "member_count": 0,
        }

    @staticmethod
    def _avatar_url(conversation_id: str) -> str:
        if not conversation_id:
            return ""
        return "/api/avatar/" + quote(str(conversation_id), safe=":/_-")

    @staticmethod
    def _preview_from_decoded(decoded: dict, content_type: Any = None) -> tuple[str, str]:
        kind = (decoded or {}).get("kind") or ""
        files = (decoded or {}).get("files") or []
        card = (decoded or {}).get("card") or {}
        text = (decoded or {}).get("text") or ""
        summary = (decoded or {}).get("summary") or ""

        if kind == "image":
            preview = "[图片]"
        elif kind == "file":
            preview = (files[0].get("name") if files else "") or "[文件]"
        elif kind == "voice":
            preview = "[语音]"
        elif kind == "link":
            preview = (card.get("title") or "") or text or "[链接]"
        elif kind == "video":
            preview = (files[0].get("name") if files else "") or "[视频]"
        else:
            preview = summary or text

        preview = " ".join(str(preview or "").split())
        if not preview and content_type is not None:
            # Undecodable but existing messages still need a readable hint.
            ctype = _as_int(content_type)
            preview = "[系统消息]" if ctype is not None and 1000 <= ctype < 1100 else "[消息]"
        if _is_raw_id(preview):
            preview = ""
        return preview[:120], kind

    def _message_columns(self) -> dict[str, set[str]]:
        conn = _connect_ro(self._get_db_path("message.db"))
        try:
            result: dict[str, set[str]] = {}
            for table in MESSAGE_TABLES:
                row = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if row is not None:
                    result[table] = {
                        r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')
                    }
            return result
        finally:
            conn.close()

    @staticmethod
    def _select_expr(available: set[str]) -> str:
        parts = []
        for name in _SELECT_FIELDS:
            if name in available:
                parts.append(f'"{name}" AS "{name}"')
            else:
                parts.append(f'NULL AS "{name}"')
        return ", ".join(parts)

    @staticmethod
    def _row_dict(row: sqlite3.Row, source_table: str) -> dict:
        data = {key: row[key] for key in row.keys()}
        data["source_table"] = source_table
        return data

    def _query_message_rows(
        self,
        message_ids: Optional[list[int]] = None,
        message_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
    ) -> list[dict]:
        """Read raw message rows from every message table (best effort)."""
        msg_db = self._get_db_path("message.db")
        if not msg_db:
            return []
        rows: list[dict] = []
        try:
            conn = _connect_ro(msg_db)
        except Exception:
            return []
        try:
            for table in MESSAGE_TABLES:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if exists is None:
                    continue
                available = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
                expr = self._select_expr(available)
                where: list[str] = []
                params: list[Any] = []
                if message_ids:
                    placeholders = ", ".join("?" for _ in message_ids)
                    where.append(f"message_id IN ({placeholders})")
                    params.extend(int(mid) for mid in message_ids)
                if message_id is not None:
                    where.append("message_id = ?")
                    params.append(int(message_id))
                if conversation_id:
                    where.append("conversation_id = ?")
                    params.append(str(conversation_id))
                sql = f'SELECT {expr} FROM "{table}"'
                if where:
                    sql += " WHERE " + " AND ".join(where)
                try:
                    for row in conn.execute(sql, params):
                        rows.append(self._row_dict(row, table))
                except sqlite3.Error:
                    continue
        finally:
            conn.close()
        return rows

    def _decode_row(self, row: dict) -> dict:
        try:
            return decode_message(
                row.get("content_type"),
                row.get("content"),
                row.get("extra_content"),
            )
        except Exception:
            return {
                "kind": "unknown",
                "text": "",
                "summary": "",
                "quote": None,
                "files": [],
                "card": None,
                "items": [],
            }

    def _batch_previews(self, sessions: list[dict]) -> dict[tuple, dict]:
        """Fetch and decode the last message of each session in one pass."""
        wanted: dict[tuple, int] = {}
        for session in sessions:
            cid = session.get("id")
            mid = _as_int(session.get("last_message_id"))
            if cid and mid is not None:
                wanted[(cid, mid)] = mid

        result: dict[tuple, dict] = {}
        if not wanted:
            return result

        ids = sorted(set(wanted.values()))
        rows = self._query_message_rows(message_ids=ids)
        by_key: dict[tuple, dict] = {}
        for row in rows:
            key = (str(row.get("conversation_id") or ""), _as_int(row.get("message_id")))
            if key in wanted:
                by_key.setdefault(key, row)

        for key, row in by_key.items():
            decoded = self._decode_row(row)
            preview, kind = self._preview_from_decoded(decoded, row.get("content_type"))
            info = {
                "preview": preview,
                "kind": kind,
                "send_time": _as_int(row.get("send_time")),
            }
            result[key] = info
            self._preview_cache[key] = info
            self._message_row_cache[key] = row
        return result

    def _latest_message_row(self, conversation_id: str) -> Optional[dict]:
        """Cheapest possible "latest message" lookup (no COUNT)."""
        msg_db = self._get_db_path("message.db")
        if not msg_db:
            return None
        try:
            conn = _connect_ro(msg_db)
        except Exception:
            return None
        best: Optional[dict] = None
        best_key: tuple = ()
        try:
            for table in MESSAGE_TABLES:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if exists is None:
                    continue
                available = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
                expr = self._select_expr(available)
                row = conn.execute(
                    f'SELECT {expr} FROM "{table}" WHERE conversation_id = ? '
                    "ORDER BY COALESCE(send_time, 0) DESC, "
                    "COALESCE(sequence, 0) DESC, COALESCE(message_id, 0) DESC LIMIT 1",
                    (str(conversation_id),),
                ).fetchone()
                if row is None:
                    continue
                data = self._row_dict(row, table)
                key = (
                    _as_int(data.get("send_time")) or 0,
                    _as_int(data.get("sequence")) or 0,
                    _as_int(data.get("message_id")) or 0,
                )
                if best is None or key > best_key:
                    best = data
                    best_key = key
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        return best

    def _lookup_last_message(self, conversation_id: str, message_id: Optional[int]) -> Optional[dict]:
        """Fallback single lookup when the batch query did not match."""
        key = (str(conversation_id or ""), _as_int(message_id))
        cached = self._preview_cache.get(key)
        if cached is not None:
            return cached

        row = None
        if message_id is not None:
            matches = self._query_message_rows(
                message_id=int(message_id), conversation_id=conversation_id
            )
            if matches:
                row = matches[0]

        if row is None:
            row = self._latest_message_row(conversation_id)
        if row is None:
            return None

        decoded = self._decode_row(row)
        preview, kind = self._preview_from_decoded(decoded, row.get("content_type"))
        info = {
            "preview": preview,
            "kind": kind,
            "send_time": _as_int(row.get("send_time")),
        }
        self._preview_cache[key] = info
        self._message_row_cache[key] = row
        return info

    def _enrich_session_page(self, sessions: list[dict]) -> list[dict]:
        batch = self._batch_previews(sessions)
        enriched: list[dict] = []
        for session in sessions:
            item = dict(session)
            cid = item.get("id") or ""
            mid = _as_int(item.get("last_message_id"))
            info = batch.get((cid, mid))
            if info is None and mid is not None and mid > 0:
                info = self._lookup_last_message(cid, mid)

            item["avatar_cid"] = cid
            item["avatar_url"] = self._avatar_url(cid)
            item["last_preview"] = (info or {}).get("preview", "")
            item["last_preview_kind"] = (info or {}).get("kind", "")
            if not item.get("last_message_time") and info:
                if info.get("send_time"):
                    item["last_message_time"] = info["send_time"]
            enriched.append(item)
        return enriched

    def _file_rows_for(self, message_id: Optional[int]) -> list[dict]:
        """file.db attachment rows for one message (cached)."""
        if message_id is None:
            return []
        mid = _as_int(message_id)
        if mid is None:
            return []
        cached = self._file_rows_cache.get(mid)
        if cached is not None:
            return cached
        catalog = self._media_catalog
        files: list[dict] = []
        if catalog is not None:
            try:
                files = catalog.get_files_for_message(mid)
            except Exception:
                files = []
        self._file_rows_cache[mid] = files
        return files

    def _prefetch_file_rows(self, message_ids: list[Any]) -> None:
        """Batch-load file.db rows for a page of messages in a single query."""
        catalog = self._media_catalog
        file_db = self._get_db_path("file.db")
        if catalog is None or not file_db:
            return
        wanted: list[int] = []
        for value in message_ids:
            mid = _as_int(value)
            if mid is not None and mid not in self._file_rows_cache and mid not in wanted:
                wanted.append(mid)
        if not wanted:
            return

        rows: list[sqlite3.Row] = []
        try:
            conn = _connect_ro(file_db)
        except Exception:
            return
        try:
            placeholders = ", ".join("?" for _ in wanted)
            rows = conn.execute(
                "SELECT origin, message_id, file_index, message_type, extension_type, "
                "server_id, name, size, md5 "
                f"FROM file_table4 WHERE message_id IN ({placeholders}) "
                "ORDER BY file_index, origin",
                wanted,
            ).fetchall()
        except sqlite3.Error:
            rows = []
        finally:
            conn.close()

        grouped: dict[int, list[dict]] = {}
        for row in rows:
            mid = _as_int(row["message_id"])
            if mid is None:
                continue
            name = row["name"] or ""
            kind = guess_media_kind(
                name, row["message_type"] or 0, row["extension_type"] or 0
            )
            try:
                path = catalog.find_file(name)
            except Exception:
                path = None
            grouped.setdefault(mid, []).append({
                "message_id": mid,
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

        for mid in wanted:
            self._file_rows_cache[mid] = grouped.get(mid, [])

    def _merge_media(
        self,
        message: dict,
        decoded: dict,
        file_rows: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Merge decoded attachment metadata with file.db rows (no local paths)."""
        catalog = self._media_catalog
        message_id = _as_int(message.get("message_id"))
        if file_rows is None:
            file_rows = self._file_rows_for(message_id)

        media: list[dict] = []
        seen: set[tuple] = set()
        for file_row in file_rows:
            name = file_row.get("name") or ""
            server_id = file_row.get("server_id") or ""
            seen.add((name.lower(), server_id))
            media.append({
                "index": file_row.get("index"),
                "name": name,
                "size": file_row.get("size") or 0,
                "kind": file_row.get("kind") or "file",
                "exists": bool(file_row.get("exists")),
                "mimetype": _guess_mimetype(name),
            })

        decoded_files = (decoded or {}).get("files") or []
        if not decoded_files and file_rows:
            return media

        for file_info in decoded_files:
            name = file_info.get("name") or ""
            server_id = file_info.get("server_id") or ""
            key = (name.lower(), server_id)
            if key in seen and (name or server_id):
                continue
            seen.add(key)
            exists = False
            if catalog is not None and name:
                try:
                    exists = bool(catalog.find_file(name))
                except Exception:
                    exists = False
            media.append({
                "index": None,
                "name": name,
                "size": file_info.get("size") or 0,
                "kind": file_info.get("kind") or "file",
                "exists": exists,
                "mimetype": _guess_mimetype(name),
            })
        return media

    def _enrich_forward_items(self, items: list[Any]) -> list[dict]:
        """Copy forwarded-chat items and annotate their files with local state."""
        enriched: list[dict] = []
        catalog = self._media_catalog
        for item in items or []:
            if not isinstance(item, dict):
                enriched.append(item)
                continue
            copied = dict(item)
            files = item.get("files")
            if not files:
                enriched.append(copied)
                continue
            new_files: list[dict] = []
            for file_info in files:
                if not isinstance(file_info, dict):
                    new_files.append(file_info)
                    continue
                file_copy = dict(file_info)
                name = file_copy.get("name") or ""
                try:
                    file_copy["size"] = int(file_copy.get("size") or 0)
                except (TypeError, ValueError):
                    file_copy["size"] = 0
                file_copy["mimetype"] = _guess_mimetype(name)
                exists = False
                if catalog is not None and name:
                    try:
                        exists = bool(catalog.find_file(name))
                    except Exception:
                        exists = False
                file_copy["exists"] = exists
                new_files.append(file_copy)
            copied["files"] = new_files
            enriched.append(copied)
        return enriched

    def _enrich_message(self, message: dict) -> dict:
        """Add sender, self-flag, decoded fields and media metadata."""
        msg = dict(message)
        decoded = msg.get("decoded")
        if not isinstance(decoded, dict):
            decoded = self._decode_row(msg)

        sender_id = _as_int(msg.get("sender_id"))
        self_id = self._self_id
        sender_name = self._user_names.get(sender_id, "") if sender_id is not None else ""

        msg["sender_id"] = sender_id
        msg["sender_name"] = sender_name
        msg["is_send"] = bool(sender_id is not None and self_id is not None
                             and sender_id == self_id)
        msg["text"] = decoded.get("text") or ""
        msg["summary"] = decoded.get("summary") or ""
        msg["kind"] = decoded.get("kind") or ""
        msg["quote"] = decoded.get("quote")
        msg["card"] = decoded.get("card")
        msg["items"] = self._enrich_forward_items(decoded.get("items") or [])
        msg["media"] = self._merge_media(msg, decoded)
        if msg["kind"] == "voice" and not msg["text"] and self._voice_texts:
            keys = [str(msg.get("message_id") or "")]
            for item in msg["media"] or []:
                keys.append(str(item.get("server_id") or ""))
            transcript = next((self._voice_texts[k] for k in keys if k in self._voice_texts), "")
            if transcript:
                msg["text"] = transcript
                if msg["summary"] in ("", "[语音]"):
                    msg["summary"] = "[语音] " + transcript
        msg["sender_avatar"] = (
            f"/api/avatar/user/{sender_id}" if sender_id is not None else ""
        )
        return msg

    def _total_message_count(self) -> Optional[int]:
        msg_db = self._get_db_path("message.db")
        if not msg_db:
            return None
        total = 0
        try:
            conn = _connect_ro(msg_db)
        except Exception:
            return None
        try:
            for table in MESSAGE_TABLES:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if exists is None:
                    continue
                total += int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        except Exception:
            return None
        finally:
            conn.close()
        return total

    def _filter_sessions(
        self,
        sessions: list[dict],
        keyword: Optional[str],
        session_type: Optional[str],
    ) -> list[dict]:
        filtered = sessions

        if keyword:
            needle = str(keyword).strip().casefold()
            if needle:
                matches = []
                for session in filtered:
                    haystack = [session.get("name") or ""]
                    cid = session.get("id") or ""
                    haystack.extend(self._session_member_names(cid))
                    if any(needle in item.casefold() for item in haystack if item):
                        matches.append(session)
                filtered = matches

        if session_type:
            lowered = str(session_type).strip().lower()
            if lowered in ("", "all", "*"):
                return filtered
            prefix = _LEGACY_TYPE_PREFIXES.get(lowered)
            if prefix is None and len(lowered) == 1 and lowered in ("r", "s", "m", "o", "y"):
                prefix = lowered.upper() + ":"
            if prefix is not None:
                return [
                    item for item in filtered
                    if str(item.get("id") or "").upper().startswith(prefix)
                ]
            wanted = _TYPE_ALIASES.get(lowered, lowered)
            return [item for item in filtered if item.get("type") == wanted]

        return filtered

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        keyword: Optional[str] = None,
        session_type: Optional[str] = None,
    ) -> list[dict]:
        """List WeCom sessions/conversations (CLI compatible list result)."""
        page = self.list_sessions_page(
            limit=limit, offset=offset, keyword=keyword, session_type=session_type
        )
        return page.get("sessions", [])

    def list_sessions_page(
        self,
        limit: int = 50,
        offset: int = 0,
        keyword: Optional[str] = None,
        session_type: Optional[str] = None,
    ) -> dict:
        """Paginated session list with preview and avatar metadata."""
        try:
            limit = max(0, int(limit or 0))
        except (TypeError, ValueError):
            limit = 0
        try:
            offset = max(0, int(offset or 0))
        except (TypeError, ValueError):
            offset = 0

        try:
            self._ensure_caches()
            filtered = self._filter_sessions(
                list(self._sessions), keyword, session_type
            )
            total = len(filtered)
            page_sessions = filtered[offset:offset + limit]
            enriched = self._enrich_session_page(page_sessions)
            return {
                "total": total,
                "has_more": offset + len(enriched) < total,
                "offset": offset,
                "limit": limit,
                "sessions": enriched,
            }
        except Exception:
            return {
                "total": 0,
                "has_more": False,
                "offset": offset,
                "limit": limit,
                "sessions": [],
            }

    def session_detail(self, conversation_id: str) -> dict:
        """Full detail (including members) for one conversation."""
        try:
            self._ensure_caches()
            cid = self.resolve_session_id(conversation_id)
            session_db = self._get_db_path("session.db")
            if not session_db:
                return {}
            detail = get_session_detail(
                session_db,
                cid,
                user_db_path=self._get_db_path("user.db"),
                doc_db_path=self._get_db_path("tencent_doc_list.db"),
                self_id=self._self_id,
            ) or {}
            if not detail:
                cached = self._sessions_by_id.get(cid)
                if not cached:
                    return {}
                detail = {
                    "id": cached.get("id"),
                    "name": cached.get("name") or "",
                    "type": cached.get("type") or self._infer_session_type(cid),
                    "type_label": cached.get("type_label") or "",
                    "member_count": cached.get("member_count") or 0,
                    "members": [],
                    "is_external": cached.get("is_external") or False,
                    "create_time": None,
                    "last_message_time": cached.get("last_message_time"),
                    "self_id": self._self_id,
                }

            detail["self_id"] = self._self_id
            detail["avatar_cid"] = detail.get("id") or cid
            detail["avatar_url"] = self._avatar_url(detail["avatar_cid"])
            detail["member_names"] = self._session_member_names(detail["avatar_cid"])
            detail["type"] = detail.get("type") or self._infer_session_type(cid)
            detail["type_label"] = detail.get("type_label") or _TYPE_LABELS.get(
                detail["type"], detail["type"]
            )
            members = detail.get("members") or []
            if members:
                entry = self._member_cache.setdefault(
                    detail["avatar_cid"], {"names": detail["member_names"], "members": []}
                )
                entry["members"] = members
            return detail
        except Exception:
            return {}

    def resolve_session_id(self, conversation_id: str) -> str:
        """Map a numeric conversation alias to its ``R:`` id when one exists."""
        try:
            if conversation_id is None:
                return ""
            cid = str(conversation_id).strip()
            if not cid:
                return cid
            self._ensure_caches()
            if cid.isdigit() and f"R:{cid}" in self._sessions_by_id:
                return f"R:{cid}"
            return cid
        except Exception:
            return str(conversation_id or "")

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def query_messages_page(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
        types: Any = None,
        msg_type: Optional[int] = None,
        keyword: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        anchor_message_id: Optional[int] = None,
    ) -> dict:
        """Paginated, fully enriched messages for one conversation."""
        try:
            limit = max(0, int(limit or 0))
        except (TypeError, ValueError):
            limit = 0
        try:
            offset = max(0, int(offset or 0))
        except (TypeError, ValueError):
            offset = 0

        try:
            self._ensure_caches()
            cid = self.resolve_session_id(conversation_id)
            msg_db = self._get_db_path("message.db")
            conversation = self._session_summary(cid)
            if not msg_db:
                return {
                    "messages": [],
                    "total": 0,
                    "has_more": False,
                    "offset": offset,
                    "anchor_offset": None,
                    "self_id": self._self_id,
                    "conversation": conversation,
                    "limit": limit,
                }

            result = db_query_messages(
                msg_db,
                cid,
                limit=limit,
                offset=offset,
                types=types,
                msg_type=msg_type,
                keyword=keyword,
                start_time=start_time,
                end_time=end_time,
                anchor_message_id=anchor_message_id,
            )
            raw_messages = result.get("messages", [])
            self._prefetch_file_rows([m.get("message_id") for m in raw_messages])
            messages = [self._enrich_message(message) for message in raw_messages]
            return {
                "messages": messages,
                "total": result.get("total", 0),
                "has_more": result.get("has_more", False),
                "offset": result.get("offset", offset),
                "anchor_offset": result.get("anchor_offset"),
                "self_id": self._self_id,
                "conversation": conversation,
                "limit": limit,
            }
        except Exception:
            return {
                "messages": [],
                "total": 0,
                "has_more": False,
                "offset": offset,
                "anchor_offset": None,
                "self_id": self._self_id,
                "conversation": {"id": str(conversation_id or "")},
                "limit": limit,
            }

    def get_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
        since: Optional[int] = None,
        until: Optional[int] = None,
    ) -> list[dict]:
        """Get messages for a conversation (CLI compatible list result).

        ``since`` is inclusive (>=), ``until`` exclusive (<).
        """
        page = self.query_messages_page(
            conversation_id,
            limit=limit,
            offset=offset,
            start_time=since,
            end_time=until,
        )
        return page.get("messages", [])

    def message_by_id(self, conversation_id: str, message_id: int) -> Optional[dict]:
        """Return one fully enriched message or ``None``."""
        try:
            self._ensure_caches()
            cid = self.resolve_session_id(conversation_id)
            mid = _as_int(message_id)
            if mid is None:
                return None
            rows = self._query_message_rows(message_id=mid, conversation_id=cid)
            if not rows:
                return None
            row = rows[0]
            message = {
                "message_id": row.get("message_id"),
                "server_id": row.get("server_id"),
                "sequence": row.get("sequence"),
                "sender_id": row.get("sender_id"),
                "conversation_id": row.get("conversation_id"),
                "content_type": row.get("content_type"),
                "send_time": row.get("send_time"),
                "flag": row.get("flag"),
                "from_app_id": row.get("from_app_id"),
                "source_table": row.get("source_table"),
                "decoded": self._decode_row(row),
            }
            decoded = message["decoded"]
            message["content"] = decoded.get("text") or decoded.get("summary") or ""
            return self._enrich_message(message)
        except Exception:
            return None

    def search_messages(
        self,
        keyword: str,
        conversation_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        types: Any = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[dict]:
        """Search messages by keyword (CLI compatible list result)."""
        page = self.search_messages_page(
            keyword,
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
            types=types,
            start_time=start_time,
            end_time=end_time,
        )
        return page.get("results", [])

    def search_messages_page(
        self,
        keyword: str,
        conversation_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        types: Any = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> dict:
        """Paginated search results enriched with session and sender names."""
        try:
            limit = max(0, int(limit or 0))
        except (TypeError, ValueError):
            limit = 0
        try:
            offset = max(0, int(offset or 0))
        except (TypeError, ValueError):
            offset = 0

        empty = {
            "total": 0,
            "has_more": False,
            "offset": offset,
            "limit": limit,
            "results": [],
        }
        try:
            self._ensure_caches()
            msg_db = self._get_db_path("message.db")
            if not msg_db:
                return empty
            cid = self.resolve_session_id(conversation_id) if conversation_id else None
            raw = db_search_messages(
                msg_db,
                keyword,
                conversation_id=cid,
                limit=limit,
                offset=offset,
                types=types,
                start_time=start_time,
                end_time=end_time,
            )
            raw_results = raw.get("results", [])
            self._prefetch_file_rows([m.get("message_id") for m in raw_results])
            results: list[dict] = []
            for message in raw_results:
                msg = self._enrich_message(message)
                session = self._session_summary(msg.get("conversation_id") or "")
                snippet = " ".join(str(msg.get("snippet") or "").split())
                if not snippet:
                    snippet = (msg.get("summary") or msg.get("text") or "")[:120]
                if _is_raw_id(snippet):
                    snippet = ""
                msg["session_id"] = msg.get("conversation_id") or ""
                msg["session_name"] = session.get("name") or ""
                msg["session_type"] = session.get("type") or ""
                msg["session_type_label"] = session.get("type_label") or ""
                msg["snippet"] = snippet
                results.append(msg)

            results.sort(
                key=lambda item: (
                    item.get("send_time") or 0,
                    item.get("message_id") or 0,
                ),
                reverse=True,
            )
            return {
                "total": raw.get("total", 0),
                "has_more": raw.get("has_more", False),
                "offset": offset,
                "limit": limit,
                "results": results,
            }
        except Exception:
            return empty

    def get_message_count(
        self,
        conversation_id: str,
        types: Any = None,
        keyword: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> int:
        """Total number of messages matching the query filters."""
        try:
            self._ensure_caches()
            msg_db = self._get_db_path("message.db")
            if not msg_db:
                return 0
            cid = self.resolve_session_id(conversation_id)
            return int(
                db_get_message_count(
                    msg_db,
                    cid,
                    types=types,
                    keyword=keyword,
                    start_time=start_time,
                    end_time=end_time,
                )
            )
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Media and avatars
    # ------------------------------------------------------------------

    def get_media(self, message_id: int, index: int = 0) -> Optional[dict]:
        """Return attachment metadata (never an externally supplied path)."""
        try:
            self._ensure_caches()
            mid = _as_int(message_id)
            idx = _as_int(index)
            if mid is None or idx is None or idx < 0:
                return None
            catalog = self._media_catalog

            if catalog is not None:
                try:
                    item = catalog.get_file_by_index(mid, idx)
                except Exception:
                    item = None
                if item is not None:
                    name = item.get("name") or ""
                    return {
                        "path": item.get("path"),
                        "name": name,
                        "size": item.get("size") or 0,
                        "kind": item.get("kind") or "file",
                        "mimetype": _guess_mimetype(name),
                        "exists": bool(item.get("exists")),
                    }

            cached = self._decoded_files_cache.get(mid)
            if cached is None:
                rows = self._query_message_rows(message_id=mid)
                files: list[dict] = []
                for row in rows:
                    decoded = self._decode_row(row)
                    files.extend(decoded.get("files") or [])
                self._decoded_files_cache[mid] = files
                cached = files
            if idx >= len(cached):
                return None

            file_info = cached[idx]
            name = file_info.get("name") or ""
            path = None
            if catalog is not None and name:
                try:
                    path = catalog.find_file(name)
                except Exception:
                    path = None
            return {
                "path": path,
                "name": name,
                "size": file_info.get("size") or 0,
                "kind": file_info.get("kind") or "file",
                "mimetype": _guess_mimetype(name),
                "exists": bool(path and os.path.isfile(path)),
            }
        except Exception:
            return None

    def media_by_name(self, name: str) -> Optional[dict]:
        """Return attachment metadata for an indexed media filename.

        Only filenames that are already present in the local media index are
        resolved; a caller supplied path is never opened directly.
        """
        try:
            self._ensure_caches()
            catalog = self._media_catalog
            if catalog is None or not name:
                return None
            path = catalog.find_file(name)
            if not path or not os.path.isfile(path):
                return None
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            basename = os.path.basename(path)
            extension = os.path.splitext(basename)[1].lower()
            if extension in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                kind = "image"
            elif extension in (".mp4", ".mov"):
                kind = "video"
            elif extension in (".silk", ".slk", ".amr"):
                kind = "voice"
            else:
                kind = "file"
            return {
                "path": path,
                "name": basename,
                "size": size,
                "kind": kind,
                "mimetype": _guess_mimetype(basename),
                "exists": True,
            }
        except Exception:
            return None

    @staticmethod
    def media_url(message_id: int, index: int = 0) -> str:
        """URL that serves the attachment through the web API."""
        return f"/api/media/{message_id}?i={index}"

    def avatar_file_path(self, user_id: int) -> Optional[str]:
        """Local avatar file path for *user_id* (internal use only)."""
        try:
            self._ensure_caches()
            uid = _as_int(user_id)
            if uid is None:
                return None
            return self._user_avatar_map.get(uid)
        except Exception:
            return None

    def _avatar_for_user(self, user_id: Any) -> tuple[Optional[bytes], str]:
        uid = _as_int(user_id)
        if uid is None:
            return None, "image/png"
        cache_key = ("user", uid)
        if cache_key in self._avatar_bytes_cache:
            return self._avatar_bytes_cache[cache_key]

        path = self._user_avatar_map.get(uid)
        if not path or not os.path.isfile(path):
            result = (None, "image/png")
        else:
            try:
                size = os.path.getsize(path)
                if size >= _AVATAR_MAX_BYTES:
                    result = (None, "image/png")
                else:
                    with open(path, "rb") as handle:
                        data = handle.read()
                    mimetype = mimetypes.guess_type(path)[0] or _sniff_mimetype(data)
                    result = (data, mimetype)
            except OSError:
                result = (None, "image/png")
        self._avatar_bytes_cache[cache_key] = result
        return result

    def avatar_bytes(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> tuple[Optional[bytes], str]:
        """Return ``(bytes, mimetype)`` for a conversation or user avatar."""
        try:
            self._ensure_caches()

            if conversation_id is not None:
                cid = self.resolve_session_id(conversation_id)
                cache_key = ("conversation", cid)
                if cache_key in self._avatar_bytes_cache:
                    return self._avatar_bytes_cache[cache_key]

                buffer = None
                avatar_db = self._avatar_db_path
                if avatar_db:
                    try:
                        buffer = get_avatar_buffer(avatar_db, cid)
                    except Exception:
                        buffer = None
                if buffer:
                    result = (bytes(buffer), _sniff_mimetype(bytes(buffer)))
                elif cid.startswith("S:"):
                    parts = cid[2:].split("_")
                    other = None
                    for part in parts:
                        uid = _as_int(part)
                        if uid is not None and uid != self._self_id:
                            other = uid
                            break
                    result = self._avatar_for_user(other) if other is not None else (None, "image/png")
                elif cid.isdigit():
                    result = self._avatar_for_user(cid)
                else:
                    result = (None, "image/png")
                self._avatar_bytes_cache[cache_key] = result
                return result

            if user_id is not None:
                return self._avatar_for_user(user_id)

            return None, "image/png"
        except Exception:
            return None, "image/png"

    # ------------------------------------------------------------------
    # Contacts and legacy helpers
    # ------------------------------------------------------------------

    def contacts(
        self,
        keyword: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """List contacts."""
        try:
            user_db = self._get_db_path("user.db")
            if not user_db:
                return []
            return list_contacts(user_db, keyword=keyword, limit=limit, offset=offset)
        except Exception:
            return []

    def group_members(self, conversation_id: str) -> dict[int, str]:
        """Get group members with nicknames."""
        try:
            session_db = self._get_db_path("session.db")
            if not session_db:
                return {}
            return get_group_members(session_db, conversation_id)
        except Exception:
            return {}

    def session_count(self) -> int:
        """Get total session count (raw conversation_table rows)."""
        try:
            session_db = self._get_db_path("session.db")
            if not session_db:
                return 0
            return get_session_count(session_db)
        except Exception:
            return 0

    def message_count(self, conversation_id: str) -> int:
        """Get message count for a conversation."""
        try:
            msg_db = self._get_db_path("message.db")
            if not msg_db:
                return 0
            return db_get_message_count(msg_db, conversation_id)
        except Exception:
            return 0
