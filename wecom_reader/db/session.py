"""Session (会话) queries for decrypted WeCom databases.

Conversation names are only partially stored in ``conversation_table``:
``S:`` rows are always empty, many ``R:`` groups have no name, and ``M:`` /
``O:`` / ``Y:`` ids are meaningless on their own.  This module resolves every
row into a human-readable name using ``conversation_user_table``, user.db and
tencent_doc_list.db, and merges legacy numeric conversation ids into their
``R:`` alias when one exists.
"""

import os
import re
import sqlite3
from typing import Optional

from .contact import build_user_names, detect_self_id

_TYPE_LABELS = {
    "group": "群聊",
    "single": "单聊",
    "wechat": "微信",
    "app": "应用",
    "system": "系统",
    "external": "外部会话",
    "other": "其它",
}

_SPECIAL_NAMES = {
    "FILEASSIST": "文件传输助手",
    "APPROVAL": "审批",
    "ANNOUNCE": "公告",
    "SERVICE_NOTIFICATION": "服务通知",
    "MAIL": "邮件",
    "WORK_JOURNAL": "汇报",
    "HIDDEN_APP_CONVERGE": "应用消息",
}

_SPECIAL_TYPES = {
    "FILEASSIST": "single",
    "APPROVAL": "app",
    "ANNOUNCE": "system",
    "SERVICE_NOTIFICATION": "system",
    "MAIL": "app",
    "WORK_JOURNAL": "app",
    "HIDDEN_APP_CONVERGE": "app",
}

_SYSTEM_NAMES = {
    "Y:10081": "微盘",
    "Y:10034": "同事吧",
    "Y:10079": "微文档",
    "Y:10085": "会议",
    "Y:10077": "紧急通知",
}

_DOC_ID_RE = re.compile(r"[a-z]\d_[A-Za-z0-9_-]{8,}")
_RAW_ID_RE = re.compile(r"^(?:[RSMOY]:|\d{8,}$|[A-Z][A-Z_]{3,}$)")
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


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a decrypted database read-only (avoids creating -wal/-shm files)."""
    path = str(db_path)
    uri = "file:" + path.replace("\\", "/").replace("?", "%3F").replace("#", "%23")
    params = "?mode=ro"
    wal = path + "-wal"
    # Fully immutable when there is no pending WAL, so SQLite creates no sidecars.
    if not os.path.exists(wal) or os.path.getsize(wal) == 0:
        params += "&immutable=1"
    try:
        conn = sqlite3.connect(uri + params, uri=True)
    except sqlite3.Error:
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _pick(available: set[str], *candidates: str) -> Optional[str]:
    for name in candidates:
        if name in available:
            return name
    return None


def _text(value) -> str:
    """Decode/Normalise a possibly-binary, possibly-NULL text field."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", "replace")
        except Exception:
            return ""
    return str(value).strip()


def _clean_name(value) -> str:
    """Return a display name, discarding raw conversation/user ids."""
    name = _text(value)
    if not name or _RAW_ID_RE.match(name):
        return ""
    return name


def _sibling(db_path: Optional[str], filename: str) -> Optional[str]:
    """Locate a companion database next to ``db_path`` (None when absent)."""
    if not db_path:
        return None
    candidate = os.path.join(os.path.dirname(os.path.abspath(db_path)), filename)
    return candidate if os.path.isfile(candidate) else None


def _classify_session(cid: str, is_external: bool = False) -> str:
    """Classify a conversation id into group/single/wechat/app/system/..."""
    cid = _text(cid)
    if not cid:
        return "other"
    if cid in _SPECIAL_TYPES:
        return _SPECIAL_TYPES[cid]
    if is_external:
        return "external"
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


def _load_conversations(conn: sqlite3.Connection) -> list[dict]:
    """Read every conversation row, tolerating missing columns."""
    if not _table_exists(conn, "conversation_table"):
        return []
    available = _columns(conn, "conversation_table")
    if "id" not in available:
        return []

    wanted = {
        "con_numeric_id": "con_numeric_id",
        "name": "name",
        "create_time": "create_time",
        "last_message_time": "last_message_time",
        "last_message_id": "last_message_id",
        "roomname_remark": "roomname_remark",
        "type_content": "type_content",
    }
    expr = []
    for logical, column in wanted.items():
        expr.append(f'"{column}" AS "{logical}"' if column in available else f'NULL AS "{logical}"')
    expr.insert(0, 'id AS "id"')

    rows = []
    for row in conn.execute(f"SELECT {', '.join(expr)} FROM conversation_table"):
        rows.append({
            "id": _text(row["id"]),
            "con_numeric_id": row["con_numeric_id"],
            "name": _text(row["name"]),
            "create_time": row["create_time"],
            "last_message_time": row["last_message_time"],
            "last_message_id": row["last_message_id"],
            "roomname_remark": _text(row["roomname_remark"]),
            "type_content": row["type_content"],
        })
    return [row for row in rows if row["id"]]


