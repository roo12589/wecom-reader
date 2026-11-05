"""Message (消息) queries for decrypted WeCom databases.

Actual schema (from decrypted message.db):
  message_table: message_id, server_id, sequence, sender_id, conversation_id,
                 content_type, send_time, flag, content, devinfo, from_app_id,
                 msg_from_devinfo, extra_content, local_extra_content, client_id, ...
  message_small_table: same schema
  kf_message_tableV1: same schema (客服消息)

All message tables are structurally equivalent, so pagination and sorting are
done across a single ``UNION ALL`` of the existing tables.  This avoids the
duplicate/missing rows that per-table ``LIMIT/OFFSET`` produces.

Time filters: ``start_time`` is inclusive (>=) and ``end_time`` is exclusive
(<), matching the historical ``since`` / ``until`` CLI options.
"""

from __future__ import annotations

import base64
import sqlite3
from typing import Any, Optional

from .proto import decode_message, extract_strings

MESSAGE_TABLES = ("message_table", "message_small_table", "kf_message_tableV1")

# Category names -> content_type values.  ``unknown`` is the complement of
# every other category and is handled separately in ``_resolve_types``.
TYPE_GROUPS: dict[str, tuple[int, ...]] = {
    "text": (0, 2),
    "image": (14, 48),
    "file": (15,),
    "video": (17,),
    "voice": (16,),
    "link": (13,),
    "app": (35, 38, 145, 520, 573, 581),
    "system": (1001, 1002, 1003, 1004, 1005, 1006, 1016, 1022, 1030, 1051, 1052, 1055),
    "forward": (4,),
    "quote": (123, 570),
    "sticker": (29,),
    "call": (40,),
    "meeting": (1011,),
    "unknown": (),
}

MSG_TYPES: dict[int, str] = {
    content_type: name
    for name, content_types in TYPE_GROUPS.items()
    for content_type in content_types
}

_ALL_KNOWN_TYPES = tuple(sorted(MSG_TYPES))

_MESSAGE_COLUMNS = (
    "message_id",
    "server_id",
    "sequence",
    "sender_id",
    "conversation_id",
    "content_type",
    "send_time",
    "flag",
    "content",
    "from_app_id",
    "extra_content",
    "local_extra_content",
)

_ORDER_BY = (
    "COALESCE(send_time, 0) DESC, COALESCE(sequence, 0) DESC, "
    "COALESCE(message_id, 0) DESC"
)

# "Strictly newer than the anchor" under the ordering above.
_NEWER_THAN = (
    "((COALESCE(send_time, 0) > ?) "
    "OR (COALESCE(send_time, 0) = ? AND COALESCE(sequence, 0) > ?) "
    "OR (COALESCE(send_time, 0) = ? AND COALESCE(sequence, 0) = ? "
    "AND COALESCE(message_id, 0) > ?))"
)


# ---------------------------------------------------------------------------
# Connection / schema helpers
# ---------------------------------------------------------------------------


def _connect(db_path: str) -> sqlite3.Connection:
    """Open the decrypted database read-only (no -wal/-shm sidecars)."""
    path = str(db_path)
    uri = "file:" + path.replace("\\", "/").replace("?", "%3F").replace("#", "%23")
    params = "?mode=ro"
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


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _available_tables(conn: sqlite3.Connection) -> list[str]:
    return [table for table in MESSAGE_TABLES if _table_exists(conn, table)]


def _union_sql(conn: sqlite3.Connection, tables: list[str], where_sql: str) -> str:
    """Build one ``SELECT`` per existing table joined with ``UNION ALL``.

    Missing columns are emitted as ``NULL`` so heterogeneous (older) tables
    still participate without breaking the shared column list.
    """
    parts: list[str] = []
    for table in tables:
        columns = _table_columns(conn, table)
        select = [
            f'"{name}" AS "{name}"' if name in columns else f'NULL AS "{name}"'
            for name in _MESSAGE_COLUMNS
        ]
        select.insert(0, f"'{table}' AS source_table")
        part = f'SELECT {", ".join(select)} FROM "{table}"'
        if where_sql:
            part += f" WHERE {where_sql}"
        parts.append(part)
    return " UNION ALL ".join(parts)


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------


