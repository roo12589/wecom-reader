"""Web UI for browsing WeCom chat data.

Usage: python -m wecom_reader.web --db-dir E:/WXWork/1688851235369380/Data
"""

import json
import os
from datetime import date, datetime

from flask import Flask, Response, render_template, request, send_file

from .reader import WeComReader

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
    static_url_path="/static",
)
app.config["TEMPLATES_AUTO_RELOAD"] = True

reader: WeComReader = None


def _json_default(obj):
    """Best-effort conversion of non JSON-native values."""
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if isinstance(obj, BaseException):
        return str(obj)
    return str(obj)


def safe_jsonify(data):
    """JSON response that handles bytes, datetime, etc."""
    return Response(
        json.dumps(data, ensure_ascii=False, default=_json_default),
        mimetype="application/json",
    )


def _json_error(message, status=400, **extra):
    payload = {"error": str(message)}
    payload.update(extra)
    return safe_jsonify(payload), status


def _get_reader():
    """Return the module-level reader (may be ``None``)."""
    return reader


def _int_arg(name, default, minimum=None, maximum=None):
    """Parse an integer query parameter without ever raising."""
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def _limit_arg():
    return _int_arg("limit", 50, 1, 200)


def _offset_arg():
    return _int_arg("offset", 0, 0)


def _time_arg(name):
    """Parse a unix timestamp or a local ``YYYY-MM-DD[ HH:MM:SS]`` value."""
    raw = request.args.get(name)
    if raw is None:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except (TypeError, ValueError):
            continue
    return None


def _types_arg():
    """Comma separated message categories; empty/all disables filtering."""
    raw = request.args.get("types")
    if not raw:
        return None
    parts = [part.strip() for part in str(raw).split(",") if part.strip()]
    if not parts:
        return None
    if all(part.lower() in ("all", "*") for part in parts):
        return None
    return ",".join(parts)


_SESSION_TYPE_ALIASES = {
    "single": "single",
    "单聊": "single",
    "s": "single",
    "s:": "single",
    "group": "group",
    "群聊": "group",
    "r": "group",
    "r:": "group",
    "wechat": "wechat",
    "微信": "wechat",
    "m": "wechat",
    "m:": "wechat",
    "wechat_contact": "wechat",
    "app": "app",
    "应用": "app",
    "o": "app",
    "o:": "app",
    "system": "system",
    "系统": "system",
    "y": "system",
    "y:": "system",
    "external": "external",
    "外部": "external",
    "外部会话": "external",
    "other": "other",
    "其他": "other",
    "其它": "other",
}

_NO_SESSION_TYPE = {"", "all", "*", "全部", "全部会话"}


def _session_type_arg():
    raw = request.args.get("type")
    if raw is None:
        raw = request.args.get("session_type")
    if raw is None:
        return None
    value = str(raw).strip()
    if value.lower() in _NO_SESSION_TYPE or value in _NO_SESSION_TYPE:
        return None
    return _SESSION_TYPE_ALIASES.get(value.lower(), value)


def _download_arg():
    raw = request.args.get("download", "0")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _path_within(path, root):
    """True when *path* resolves to a file inside *root*."""
    if not path or not root:
        return False
    try:
        path_abs = os.path.abspath(path)
        root_abs = os.path.abspath(root)
        if os.path.commonpath([path_abs, root_abs]) != root_abs:
            return False
        relative = os.path.relpath(path_abs, root_abs)
    except (OSError, ValueError):
        return False
    return relative != ".." and not relative.startswith(".." + os.sep)


def _error_response(message, status):
    """Plain response used by the global error handlers."""
    if request.path.startswith("/api/"):
        payload = {"error": message}
        return Response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            mimetype="application/json",
        )
    return Response(f"<h1>{status} {message}</h1>", status=status, mimetype="text/html")


@app.errorhandler(404)
def handle_not_found(error):
    return _error_response("not found", 404)


@app.errorhandler(405)
def handle_method_not_allowed(error):
    return _error_response("method not allowed", 405)


