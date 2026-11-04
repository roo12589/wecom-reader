"""Contact (联系人) queries for decrypted WeCom databases.

Column names differ between consumer WeCom and private-deployment builds
(``external_corp_name`` vs ``external_company_name``, ``external_job`` vs
``position``, and ``external_user_relation_v3.corp_remark`` only exists in some
releases), so every query below resolves the columns actually present instead
of assuming one schema.
"""

import sqlite3
from typing import Optional


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names of ``table`` (empty if it is missing)."""
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _pick(available: set[str], *candidates: str) -> Optional[str]:
    """First candidate column that actually exists."""
    for name in candidates:
        if name in available:
            return name
    return None


# Candidate column names, in preference order, per logical field.
_USER_COLS = {
    "name": ("name",),
    "real_name": ("real_name",),
    "account": ("account",),
    "corp": ("external_company_name", "external_corp_name", "cross_corpany_id"),
    "job": ("position", "external_job"),
}
_RELATION_COLS = {
    "remarks": ("real_remarks", "remarks"),
    "corp_remark": ("corp_remark",),
}


def _user_select(conn: sqlite3.Connection) -> Optional[list[str]]:
    """Build the SELECT list for ``user_table`` using only existing columns."""
    if not _table_exists(conn, "user_table"):
        return None
    available = _columns(conn, "user_table")
    if "id" not in available:
        return None
    expr = ["id"]
    for field, candidates in _USER_COLS.items():
        col = _pick(available, *candidates)
        expr.append(col if col else f"NULL AS {field}_missing")
    return expr


def _display_name(row: sqlite3.Row, name_key: str, real_key: str, account_key: str) -> str:
    """Pick the best human-readable name from a contact row."""
    return (row[name_key] or row[real_key] or row[account_key] or "")


def list_contacts(
    db_path: str,
    keyword: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List contacts from user.db.

    Args:
        db_path: Path to decrypted user.db.
        keyword: Filter by name/account/corp.
        limit: Max results.
        offset: Pagination offset.

    Returns:
        List of contact dicts.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        contacts = []

        expr = _user_select(conn)
        if expr:
            available = _columns(conn, "user_table")
            name_key = _pick(available, *_USER_COLS["name"]) or "name"
            real_key = _pick(available, *_USER_COLS["real_name"]) or "real_name"
            account_key = _pick(available, *_USER_COLS["account"]) or "account"
            corp_key = _pick(available, *_USER_COLS["corp"])
            job_key = _pick(available, *_USER_COLS["job"])

            query = f"SELECT {', '.join(expr)} FROM user_table"
            params: list = []

            if keyword:
                searchable = [c for c in (name_key, real_key, account_key, corp_key) if c]
                if searchable:
                    query += " WHERE (" + " OR ".join(
                        f"{c} LIKE ?" for c in searchable
                    ) + ")"
                    params.extend([f"%{keyword}%"] * len(searchable))

            query += " ORDER BY id LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            for row in conn.execute(query, params):
                display_name = _display_name(row, name_key, real_key, account_key)
                corp = (row[corp_key] if corp_key else "") or ""
                if corp and corp not in display_name:
                    display_name = f"{display_name} ({corp})" if display_name else corp

                contacts.append({
                    "id": row["id"],
                    "name": display_name,
                    "raw_name": row[name_key],
                    "real_name": row[real_key],
                    "account": row[account_key],
                    "corp_name": corp,
                    "job": row[job_key] if job_key else None,
                })

        # Also check external_user_relation_v3 for external contacts
        if _table_exists(conn, "external_user_relation_v3"):
            available = _columns(conn, "external_user_relation_v3")
            if "user_id" in available:
                remark_key = _pick(available, *_RELATION_COLS["remarks"])
                corp_key = _pick(available, *_RELATION_COLS["corp_remark"])

                existing_ids = {c["id"] for c in contacts}
                select_cols = ["user_id"]
                select_cols.append(remark_key or "NULL AS remarks_missing")
                if corp_key:
                    select_cols.append(corp_key)

                query = f"SELECT {', '.join(select_cols)} FROM external_user_relation_v3"
                params = []
                if keyword and remark_key:
                    query += " WHERE " + remark_key + " LIKE ?"
                    params.append(f"%{keyword}%")
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                for row in conn.execute(query, params):
                    uid = row["user_id"]
                    if uid in existing_ids:
                        continue
                    name = (row[remark_key] if remark_key else "") or ""
                    if name:
                        contacts.append({
                            "id": uid,
                            "name": name,
                            "raw_name": None,
                            "real_name": None,
                            "account": None,
                            "corp_name": row[corp_key] if corp_key else None,
                            "job": None,
                        })

        return contacts
    finally:
        conn.close()


def build_user_map(db_path: str) -> dict[int, str]:
    """Build user_id -> display_name mapping for message sender resolution."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        users = {}

        expr = _user_select(conn)
        if expr:
            available = _columns(conn, "user_table")
            name_key = _pick(available, *_USER_COLS["name"]) or "name"
            real_key = _pick(available, *_USER_COLS["real_name"]) or "real_name"
            account_key = _pick(available, *_USER_COLS["account"]) or "account"
            corp_key = _pick(available, *_USER_COLS["corp"])

            for row in conn.execute(f"SELECT {', '.join(expr)} FROM user_table"):
                name = _display_name(row, name_key, real_key, account_key)
                corp = (row[corp_key] if corp_key else "") or ""
                if corp and corp not in name:
                    name = f"{name} ({corp})" if name else corp
                if name:
                    users[int(row["id"])] = name

        if _table_exists(conn, "external_user_relation_v3"):
            available = _columns(conn, "external_user_relation_v3")
            remark_key = _pick(available, *_RELATION_COLS["remarks"])
            if "user_id" in available and remark_key:
                for row in conn.execute(
                    f"SELECT user_id, {remark_key} FROM external_user_relation_v3"
                ):
                    uid = int(row["user_id"])
                    if uid not in users and row[remark_key]:
                        users[uid] = row[remark_key]

        return users
    finally:
        conn.close()


def get_group_members(session_db_path: str, conversation_id: str) -> dict[int, str]:
    """Get group members with nicknames for a conversation."""
    conn = sqlite3.connect(session_db_path)
    conn.row_factory = sqlite3.Row
    try:
        members = {}
        if _table_exists(conn, "conversation_user_table"):
            for row in conn.execute(
                "SELECT user_id, nick_name FROM conversation_user_table WHERE conversation_id = ?",
                (conversation_id,),
            ):
                if row["nick_name"]:
                    members[int(row["user_id"])] = row["nick_name"]
        return members
    finally:
        conn.close()