def _resolve_types(types: Any) -> Optional[tuple[str, list[int]]]:
    """Translate a category / content_type filter into an SQL fragment.

    ``types`` accepts a category name, an exact ``content_type`` (int or
    numeric string), a comma separated string or a list of any of these.
    ``None``, an empty value or ``"all"`` means "no filter".
    """
    if types is None:
        return None
    if isinstance(types, str):
        candidates: list[Any] = [part.strip() for part in types.split(",") if part.strip()]
    elif isinstance(types, (list, tuple, set)):
        candidates = list(types)
    else:
        candidates = [types]

    if not candidates:
        return None
    if any(
        isinstance(item, str) and item.strip().lower() in ("all", "*")
        for item in candidates
    ):
        return None

    include: set[int] = set()
    wants_unknown = False
    for item in candidates:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            include.add(item)
            continue
        if not isinstance(item, str):
            continue
        key = item.strip().lower()
        if not key:
            continue
        try:
            include.add(int(key))
            continue
        except ValueError:
            pass
        if key == "unknown":
            wants_unknown = True
            continue
        group = TYPE_GROUPS.get(key)
        if group:
            include.update(group)

    if wants_unknown:
        if include:
            # unknown (complement) plus any concrete type covers every row.
            return None
        placeholders = ", ".join("?" for _ in _ALL_KNOWN_TYPES)
        return (
            f"COALESCE(content_type, -1) NOT IN ({placeholders})",
            list(_ALL_KNOWN_TYPES),
        )

    if not include:
        return None

    ordered = sorted(include)
    placeholders = ", ".join("?" for _ in ordered)
    return f"content_type IN ({placeholders})", ordered