@app.errorhandler(500)
def handle_server_error(error):
    return _error_response("internal server error", 500)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    try:
        data = dict(current.status() or {})
        data["self_id"] = current.self_id
        return safe_jsonify(data)
    except Exception as exc:
        return _json_error(exc, 500)


def _has_source_databases(db_dir):
    """True when *db_dir* still holds encrypted source databases."""
    if not db_dir or not os.path.isdir(db_dir):
        return False
    for root, dirs, files in os.walk(db_dir):
        dirs[:] = [d for d in dirs if d not in ("-journal",)]
        for name in files:
            if name.endswith(".db") and not name.endswith(("-wal", "-shm")):
                return True
    return False


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    if _has_source_databases(current.db_dir):
        try:
            result = current.init(verbose=False) or {}
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
    else:
        # --db-dir may point at a media-only directory (Cache) with no
        # encrypted databases; the already decrypted data is still refreshable.
        result = {"success": False}
    current.invalidate_caches()
    try:
        status = current.status()
    except Exception as exc:
        return safe_jsonify({"success": False, "error": str(exc)}), 500
    ready = bool(result.get("success")) or bool(
        current.session_db_path and current.message_db_path
    )
    payload = {
        "success": ready,
        "refreshed": ready,
        "decrypted": result.get("decrypted", 0),
        "copied": result.get("copied", 0),
        "failed": result.get("failed", 0),
        "decrypted_dir": result.get("decrypted_dir") or current.decrypted_dir,
        "media_dir": result.get("media_dir") or current.media_dir,
        "status": status,
    }
    if not ready:
        payload["error"] = result.get("error") or "decryption unavailable"
    elif result.get("error"):
        payload["warning"] = result["error"]
    return safe_jsonify(payload)


@app.route("/api/sessions")
def api_sessions():
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    try:
        page = current.list_sessions_page(
            limit=_limit_arg(),
            offset=_offset_arg(),
            keyword=request.args.get("keyword") or None,
            session_type=_session_type_arg(),
        )
        data = dict(page or {})
        data["count"] = len(data.get("sessions") or [])
        return safe_jsonify(data)
    except Exception as exc:
        return _json_error(exc, 500)


@app.route("/api/sessions/<path:session_id>/detail")
def api_session_detail(session_id):
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    try:
        detail = current.session_detail(session_id)
        if not detail:
            return _json_error("session not found", 404, session_id=session_id)
        return safe_jsonify(detail)
    except Exception as exc:
        return _json_error(exc, 500)


@app.route("/api/messages")
def api_messages():
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return _json_error("session_id required", 400)
    try:
        page = current.query_messages_page(
            session_id,
            limit=_limit_arg(),
            offset=_offset_arg(),
            types=_types_arg(),
            keyword=request.args.get("keyword") or None,
            start_time=_time_arg("start_time"),
            end_time=_time_arg("end_time"),
            anchor_message_id=_int_arg("anchor_message_id", None),
        )
        return safe_jsonify(page)
    except Exception as exc:
        return _json_error(exc, 500)


@app.route("/api/search")
def api_search():
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    offset = _offset_arg()
    limit = _limit_arg()
    keyword = (request.args.get("q") or "").strip()
    if not keyword:
        return safe_jsonify({
            "total": 0,
            "has_more": False,
            "offset": offset,
            "limit": limit,
            "results": [],
        })
    try:
        page = current.search_messages_page(
            keyword,
            conversation_id=request.args.get("session_id") or None,
            limit=limit,
            offset=offset,
            types=_types_arg(),
            start_time=_time_arg("start_time"),
            end_time=_time_arg("end_time"),
        )
        return safe_jsonify(page)
    except Exception as exc:
        return _json_error(exc, 500)


