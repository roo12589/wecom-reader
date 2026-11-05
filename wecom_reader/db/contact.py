"""Contact (联系人) queries for decrypted WeCom databases.

Column names differ between consumer WeCom and private-deployment builds
(``external_corp_name`` vs ``external_company_name``, ``external_job`` vs
``position``, and ``external_user_relation_v3.corp_remark`` only exists in some
releases), so every query below resolves the columns actually present instead
of assuming one schema.
"""

import hashlib
import os
import sqlite3
from typing import Optional


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


def _clean_text(value) -> str:
    """Decode/Normalise a possibly-binary, possibly-NULL text field."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", "replace")
        except Exception:
            return ""
    return str(value).strip()


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
    conn = _connect(db_path)
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


def build_user_info(db_path: str) -> dict[int, dict]:
    """Build a rich ``user_id -> info`` mapping from user.db.

    Only columns that actually exist are selected, so this works for both
    consumer and private-deployment builds.  ``name`` is always a clean
    display name (no company suffix appended).
    """
    info: dict[int, dict] = {}
    try:
        conn = _connect(db_path)
    except Exception:
        return info
    try:
        if not _table_exists(conn, "user_table"):
            return info
        available = _columns(conn, "user_table")
        if "id" not in available:
            return info

        candidates = {
            "name": ("name", "real_name", "account"),
            "real_name": ("real_name",),
            "account": ("account",),
            "position": ("position", "external_job"),
            "corp_name": ("external_company_name", "external_corp_name"),
            "avator_url": ("avator_url", "avatar_url"),
        }
        expr = ["id"]
        for logical, cands in candidates.items():
            col = _pick(available, *cands)
            expr.append(f'"{col}" AS "{logical}"' if col else f'NULL AS "{logical}"')

        for row in conn.execute(f"SELECT {', '.join(expr)} FROM user_table"):
            try:
                uid = int(row["id"])
            except (TypeError, ValueError):
                continue
            name = (
                _clean_text(row["name"])
                or _clean_text(row["real_name"])
                or _clean_text(row["account"])
            )
            info[uid] = {
                "name": name,
                "real_name": _clean_text(row["real_name"]),
                "account": _clean_text(row["account"]),
                "position": _clean_text(row["position"]),
                "corp_name": _clean_text(row["corp_name"]),
                "avator_url": _clean_text(row["avator_url"]),
            }
        return info
    except Exception:
        return info
    finally:
        conn.close()


def build_user_names(db_path: str) -> dict[int, str]:
    """Build a clean ``user_id -> name`` mapping for conversation resolution."""
    info = build_user_info(db_path)
    names = {uid: value["name"] for uid, value in info.items() if value.get("name")}

    # External contacts may only exist as remarks in external_user_relation_v3.
    try:
        conn = _connect(db_path)
    except Exception:
        return names
    try:
        if _table_exists(conn, "external_user_relation_v3"):
            available = _columns(conn, "external_user_relation_v3")
            remark_key = _pick(available, *_RELATION_COLS["remarks"])
            if "user_id" in available and remark_key:
                for row in conn.execute(
                    f'SELECT user_id, "{remark_key}" AS remark FROM external_user_relation_v3'
                ):
                    try:
                        uid = int(row["user_id"])
                    except (TypeError, ValueError):
                        continue
                    if uid not in names and _clean_text(row["remark"]):
                        names[uid] = _clean_text(row["remark"])
    except Exception:
        pass
    finally:
        conn.close()
    return names


def detect_self_id(session_db_path: str) -> Optional[int]:
    """Detect the current account id from session.db.

    Uses the user that participates in the largest number of distinct
    conversations; falls back to the id shared by most ``S:`` conversations.
    Returns ``None`` instead of raising when the data is missing/ambiguous.
    """
    try:
        conn = _connect(session_db_path)
    except Exception:
        return None
    try:
        top = None
        if _table_exists(conn, "conversation_user_table"):
            rows = conn.execute(
                "SELECT user_id, COUNT(DISTINCT conversation_id) AS n "
                "FROM conversation_user_table GROUP BY user_id "
                "ORDER BY n DESC LIMIT 2"
            ).fetchall()
            if rows and (len(rows) == 1 or rows[0]["n"] > rows[1]["n"]):
                try:
                    candidate = int(rows[0]["user_id"])
                except (TypeError, ValueError):
                    candidate = 0
                if candidate > 0:
                    top = candidate

        if top is not None:
            return top

        # Fallback: the self id appears once in (nearly) every S: pair.
        if _table_exists(conn, "conversation_table"):
            counts: dict[int, int] = {}
            for row in conn.execute("SELECT id FROM conversation_table WHERE id LIKE 'S:%'"):
                for part in _clean_text(row[0])[2:].split("_"):
                    if part.isdigit():
                        uid = int(part)
                        counts[uid] = counts.get(uid, 0) + 1
            if counts:
                best = max(counts.values())
                winners = [uid for uid, n in counts.items() if n == best]
                if len(winners) == 1:
                    return winners[0]
        return None
    except Exception:
        return None
    finally:
        conn.close()


def build_avatar_file_map(db_path: str, avatar_dir: Optional[str]) -> dict[int, str]:
    """Map user_id -> local avatar file path.

    ``avatar_dir`` holds ``<md5>.<ext>`` files (usually in year-month
    sub-directories).  The md5 is computed from ``user_table.avator_url``.
    """
    result: dict[int, str] = {}
    if not avatar_dir or not os.path.isdir(avatar_dir):
        return result

    files: dict[str, str] = {}
    try:
        for root, _dirs, names in os.walk(avatar_dir):
            for filename in names:
                stem, ext = os.path.splitext(filename)
                if ext.lower() in (".db", ".db-wal", ".db-shm", ".db-journal", ".tmp", ".ini"):
                    continue
                files.setdefault(stem.lower(), os.path.join(root, filename))
    except Exception:
        return result

    try:
        conn = _connect(db_path)
    except Exception:
        return result
    try:
        if not _table_exists(conn, "user_table"):
            return result
        available = _columns(conn, "user_table")
        url_col = _pick(available, "avator_url", "avatar_url")
        if "id" not in available or not url_col:
            return result
        for row in conn.execute(f'SELECT id, "{url_col}" AS url FROM user_table'):
            url = _clean_text(row["url"])
            if not url:
                continue
            try:
                uid = int(row["id"])
            except (TypeError, ValueError):
                continue
            path = files.get(hashlib.md5(url.encode("utf-8")).hexdigest())
            if path:
                result[uid] = path
    except Exception:
        pass
    finally:
        conn.close()
    return result


def get_avatar_buffer(avatar_db_path: str, conversation_id: str) -> Optional[bytes]:
    """Return the stored avatar bytes for a conversation (None if absent).

    Checks both ``conversation_avatar_table`` and
    ``collect_conversation_avatar_table`` without loading the whole table.
    """
    cid = _clean_text(conversation_id)
    if not cid or not avatar_db_path or not os.path.isfile(avatar_db_path):
        return None
    try:
        conn = _connect(avatar_db_path)
    except Exception:
        return None
    try:
        if _table_exists(conn, "conversation_avatar_table"):
            available = _columns(conn, "conversation_avatar_table")
            if {"conversation_id", "buffer"} <= available:
                row = conn.execute(
                    'SELECT buffer FROM conversation_avatar_table '
                    'WHERE conversation_id = ? LIMIT 1',
                    (cid,),
                ).fetchone()
                if row and row["buffer"]:
                    return bytes(row["buffer"])

        if _table_exists(conn, "collect_conversation_avatar_table"):
            available = _columns(conn, "collect_conversation_avatar_table")
            if {"collect_conversation_id", "buffer"} <= available:
                row = conn.execute(
                    'SELECT buffer FROM collect_conversation_avatar_table '
                    'WHERE collect_conversation_id = ? LIMIT 1',
                    (cid,),
                ).fetchone()
                if row and row["buffer"]:
                    return bytes(row["buffer"])
        return None
    except Exception:
        return None
    finally:
        conn.close()


def build_user_map(db_path: str) -> dict[int, str]:
    """Build user_id -> display_name mapping for message sender resolution.

    Kept for CLI compatibility: unlike :func:`build_user_names` the company
    suffix is appended when a contact has one.
    """
    users: dict[int, str] = {}
    for uid, value in build_user_info(db_path).items():
        name = value.get("name") or ""
        corp = value.get("corp_name") or ""
        if corp and corp not in name:
            name = f"{name} ({corp})" if name else corp
        if name:
            users[uid] = name

    # External contacts may only exist as remarks in external_user_relation_v3.
    try:
        conn = _connect(db_path)
    except Exception:
        return users
    try:
        if _table_exists(conn, "external_user_relation_v3"):
            available = _columns(conn, "external_user_relation_v3")
            remark_key = _pick(available, *_RELATION_COLS["remarks"])
            if "user_id" in available and remark_key:
                for row in conn.execute(
                    f'SELECT user_id, "{remark_key}" AS remark FROM external_user_relation_v3'
                ):
                    try:
                        uid = int(row["user_id"])
                    except (TypeError, ValueError):
                        continue
                    if uid not in users and _clean_text(row["remark"]):
                        users[uid] = _clean_text(row["remark"])
    except Exception:
        pass
    finally:
        conn.close()
    return users


def get_group_members(session_db_path: str, conversation_id: str) -> dict[int, str]:
    """Get group members with nicknames for a conversation."""
    conn = _connect(session_db_path)
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