def _build_where(
    conversation_id: Optional[str] = None,
    type_filter: Optional[tuple[str, list[int]]] = None,
    msg_type: Optional[int] = None,
    keyword: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if conversation_id:
        clauses.append("conversation_id = ?")
        params.append(conversation_id)
    if type_filter:
        clause, values = type_filter
        clauses.append(clause)
        params.extend(values)
    if msg_type is not None:
        clauses.append("content_type = ?")
        params.append(int(msg_type))
    if keyword:
        pattern = f"%{keyword}%"
        clauses.append("(CAST(content AS TEXT) LIKE ? OR content LIKE ?)")
        params.extend([pattern, pattern])
    if start_time is not None:
        clauses.append("send_time >= ?")
        params.append(int(start_time))
    if end_time is not None:
        clauses.append("send_time < ?")
        params.append(int(end_time))

    return " AND ".join(clauses), params


# ---------------------------------------------------------------------------
# Row conversion
# ---------------------------------------------------------------------------


def _encode_raw(value: Any) -> str:
    """Base64 encode a blob so the result stays JSON serializable."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode("ascii")
    return base64.b64encode(str(value).encode("utf-8")).decode("ascii")


def _empty_decoded() -> dict:
    return {
        "kind": "unknown",
        "text": "",
        "summary": "",
        "quote": None,
        "files": [],
        "card": None,
        "items": [],
    }


def _row_to_message(row: sqlite3.Row) -> dict:
    """Convert one union row into the public message structure."""
    content = row["content"]
    extra_content = row["extra_content"]
    content_type = row["content_type"]

    try:
        decoded = decode_message(content_type, content, extra_content)
        if not isinstance(decoded, dict):
            decoded = _empty_decoded()
    except Exception:
        decoded = _empty_decoded()

    text = decoded.get("text") or ""
    summary = decoded.get("summary") or ""
    content_text = text or summary or ""

    return {
        "message_id": row["message_id"],
        "server_id": row["server_id"],
        "sequence": row["sequence"],
        "sender_id": row["sender_id"],
        "conversation_id": row["conversation_id"],
        "content_type": content_type,
        "type_name": MSG_TYPES.get(content_type, f"type_{content_type}"),
        "send_time": row["send_time"],
        "flag": row["flag"],
        "from_app_id": row["from_app_id"],
        "source_table": row["source_table"],
        "content_raw": _encode_raw(content),
        "extra_content_raw": _encode_raw(extra_content),
        "decoded": decoded,
        # Kept for compatibility with the legacy get_messages() output.
        "content": content_text,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def query_messages(
    db_path: str,
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
    """Query one conversation across all message tables.

    Rows from ``message_table``, ``message_small_table`` and
    ``kf_message_tableV1`` are combined with ``UNION ALL`` and sorted globally
    by ``send_time DESC, sequence DESC, message_id DESC`` before pagination,
    so ``offset`` applies to the whole conversation.

    Args:
        conversation_id: Conversation id, e.g. ``R:12345``.
        limit: Maximum number of messages returned.
        offset: Global offset, ignored when ``anchor_message_id`` resolves.
        types: Category name(s) (text/image/file/video/voice/link/app/system/
            forward/quote/sticker/call/meeting/unknown), an exact
            ``content_type`` (int or numeric string), a comma separated string
            or a list of these.  ``None``/empty/``"all"`` disables the filter.
        msg_type: Legacy exact ``content_type`` filter, still honoured.
        keyword: Substring matched against the raw content (UTF-8 safe).
        start_time: Inclusive unix timestamp lower bound.
        end_time: Exclusive unix timestamp upper bound.
        anchor_message_id: When given and found, returns the page starting at
            that message; ``anchor_offset`` is the computed global offset.

    Returns:
        ``{"messages": [...], "total": int, "has_more": bool,
        "offset": int, "anchor_offset": int | None}``.

        Each message carries the raw row fields plus ``source_table``,
        ``content_raw`` / ``extra_content_raw`` (base64 strings, JSON safe),
        the parsed ``decoded`` structure from :func:`proto.decode_message`
        (``kind``/``text``/``summary``/``quote``/``files``/``card``/``items``)
        and ``content`` (decoded text, legacy compatibility).
    """
    conn = _connect(db_path)
    try:
        tables = _available_tables(conn)
        if not tables:
            return {
                "messages": [],
                "total": 0,
                "has_more": False,
                "offset": offset,
                "anchor_offset": None,
            }

        type_filter = _resolve_types(types)
        where_sql, params = _build_where(
            conversation_id=conversation_id,
            type_filter=type_filter,
            msg_type=msg_type,
            keyword=keyword,
            start_time=start_time,
            end_time=end_time,
        )
        union = _union_sql(conn, tables, where_sql)
        # Every table subquery repeats the WHERE placeholders.
        union_params = params * len(tables)

        total = conn.execute(
            f"SELECT COUNT(*) FROM ({union})", union_params
        ).fetchone()[0]

        effective_offset = max(0, int(offset or 0))
        anchor_offset: Optional[int] = None
        if anchor_message_id is not None:
            anchor = conn.execute(
                f"SELECT send_time, sequence, message_id FROM ({union}) "
                f"WHERE message_id = ? ORDER BY {_ORDER_BY} LIMIT 1",
                union_params + [anchor_message_id],
            ).fetchone()
            if anchor is not None:
                bounds = [
                    anchor["send_time"], anchor["send_time"], anchor["sequence"],
                    anchor["send_time"], anchor["sequence"], anchor["message_id"],
                ]
                anchor_offset = conn.execute(
                    f"SELECT COUNT(*) FROM ({union}) WHERE {_NEWER_THAN}",
                    union_params + bounds,
                ).fetchone()[0]
                effective_offset = anchor_offset

        page_size = max(0, int(limit or 0))
        rows = conn.execute(
            f"SELECT * FROM ({union}) ORDER BY {_ORDER_BY} LIMIT ? OFFSET ?",
            union_params + [page_size, effective_offset],
        ).fetchall()

        messages = [_row_to_message(row) for row in rows]

        return {
            "messages": messages,
            "total": int(total),
            "has_more": effective_offset + len(messages) < total,
            "offset": effective_offset,
            "anchor_offset": anchor_offset,
        }
    finally:
        conn.close()


def _slice_around(text: str, keyword: str, max_len: int = 120) -> str:
    """Return at most ``max_len`` characters of *text* around *keyword*."""
    if not text:
        return ""
    index = text.find(keyword) if keyword else -1
    if index < 0 and keyword:
        index = text.lower().find(keyword.lower())
    if index < 0:
        return text[:max_len]

    end = min(len(text), index + len(keyword) + 30)
    start = max(0, end - max_len)
    end = min(len(text), start + max_len)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _snippet_for(decoded: dict, keyword: str, content: Any, extra_content: Any) -> str:
    """Build a search snippet that contains *keyword* whenever possible."""
    text = decoded.get("text") or ""
    summary = decoded.get("summary") or ""

    for candidate in (text, summary):
        if candidate and keyword and keyword in candidate:
            return _slice_around(candidate, keyword)

    for raw in (content, extra_content):
        if not isinstance(raw, (bytes, bytearray)):
            continue
        for candidate in extract_strings(bytes(raw)):
            if keyword in candidate:
                return _slice_around(candidate, keyword)
        text_raw = bytes(raw).decode("utf-8", errors="ignore")
        if keyword and keyword in text_raw:
            return _slice_around(text_raw, keyword)

    return _slice_around(text or summary, keyword)


def search_messages(
    db_path: str,
    keyword: str,
    conversation_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    types: Any = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> dict:
    """Search messages by keyword across all message tables.

    Returns ``{"results": [...], "total": int, "has_more": bool}``.  Each
    result has the same structure as :func:`query_messages` messages plus a
    ``snippet`` (at most 120 characters around the keyword, when possible).

    The keyword is matched against the raw content, so Chinese text stored in
    protobuf blobs is found.  ``start_time`` is inclusive, ``end_time``
    exclusive.
    """
    keyword = (keyword or "").strip()
    empty = {"results": [], "total": 0, "has_more": False}
    if not keyword:
        return empty

    conn = _connect(db_path)
    try:
        tables = _available_tables(conn)
        if not tables:
            return empty

        type_filter = _resolve_types(types)
        where_sql, params = _build_where(
            conversation_id=conversation_id,
            type_filter=type_filter,
            keyword=keyword,
            start_time=start_time,
            end_time=end_time,
        )
        union = _union_sql(conn, tables, where_sql)
        union_params = params * len(tables)

        total = int(
            conn.execute(f"SELECT COUNT(*) FROM ({union})", union_params).fetchone()[0]
        )

        effective_offset = max(0, int(offset or 0))
        page_size = max(0, int(limit or 0))
        rows = conn.execute(
            f"SELECT * FROM ({union}) ORDER BY {_ORDER_BY} LIMIT ? OFFSET ?",
            union_params + [page_size, effective_offset],
        ).fetchall()

        results = []
        for row in rows:
            message = _row_to_message(row)
            message["snippet"] = _snippet_for(
                message["decoded"], keyword, row["content"], row["extra_content"]
            )
            results.append(message)

        return {
            "results": results,
            "total": total,
            "has_more": effective_offset + len(results) < total,
        }
    finally:
        conn.close()


def search_messages_legacy(
    db_path: str,
    keyword: str,
    conversation_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Legacy list-returning search wrapper (see :func:`search_messages`)."""
    result = search_messages(
        db_path,
        keyword,
        conversation_id=conversation_id,
        limit=limit,
    )
    return result["results"]


def get_message_count(
    db_path: str,
    conversation_id: str,
    types: Any = None,
    keyword: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> int:
    """Total number of messages matching the same filters as query_messages."""
    conn = _connect(db_path)
    try:
        tables = _available_tables(conn)
        if not tables:
            return 0

        type_filter = _resolve_types(types)
        where_sql, params = _build_where(
            conversation_id=conversation_id,
            type_filter=type_filter,
            keyword=keyword,
            start_time=start_time,
            end_time=end_time,
        )
        union = _union_sql(conn, tables, where_sql)
        union_params = params * len(tables)
        return int(
            conn.execute(
                f"SELECT COUNT(*) FROM ({union})", union_params
            ).fetchone()[0]
        )
    finally:
        conn.close()


def get_messages(
    db_path: str,
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
    since: Optional[int] = None,
    until: Optional[int] = None,
    msg_type: Optional[int] = None,
) -> list[dict]:
    """Legacy API: messages for a conversation as a plain list.

    Delegates to :func:`query_messages`; ``since`` is an inclusive lower bound
    and ``until`` an exclusive upper bound.  Every returned field is JSON
    serializable and ``content`` holds the decoded text (or summary).
    """
    result = query_messages(
        db_path,
        conversation_id,
        limit=limit,
        offset=offset,
        msg_type=msg_type,
        start_time=since,
        end_time=until,
    )
    return result["messages"]