@app.route("/api/media/forward")
def api_media_forward():
    """Serve a forwarded-chat attachment by filename (index lookup only)."""
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    raw_name = request.args.get("name")
    name = str(raw_name or "").strip()
    if not name:
        return _json_error("name required", 400)
    if ".." in name or os.path.isabs(name) or "\x00" in name:
        return _json_error("forbidden", 403, name=name)
    download = _download_arg()
    try:
        info = current.media_by_name(name)
        path = (info or {}).get("path")
        if not info or not info.get("exists") or not path or not os.path.isfile(path):
            return _json_error("media not found", 404, name=name)
        if not _path_within(path, current.media_dir):
            return _json_error("forbidden", 403, name=name)
        basename = info.get("name") or os.path.basename(path)
        response = send_file(
            path,
            mimetype=info.get("mimetype") or "application/octet-stream",
            as_attachment=download,
            download_name=basename if download else None,
            conditional=True,
        )
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response
    except Exception as exc:
        return _json_error(exc, 500, name=name)


@app.route("/api/media/<int:message_id>")
def api_media(message_id):
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    raw_index = request.args.get("i")
    if raw_index is not None and str(raw_index).strip():
        try:
            int(str(raw_index).strip())
        except (TypeError, ValueError):
            return _json_error("invalid media index", 403, message_id=message_id)
    index = _int_arg("i", 0, minimum=0)
    download = _download_arg()
    try:
        info = current.get_media(message_id, index=index)
        path = (info or {}).get("path")
        if not info or not info.get("exists") or not path or not os.path.isfile(path):
            return _json_error(
                "media not found",
                404,
                message_id=message_id,
                index=index,
            )
        if not _path_within(path, current.media_dir):
            return _json_error(
                "forbidden",
                403,
                message_id=message_id,
                index=index,
            )
        name = info.get("name") or os.path.basename(path)
        response = send_file(
            path,
            mimetype=info.get("mimetype") or "application/octet-stream",
            as_attachment=download,
            download_name=name if download else None,
            conditional=True,
        )
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response
    except Exception as exc:
        return _json_error(exc, 500)


@app.route("/api/avatar/user/<int:user_id>")
def api_avatar_user(user_id):
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    try:
        data, mimetype = current.avatar_bytes(user_id=user_id)
        if not data:
            return _json_error("avatar not found", 404, user_id=user_id)
        response = Response(data, mimetype=mimetype or "image/png")
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response
    except Exception as exc:
        return _json_error(exc, 500)


@app.route("/api/avatar/<path:conversation_id>")
def api_avatar(conversation_id):
    current = _get_reader()
    if current is None:
        return _json_error("reader not initialized", 503)
    try:
        data, mimetype = current.avatar_bytes(conversation_id=conversation_id)
        if not data:
            return _json_error(
                "avatar not found", 404, conversation_id=conversation_id
            )
        response = Response(data, mimetype=mimetype or "image/png")
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response
    except Exception as exc:
        return _json_error(exc, 500)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="WeCom chat web viewer")
    parser.add_argument("--db-dir", required=True, help="WeCom data directory")
    parser.add_argument(
        "--decrypted-dir", default="wxwork_decrypted", help="Decrypted DB directory"
    )
    parser.add_argument("--media-dir", default=None, help="Media cache directory")
    parser.add_argument("--self-id", type=int, default=None, help="Current account id")
    parser.add_argument("--port", type=int, default=8765, help="Web server port")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    args = parser.parse_args()

    global reader
    reader = WeComReader(
        db_dir=args.db_dir,
        decrypted_dir=args.decrypted_dir,
        media_dir=args.media_dir,
        self_id=args.self_id,
    )

    try:
        ready = reader.ensure_ready(timeout=120)
    except Exception as exc:  # never prevent the page from starting
        ready = {"ready": False, "error": str(exc)}

    if ready.get("ready"):
        print("[*] Decrypted databases are ready.")
    else:
        detail = ready.get("error") or "databases missing"
        print(f"[!] Decrypted databases are not ready: {detail}")
        if "decrypted" in ready:
            print(
                "[*] Decrypt result: "
                f"decrypted={ready.get('decrypted', 0)}, "
                f"copied={ready.get('copied', 0)}, "
                f"failed={ready.get('failed', 0)}"
            )

    print(f"[*] Decrypted data: {reader.decrypted_dir}")
    print(f"[*] Media dir: {reader.media_dir or '(not found)'}")
    print(f"[*] Starting web UI on http://{args.host}:{args.port}")
    print("[*] Press Ctrl+C to quit.")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