def _load_members(conn: sqlite3.Connection) -> dict[str, list[tuple[int, str]]]:
    """Load conversation_id -> [(user_id, nick_name)]."""
    members: dict[str, list[tuple[int, str]]] = {}
    if not _table_exists(conn, "conversation_user_table"):
        return members
    available = _columns(conn, "conversation_user_table")
    if "conversation_id" not in available or "user_id" not in available:
        return members
    nick_expr = '"nick_name"' if "nick_name" in available else "NULL"
    for row in conn.execute(
        f'SELECT conversation_id, user_id, {nick_expr} AS nick_name FROM conversation_user_table'
    ):
        cid = _text(row["conversation_id"])
        if not cid:
            continue
        try:
            uid = int(row["user_id"])
        except (TypeError, ValueError):
            continue
        members.setdefault(cid, []).append((uid, _text(row["nick_name"])))
    return members


def _read_varint(raw: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while pos < len(raw) and shift < 64:
        byte = raw[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
    raise ValueError("truncated varint")


def _proto_strings(raw) -> list[str]:
    """Extract UTF-8 string fields from a protobuf blob (best effort)."""
    if not isinstance(raw, bytes) or not raw:
        return []
    strings = []
    pos = 0
    try:
        while pos < len(raw):
            tag = raw[pos]
            pos += 1
            wire = tag & 0x07
            if wire == 0:
                _, pos = _read_varint(raw, pos)
            elif wire == 2:
                length, pos = _read_varint(raw, pos)
                if length < 0 or pos + length > len(raw):
                    break
                payload = raw[pos:pos + length]
                pos += length
                try:
                    strings.append(payload.decode("utf-8"))
                except UnicodeDecodeError:
                    continue
            elif wire == 1:
                pos += 8
            elif wire == 5:
                pos += 4
            else:
                break
    except Exception:
        pass
    return strings


def _parse_type_content(raw) -> tuple[str, str]:
    """Return ``(doc_id, title)`` parsed from conversation.type_content."""
    strings = _proto_strings(raw)
    if not strings and isinstance(raw, bytes) and raw:
        try:
            strings = [raw.decode("utf-8")]
        except UnicodeDecodeError:
            strings = []
    elif not strings and isinstance(raw, str):
        strings = [raw]

    doc_id = ""
    title = ""
    for text in strings:
        chunk = text.strip()
        if not chunk:
            continue
        match = _DOC_ID_RE.search(chunk)
        if match and not doc_id:
            doc_id = match.group(0)
        if "://" in chunk:
            continue
        if match and match.group(0) == chunk:
            continue
        if len(chunk) > 120:
            continue
        title = chunk
    return doc_id, _clean_name(title)


def _load_doc_titles(doc_db_path: Optional[str]) -> dict[str, str]:
    """Build doc_id -> title from tencent_doc_list.db (table names vary)."""
    titles: dict[str, str] = {}
    if not doc_db_path or not os.path.isfile(doc_db_path):
        return titles
    try:
        conn = _connect(doc_db_path)
    except Exception:
        return titles
    try:
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
        for table in tables:
            available = _columns(conn, table)
            id_col = _pick(available, "id", "doc_id")
            title_col = _pick(available, "title", "doc_title")
            if not id_col or not title_col:
                continue
            try:
                for row in conn.execute(
                    f'SELECT "{id_col}" AS doc_id, "{title_col}" AS title FROM "{table}" '
                    f'WHERE "{title_col}" IS NOT NULL'
                ):
                    doc_id = _text(row["doc_id"])
                    title = _clean_name(row["title"])
                    if doc_id and title:
                        titles.setdefault(doc_id, title)
            except Exception:
                continue
    except Exception:
        return titles
    finally:
        conn.close()
    return titles


def _member_names(
    members: list[tuple[int, str]],
    user_names: dict[int, str],
    self_id: Optional[int],
) -> list[str]:
    """Ordered, de-duplicated member display names (self excluded)."""
    names: list[str] = []
    seen: set[str] = set()
    for uid, nick in members:
        if self_id is not None and uid == self_id:
            continue
        name = user_names.get(uid) or _clean_name(nick)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _compose_group_name(names: list[str], total: int) -> str:
    if not names:
        return f"群聊 · {total} 人" if total else "群聊"
    head = "、".join(names[:3])
    if total > 3:
        return f"{head} 等 {total} 人"
    return head


def _resolve_name(
    row: dict,
    members: list[tuple[int, str]],
    user_names: dict[int, str],
    self_id: Optional[int],
    doc_titles: dict[str, str],
) -> str:
    cid = row["id"]
    raw_name = _clean_name(row["name"])
    remark = _clean_name(row["roomname_remark"])
    total = len(members)

    if cid in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[cid]

    if cid.startswith("R:"):
        if remark:
            return remark
        if raw_name:
            return raw_name
        names = _member_names(members, user_names, self_id)
        return _compose_group_name(names, total)

    if cid.startswith("S:"):
        parts = cid[2:].split("_")
        uids = [int(part) for part in parts if part.isdigit()]
        candidates = [uid for uid in uids if self_id is None or uid != self_id]
        for uid in candidates:
            if user_names.get(uid):
                return user_names[uid]
        for uid, _nick in members:
            if self_id is not None and uid == self_id:
                continue
            name = user_names.get(uid)
            if name:
                return name
        for uid, nick in members:
            if self_id is not None and uid == self_id:
                continue
            if _clean_name(nick):
                return _clean_name(nick)
        return "单聊"

    if cid.startswith("M:"):
        doc_id, title = _parse_type_content(row["type_content"])
        if title:
            return title
        if doc_id and doc_titles.get(doc_id):
            return doc_titles[doc_id]
        return "微信会话"

    if cid.startswith("O:"):
        if raw_name:
            return raw_name
        _doc_id, title = _parse_type_content(row["type_content"])
        return title or "应用消息"

    if cid.startswith("Y:"):
        return raw_name or _SYSTEM_NAMES.get(cid) or "系统消息"

    if cid.isdigit():
        num = int(cid)
        if user_names.get(num):
            return user_names[num]
        return "外部会话"

    return raw_name or "其它会话"


def _load_all(
    session_db_path: str,
    user_db_path: Optional[str] = None,
    doc_db_path: Optional[str] = None,
    self_id: Optional[int] = None,
) -> tuple[list[dict], dict[str, list[str]], Optional[int]]:
    """Resolve every conversation (merged, sorted, pagination-ready)."""
    if not session_db_path or not os.path.isfile(session_db_path):
        return [], {}, None

    user_db_path = user_db_path or _sibling(session_db_path, "user.db")
    doc_db_path = doc_db_path or _sibling(session_db_path, "tencent_doc_list.db")

    user_names: dict[int, str] = {}
    if user_db_path and os.path.isfile(user_db_path):
        try:
            user_names = build_user_names(user_db_path) or {}
        except Exception:
            user_names = {}
    doc_titles = _load_doc_titles(doc_db_path)

    conn = _connect(session_db_path)
    try:
        rows = _load_conversations(conn)
        members_map = _load_members(conn)
        if self_id is None:
            self_id = detect_self_id(session_db_path)
    finally:
        conn.close()

    existing_ids = {row["id"] for row in rows}
    sessions: list[dict] = []
    search_names: dict[str, list[str]] = {}

    for row in rows:
        cid = row["id"]
        if cid.isdigit() and f"R:{cid}" in existing_ids:
            # Legacy duplicate of a real group: keep only the R: row.
            continue

        members = members_map.get(cid, [])
        if cid.isdigit() and not user_names.get(int(cid)):
            is_external = True
        else:
            is_external = False
        stype = _classify_session(cid, is_external=is_external)
        name = _resolve_name(row, members, user_names, self_id, doc_titles)

        sessions.append({
            "id": cid,
            "name": name,
            "type": stype,
            "type_label": _TYPE_LABELS.get(stype, stype),
            "last_message_time": row["last_message_time"],
            "last_message_id": row["last_message_id"],
            "member_count": len(members),
            "is_external": is_external,
            "raw_name": row["name"],
            "raw_roomname_remark": row["roomname_remark"],
            "con_numeric_id": row["con_numeric_id"],
        })
        if members:
            search_names[cid] = _member_names(members, user_names, self_id)

    sessions.sort(key=lambda item: item.get("last_message_time") or 0, reverse=True)
    return sessions, search_names, self_id


def load_sessions(
    session_db_path: str,
    user_db_path: Optional[str] = None,
    doc_db_path: Optional[str] = None,
    self_id: Optional[int] = None,
) -> dict:
    """Load and fully resolve every session.

    Returns ``{"total": int, "self_id": int | None, "sessions": [...]}``.
    """
    sessions, _search_names, detected_id = _load_all(
        session_db_path, user_db_path, doc_db_path, self_id
    )
    return {
        "total": len(sessions),
        "self_id": detected_id,
        "sessions": sessions,
    }


def _normalise_type_filter(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    lowered = str(value).strip().lower()
    if lowered in ("", "all", "*"):
        return None
    return _TYPE_ALIASES.get(lowered, lowered)


def list_sessions(
    db_path: str,
    limit: int = 50,
    offset: int = 0,
    keyword: Optional[str] = None,
    session_type: Optional[str] = None,
) -> list[dict]:
    """List sessions from session.db (CLI compatible signature).

    Keyword filtering runs against the resolved name and member names; the
    ``session_type`` filter accepts the new classification (single/group/
    wechat/app/system/external) as well as the legacy prefixes (R/S/M/O/Y).
    """
    sessions, search_names, _self_id = _load_all(db_path)

    if keyword:
        needle = str(keyword).strip().casefold()
        if needle:
            filtered = []
            for session in sessions:
                haystack = [session.get("name") or ""]
                haystack.extend(search_names.get(session["id"], []))
                if any(needle in item.casefold() for item in haystack if item):
                    filtered.append(session)
            sessions = filtered

    wanted_type = _normalise_type_filter(session_type)
    if wanted_type:
        sessions = [item for item in sessions if item.get("type") == wanted_type]

    start = max(0, int(offset or 0))
    if limit is None:
        return sessions[start:]
    return sessions[start:start + max(0, int(limit))]


def get_session(
    session_db_path: str,
    conversation_id: str,
    user_db_path: Optional[str] = None,
    doc_db_path: Optional[str] = None,
    self_id: Optional[int] = None,
) -> Optional[dict]:
    """Resolve a single conversation (numeric ids follow their R: alias)."""
    cid = _text(conversation_id)
    if not cid:
        return None
    sessions, _search_names, _self_id = _load_all(
        session_db_path, user_db_path, doc_db_path, self_id
    )
    by_id = {session["id"]: session for session in sessions}
    if cid.isdigit() and f"R:{cid}" in by_id:
        return by_id[f"R:{cid}"]
    return by_id.get(cid)


def get_session_detail(
    session_db_path: str,
    conversation_id: str,
    user_db_path: Optional[str] = None,
    doc_db_path: Optional[str] = None,
    self_id: Optional[int] = None,
) -> dict:
    """Resolve one conversation including its member list."""
    cid = _text(conversation_id)
    if not cid:
        return {}
    user_db_path = user_db_path or _sibling(session_db_path, "user.db")

    session = get_session(
        session_db_path, cid, user_db_path=user_db_path,
        doc_db_path=doc_db_path, self_id=self_id,
    )
    if not session:
        return {}

    resolved_id = session["id"]
    if self_id is None:
        self_id = detect_self_id(session_db_path)

    user_names: dict[int, str] = {}
    if user_db_path and os.path.isfile(user_db_path):
        try:
            user_names = build_user_names(user_db_path) or {}
        except Exception:
            user_names = {}

    members: list[dict] = []
    create_time = None
    try:
        conn = _connect(session_db_path)
        try:
            if _table_exists(conn, "conversation_table"):
                available = _columns(conn, "conversation_table")
                if "create_time" in available:
                    row = conn.execute(
                        'SELECT create_time FROM conversation_table WHERE id = ? LIMIT 1',
                        (resolved_id,),
                    ).fetchone()
                    if row:
                        create_time = row["create_time"]

            members_map = _load_members(conn)
            for uid, nick in members_map.get(resolved_id, []):
                members.append({
                    "user_id": uid,
                    "name": user_names.get(uid) or _clean_name(nick) or "",
                    "nick_name": nick,
                })
        finally:
            conn.close()
    except Exception:
        pass

    return {
        "id": session["id"],
        "name": session["name"],
        "type": session["type"],
        "type_label": session["type_label"],
        "member_count": len(members) or session["member_count"],
        "members": members,
        "is_external": session["is_external"],
        "create_time": create_time,
        "last_message_time": session["last_message_time"],
        "self_id": self_id,
    }


def get_session_count(db_path: str) -> int:
    """Get total number of rows in conversation_table (unmerged count)."""
    try:
        conn = _connect(db_path)
    except Exception:
        return 0
    try:
        if not _table_exists(conn, "conversation_table"):
            return 0
        row = conn.execute("SELECT COUNT(*) FROM conversation_table").fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()
