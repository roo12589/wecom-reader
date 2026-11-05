"""Protocol-buffer wire decoding and WeCom message content normalization.

The decrypted WeCom databases store message bodies as protobuf-like binary
payloads.  Field numbering is not the usual IM schema, so this module maps
the concrete content types found in real data to a stable presentation model.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Low level wire decoding
# ---------------------------------------------------------------------------


def _read_varint(data: bytes, pos: int) -> tuple[Optional[int], int]:
    """Read a base-128 varint.

    Returns ``(value, new_pos)`` or ``(None, pos)`` when the data is
    truncated / malformed.
    """
    result = 0
    shift = 0
    n = len(data)
    while pos < n:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
        if shift > 63:
            return None, pos
    return None, pos


def decode_wire(data: bytes) -> list[tuple[int, int, object]]:
    """Safely decode a protobuf wire stream.

    Only wire types 0 (varint), 1 (64-bit), 2 (length-delimited) and 5
    (32-bit) are supported.  Decoding stops silently at the first truncated
    or malformed field; no exception is raised.

    Returns a list of ``(field_number, wire_type, value)`` tuples.  For
    length-delimited fields the value is ``bytes``.
    """
    fields: list[tuple[int, int, object]] = []
    if not isinstance(data, (bytes, bytearray)):
        return fields

    buf = bytes(data)
    n = len(buf)
    pos = 0

    while pos < n:
        tag, pos = _read_varint(buf, pos)
        if tag is None:
            break
        field_number = tag >> 3
        wire_type = tag & 0x07
        if field_number == 0:
            break

        if wire_type == 0:
            value, pos = _read_varint(buf, pos)
            if value is None:
                break
            fields.append((field_number, 0, value))
        elif wire_type == 1:
            if pos + 8 > n:
                break
            fields.append((field_number, 1, buf[pos:pos + 8]))
            pos += 8
        elif wire_type == 2:
            length, pos = _read_varint(buf, pos)
            if length is None or length < 0 or pos + length > n:
                break
            fields.append((field_number, 2, buf[pos:pos + length]))
            pos += length
        elif wire_type == 5:
            if pos + 4 > n:
                break
            fields.append((field_number, 5, buf[pos:pos + 4]))
            pos += 4
        else:
            # Wire types 3/4 (groups) are not used by WeCom and are unsafe.
            break

    return fields


# ---------------------------------------------------------------------------
# String extraction
# ---------------------------------------------------------------------------

_NOISE_RE = re.compile(r"^(?:WN[0-9A-Za-z~._+\-]+|[0-9]+|[0-9a-fA-F]{32})$")


def _decode_readable(payload: bytes) -> Optional[str]:
    """Decode *payload* as UTF-8 text when it looks like human readable data."""
    try:
        text = payload.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return None
    if not text:
        return ""
    # Control characters other than normal whitespace mean this payload is a
    # nested wire structure, not a leaf string.
    if any(ord(ch) < 32 and ch not in "\n\r\t" for ch in text):
        return None
    printable = sum(1 for ch in text if ord(ch) >= 32 or ch in "\n\r\t")
    if printable / len(text) < 0.85:
        return None
    return text


def _is_noise(text: str) -> bool:
    """Reject internal identifiers: pure numbers, WN... server ids and md5s."""
    stripped = text.strip()
    if not stripped:
        return True
    return bool(_NOISE_RE.match(stripped))


def _strings_with_depth(data: bytes, depth: int = 0, out: Optional[list[tuple[int, str]]] = None) -> list[tuple[int, str]]:
    if out is None:
        out = []
    if depth > 12 or not isinstance(data, (bytes, bytearray)):
        return out

    for field_number, wire_type, value in decode_wire(data):
        if wire_type != 2 or not isinstance(value, bytes):
            continue
        text = _decode_readable(value)
        if text is not None and len(text.strip()) >= 2:
            out.append((depth, text))
        # Always descend: a payload that decodes as printable text can still
        # be a length-delimited container (e.g. "\n6<text>").
        _strings_with_depth(value, depth + 1, out)
    return out


def extract_strings(data: bytes, min_len: int = 2) -> list[str]:
    """Recursively extract human readable UTF-8 strings from a wire payload.

    Binary payloads with a high ratio of non-printable bytes are skipped as
    payloads, but are still searched recursively.  Pure numeric strings,
    ``WN...`` internal server ids and md5-like hex strings are filtered out.
    """
    if not isinstance(data, (bytes, bytearray)):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for _depth, text in _strings_with_depth(bytes(data)):
        stripped = text.strip()
        if len(stripped) < min_len or _is_noise(text):
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        result.append(text)
    return result


def _best_text(data: Optional[bytes]) -> str:
    """Pick the deepest readable string from *data* (longest on ties)."""
    if not isinstance(data, (bytes, bytearray)):
        return ""
    candidates = [
        (depth, text) for depth, text in _strings_with_depth(bytes(data))
        if len(text.strip()) >= 2 and not _is_noise(text)
    ]
    if not candidates:
        return ""
    deepest = max(depth for depth, _text in candidates)
    deepest_texts = [text for depth, text in candidates if depth == deepest]
    return _clean_text(max(deepest_texts, key=lambda item: len(item.strip())))


_INTERNAL_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{8,}")


def _is_internal_token(text: str) -> bool:
    """True when *text* is a bare internal identifier (base64url style token)."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    if _INTERNAL_TOKEN_RE.fullmatch(stripped):
        return True
    # Semicolon/comma separated lists of internal ids are not readable either.
    parts = [part for part in re.split(r"[;,|]", stripped) if part]
    return len(parts) > 1 and all(_INTERNAL_TOKEN_RE.fullmatch(part) for part in parts)


def _readable_text(data: Optional[bytes]) -> str:
    """Readable text from either a plain UTF-8 payload or a wire structure."""
    if not isinstance(data, (bytes, bytearray)):
        return ""
    decoded = _decode_readable(bytes(data))
    if decoded is not None and decoded.strip():
        return _clean_text(decoded)
    return _best_text(data)


# ---------------------------------------------------------------------------
# Field helpers
# --------------------------------------------------------------------


def _field_values(fields: list[tuple[int, int, object]], number: int, wire_type: Optional[int] = None) -> list[object]:
    return [
        value for field_number, wtype, value in fields
        if field_number == number and (wire_type is None or wtype == wire_type)
    ]


def _field_bytes(fields: list[tuple[int, int, object]], number: int) -> list[bytes]:
    return [value for value in _field_values(fields, number, 2) if isinstance(value, bytes)]


def _first_bytes(fields: list[tuple[int, int, object]], number: int) -> Optional[bytes]:
    values = _field_bytes(fields, number)
    return values[0] if values else None


def _first_int(fields: list[tuple[int, int, object]], number: int) -> Optional[int]:
    for field_number, wire_type, value in fields:
        if field_number == number and wire_type == 0 and isinstance(value, int):
            return value
    return None


def _first_str(fields: list[tuple[int, int, object]], number: int) -> str:
    for value in _field_bytes(fields, number):
        text = _decode_readable(value)
        if text is not None and text.strip():
            return _clean_text(text)
    return ""


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = "".join(ch if ch in "\n\r\t" or ord(ch) >= 32 else "" for ch in text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _truncate(text: str, limit: int = 80) -> str:
    flat = " ".join(text.split())
    return flat[:limit]


# ---------------------------------------------------------------------------
# Attachment helpers
# ---------------------------------------------------------------

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic"}
_VOICE_EXTS = {".silk", ".slk", ".amr"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv"}


def _kind_from_name(name: str) -> str:
    ext = os.path.splitext(name or "")[1].lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _VOICE_EXTS:
        return "voice"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext:
        return "file"
    return "unknown"


def _attachment_from_payload(payload: bytes, kind_hint: Optional[str] = None) -> dict:
    fields = decode_wire(payload)
    name = _first_str(fields, 2)
    size = _first_int(fields, 4) or 0
    server_id = _first_str(fields, 1) or _first_str(fields, 3)
    md5 = _first_str(fields, 10)
    if not md5:
        for text in extract_strings(payload, min_len=32):
            if re.fullmatch(r"[0-9a-fA-F]{32}", text.strip()):
                md5 = text.strip()
                break
    kind = kind_hint or _kind_from_name(name)
    return {
        "name": name,
        "size": int(size),
        "server_id": server_id,
        "md5": md5,
        "kind": kind,
    }


def _item_sender(fields: list[tuple[int, int, object]]) -> str:
    """Sender of a forwarded/quoted item, read from field 11 or nested field 1/2."""
    sender = _first_str(fields, 11)
    if sender:
        return sender
    payload = _first_bytes(fields, 1)
    if payload:
        sender = _first_str(decode_wire(payload), 2)
        if not sender:
            nested = _first_bytes(decode_wire(payload), 2)
            if nested:
                sender = _first_str(decode_wire(nested), 2)
        if sender:
            return sender
    content = _first_bytes(fields, 101)
    if content:
        content_fields = decode_wire(content)
        first = _first_bytes(content_fields, 1)
        if first:
            nested = _first_bytes(decode_wire(first), 2)
            if nested:
                return _first_str(decode_wire(nested), 2)
    return ""


def _submessage_kind(sub_type: Optional[int]) -> str:
    if sub_type in (0, 2):
        return "text"
    if sub_type in (48, 14, 4):
        return "image"
    if sub_type == 15:
        return "file"
    if sub_type == 16:
        return "voice"
    if sub_type == 17:
        return "video"
    if sub_type == 13:
        return "link"
    return "unknown"


# ---------------------------------------------------------------------------
# Result constructors
# ---------------------------------------------------------------


def _make_card(
    title: str = "",
    description: str = "",
    url: str = "",
    source: str = "",
    items: Optional[list[dict]] = None,
    time_text: str = "",
    location: str = "",
    duration: str = "",
) -> dict:
    return {
        "title": title or None,
        "description": description or None,
        "url": url or None,
        "source": source or None,
        "items": items or [],
        "time_text": time_text or None,
        "location": location or None,
        "duration": duration or None,
    }


def _empty(kind: str = "unknown") -> dict:
    return {
        "kind": kind,
        "text": "",
        "summary": "",
        "quote": None,
        "files": [],
        "card": None,
        "items": [],
    }


def _summary_for(kind: str, text: str, files: list[dict], card: Optional[dict], items: list[dict]) -> str:
    name = files[0].get("name", "") if files else ""
    if kind == "text":
        return _truncate(text)
    if kind == "image":
        return f"[图片] {name}".strip()
    if kind == "file":
        return f"[文件] {name}".strip()
    if kind == "video":
        return f"[视频] {name}".strip()
    if kind == "voice":
        return "[语音]"
    if kind == "link":
        title = (card or {}).get("title") or ""
        return f"[链接] {title}".strip()
    if kind == "app":
        title = (card or {}).get("title") or _truncate(text)
        return f"[应用] {title}".strip()
    if kind == "forward":
        return f"[聊天记录] {len(items)}条" if items else "[聊天记录]"
    if kind == "sticker":
        return f"[表情] {_truncate(text)}".strip()
    if kind == "call":
        duration = (card or {}).get("duration") or ""
        return f"[通话] {duration}".strip()
    if kind == "meeting":
        title = (card or {}).get("title") or ""
        return f"[会议] {title}".strip()
    if kind == "system":
        flat = _truncate(text)
        if not flat or flat == "系统消息":
            return "[系统消息]"
        return f"[系统消息] {flat}"
    return _truncate(text)


def _result(kind: str, text: str = "", files: Optional[list[dict]] = None,
            card: Optional[dict] = None, quote: Optional[dict] = None,
            items: Optional[list[dict]] = None) -> dict:
    files = files or []
    items = items or []
    result = _empty(kind)
    result["text"] = text or ""
    result["files"] = files
    result["card"] = card
    result["quote"] = quote
    result["items"] = items
    result["summary"] = _summary_for(kind, result["text"], files, card, items)
    return result


# ---------------------------------------------------------------------------
# Type specific decoders
# ---------------------------------------------------------------


def _decode_text_message(raw: Optional[bytes], raw_str: str) -> dict:
    text = raw_str.strip() if raw_str else _best_text(raw)
    return _result("text", text)


def _decode_direct_media(content_type: int, raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []
    name = _first_str(fields, 2)
    size = _first_int(fields, 4) or 0
    server_id = _first_str(fields, 1) or _first_str(fields, 3)
    md5 = _first_str(fields, 10)

    if content_type in (48, 14):
        kind = "image"
    elif content_type == 16:
        kind = "voice"
    else:
        kind = "file"

    files = [{
        "name": name,
        "size": int(size),
        "server_id": server_id,
        "md5": md5,
        "kind": kind,
    }]
    card = None
    if content_type == 16:
        duration = _first_int(fields, 7) or 0
        card = _make_card(
            title="语音",
            duration=(f"{duration}″" if duration else ""),
        )
    return _result(kind, "", files=files, card=card)


def _decode_video(raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []
    path = _first_str(fields, 1)
    name = os.path.basename(path.replace("\\", "/")) if path else ""
    server_id = _first_str(fields, 2) or _first_str(fields, 7)
    size = _first_int(fields, 3) or _first_int(fields, 14) or 0
    md5 = _first_str(fields, 9)
    files = [{
        "name": name,
        "size": int(size),
        "server_id": server_id,
        "md5": md5,
        "kind": "video",
    }]
    return _result("video", "", files=files)


def _decode_forward(raw: Optional[bytes]) -> dict:
    items: list[dict] = []
    for payload in _field_bytes(decode_wire(raw) if raw else [], 1):
        fields = decode_wire(payload)
        sender = _item_sender(fields)
        sub_type = _first_int(fields, 5)
        kind = _submessage_kind(sub_type)

        text_payload = _first_bytes(fields, 101)
        text = _best_text(text_payload) if text_payload else ""
        if text and text == sender:
            text = ""

        files: list[dict] = []
        for attach_payload in _field_bytes(fields, 103):
            hint = kind if kind in ("image", "file", "voice", "video") else None
            files.append(_attachment_from_payload(attach_payload, hint))

        if not text and kind == "text":
            text = _best_text(payload)

        if not (sender or text or files):
            continue

        item_kind = kind
        if item_kind == "unknown" and files:
            item_kind = files[0]["kind"]

        items.append({
            "sender": sender,
            "text": text,
            "files": files,
            "kind": item_kind,
        })

    text = "\n".join(item["text"] for item in items if item["text"])
    return _result("forward", text, items=items)


def _decode_quote(raw: Optional[bytes]) -> dict:
    items: list[dict] = []

    for payload in _field_bytes(decode_wire(raw) if raw else [], 1):
        fields = decode_wire(payload)
        sender = _item_sender(fields)
        sub_type = _first_int(fields, 5)
        kind = _submessage_kind(sub_type)

        text_payload = _first_bytes(fields, 101)
        text = _best_text(text_payload) if text_payload else ""
        if text and text == sender:
            text = ""

        files: list[dict] = []
        for attach_payload in _field_bytes(fields, 103):
            hint = kind if kind in ("image", "file", "voice", "video") else None
            files.append(_attachment_from_payload(attach_payload, hint))

        items.append({
            "sender": sender,
            "text": text,
            "files": files,
            "kind": kind,
        })

    if not items:
        return _result("quote", _best_text(raw))

    body = items[0]
    quoted = items[1:]

    files: list[dict] = []
    seen_files: set[tuple[str, str]] = set()
    for item in items:
        for file_info in item["files"]:
            key = (file_info.get("server_id", ""), file_info.get("name", ""))
            if key in seen_files:
                continue
            seen_files.add(key)
            files.append(file_info)

    body_text = body["text"]
    quoted_text = "\n".join(item["text"] for item in quoted if item["text"])
    quoted_sender = next((item["sender"] for item in quoted if item["sender"]), "")
    if not quoted_sender:
        # Some clients put the quoted message (sender + text) first and the
        # reply attachments afterwards, so the sender lives in the body item.
        quoted_sender = body["sender"]

    if files:
        kind = files[0]["kind"]
    elif body_text or quoted_text:
        kind = "text"
    else:
        kind = "quote"

    text = body_text or quoted_text
    quote = None
    if quoted_text or quoted_sender:
        quote = {"sender": quoted_sender, "text": quoted_text}

    return _result(kind, text, files=files, quote=quote)


def _parse_json(text: str) -> Optional[Any]:
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _decode_570(raw: Optional[bytes], raw_str: str) -> dict:
    text = ""
    fields = decode_wire(raw) if raw else []

    json_payload = _first_bytes(fields, 2)
    json_text = _decode_readable(json_payload) if json_payload else raw_str

    obj = _parse_json(json_text or "")
    if isinstance(obj, dict):
        value = obj.get("text")
        if isinstance(value, str):
            text = _clean_text(value)

    if not text:
        first_payload = _first_bytes(fields, 1)
        text = _best_text(first_payload) if first_payload else (raw_str or "").strip()

    return _result("text", text)


def _host_of(url: str) -> str:
    match = re.match(r"^https?://([^/]+)", url or "")
    return match.group(1) if match else ""


def _decode_link(raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []
    url = _first_str(fields, 1)
    cover = _first_str(fields, 2)
    title = _first_str(fields, 3)
    description = _first_str(fields, 4)
    card = _make_card(
        title=title,
        description=description,
        url=url,
        source=_host_of(url),
    )
    text = title or description
    return _result("link", text, card=card)


def _decode_news(raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []
    items: list[dict] = []
    for payload in _field_bytes(fields, 1):
        item_fields = decode_wire(payload)
        items.append({
            "title": _first_str(item_fields, 1),
            "description": _first_str(item_fields, 2),
            "url": _first_str(item_fields, 3),
            "cover": _first_str(item_fields, 4),
            "source": _first_str(item_fields, 5),
        })

    first = items[0] if items else {}
    card = _make_card(
        title=first.get("title", ""),
        description=first.get("description", ""),
        url=first.get("url", ""),
        source=first.get("source", ""),
        items=items,
    )
    text = first.get("title", "")
    return _result("app", text, card=card)


def _decode_meeting(raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []
    title = _first_str(fields, 1)
    description = _first_str(fields, 2)
    url = _first_str(fields, 3)

    time_match = re.search(r"会议时间[:：]\s*([^\n]+)", description)
    location_match = re.search(r"会议地点[:：]\s*([^\n]+)", description)
    time_text = time_match.group(1).strip() if time_match else ""
    location = location_match.group(1).strip() if location_match else ""

    card = _make_card(
        title=title,
        description=description,
        url=url,
        source=_host_of(url),
        time_text=time_text,
        location=location,
    )
    text = title or description
    return _result("meeting", text, card=card)


def _decode_call(raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []
    text = ""
    for value in _field_bytes(fields, 3):
        decoded = _decode_readable(value)
        if decoded:
            text = _clean_text(decoded)
            break
    if not text:
        text = _best_text(raw)

    duration_match = re.search(r"通话时长\s*([0-9:：]+)", text)
    duration = duration_match.group(1) if duration_match else ""

    card = _make_card(
        title="通话",
        description=text,
        duration=duration,
    )
    return _result("call", text, card=card)


def _decode_sticker(raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []
    text = _first_str(fields, 9) or "自定义表情"
    return _result("sticker", text)


def _decode_meeting_placeholder(raw: Optional[bytes]) -> dict:
    text = _best_text(raw) or "会议消息（暂无详情）"
    card = _make_card(title=text, description="该会议消息无更多详情")
    return _result("meeting", text, card=card)


# ---------------------------------------------------------------------------
# Application / card messages
# ---------------------------------------------------------------


def _find_first_url(value: Any) -> str:
    if isinstance(value, str):
        return value if re.match(r"^https?://", value) else ""
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ("url", "pc_url", "mobile_url", "schema_url") and isinstance(child, str):
                if re.match(r"^https?://", child):
                    return child
        for child in value.values():
            found = _find_first_url(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_first_url(child)
            if found:
                return found
    return ""


def _find_first_text(value: Any, keys: tuple[str, ...]) -> str:
    if isinstance(value, dict):
        for key in keys:
            child = value.get(key)
            if isinstance(child, str) and child.strip():
                return child.strip()
        for child in value.values():
            found = _find_first_text(child, keys)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_first_text(child, keys)
            if found:
                return found
    return ""


def _json_card_fields(payload: bytes) -> dict:
    """Best-effort title/description/url/items extraction from card JSON."""
    json_text = _decode_readable(payload)
    obj = _parse_json(json_text or "")
    if not isinstance(obj, (dict, list)):
        return {}

    title = _find_first_text(obj, ("title",))
    description = _find_first_text(obj, ("sub_title", "desc", "description", "sub_desc"))
    url = _find_first_url(obj)

    items: list[dict] = []
    detail_list = obj.get("detail_list") if isinstance(obj, dict) else None
    if isinstance(detail_list, list):
        for entry in detail_list:
            if not isinstance(entry, dict):
                continue
            items.append({
                "title": entry.get("title") or "",
                "description": entry.get("sub_title") or entry.get("desc") or "",
                "url": _find_first_url(entry),
                "cover": "",
                "source": "",
            })

    return {
        "title": title,
        "description": description,
        "url": url,
        "items": items,
    }


def _decode_app(content_type: int, raw: Optional[bytes]) -> dict:
    fields = decode_wire(raw) if raw else []

    title = ""
    description = ""
    url = ""
    items: list[dict] = []

    if content_type == 145:
        nested = _first_bytes(fields, 11)
        if nested:
            nested_fields = decode_wire(nested)
            url = _first_str(nested_fields, 1)
            title = _first_str(nested_fields, 3)
            description = _first_str(nested_fields, 4)
    elif content_type == 573:
        title = _first_str(fields, 1)
    elif content_type == 520:
        title = _first_str(fields, 4)
        file_name = _first_str(fields, 5)
        file_size = _first_str(fields, 6)
        description = " ".join(part for part in (file_name, file_size) if part)
    elif content_type == 581:
        title = _first_str(fields, 4) or _first_str(fields, 5)
        url = _first_str(fields, 14)

    for number in (2, 13):
        payload = _first_bytes(fields, number)
        if not payload:
            continue
        parsed = _json_card_fields(payload)
        title = title or parsed.get("title", "")
        description = description or parsed.get("description", "")
        url = url or parsed.get("url", "")
        if not items:
            items = parsed.get("items", [])

    if not title:
        title = _best_text(raw)

    card = _make_card(
        title=title,
        description=description,
        url=url,
        source=_host_of(url),
        items=items,
    )
    return _result("app", title, card=card)


def _decode_system(raw: Optional[bytes], extra: Optional[bytes]) -> dict:
    text = _readable_text(raw)
    if _is_internal_token(text):
        text = ""
    if not text and extra:
        candidate = _readable_text(extra)
        if candidate and not _is_internal_token(candidate) and (
            " " in candidate or re.search(r"[\u4e00-\u9fff]", candidate)
        ):
            text = candidate
    return _result("system", text or "系统消息")


def _decode_unknown(raw: Optional[bytes], extra: Optional[bytes]) -> dict:
    text = _best_text(raw)
    if not text and extra:
        text = _best_text(extra)
    return _result("unknown", text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------

_SYSTEM_TYPES = {
    1001, 1002, 1003, 1004, 1005, 1006,
    1016, 1022, 1030, 1051, 1052, 1055,
}


def _coerce_content(content: Any) -> tuple[Optional[bytes], str]:
    if content is None:
        return None, ""
    if isinstance(content, (bytes, bytearray)):
        return bytes(content), ""
    if isinstance(content, str):
        return None, content
    return None, str(content)


def _decode_message(content_type: int, content: Any, extra_content: Any = None) -> dict:
    raw, raw_str = _coerce_content(content)
    extra_raw, _ = _coerce_content(extra_content)

    if content_type in (0, 2):
        return _decode_text_message(raw, raw_str)
    if content_type in (48, 14, 15, 16):
        return _decode_direct_media(content_type, raw)
    if content_type == 17:
        return _decode_video(raw)
    if content_type == 4:
        return _decode_forward(raw)
    if content_type == 123:
        return _decode_quote(raw)
    if content_type == 570:
        return _decode_570(raw, raw_str)
    if content_type == 13:
        return _decode_link(raw)
    if content_type == 35:
        return _decode_news(raw)
    if content_type == 38:
        return _decode_meeting(raw)
    if content_type == 40:
        return _decode_call(raw)
    if content_type == 1011:
        return _decode_meeting_placeholder(raw)
    if content_type == 29:
        return _decode_sticker(raw)
    if content_type in (145, 573, 520, 581):
        return _decode_app(content_type, raw)
    if content_type in _SYSTEM_TYPES:
        return _decode_system(raw, extra_raw)
    return _decode_unknown(raw, extra_raw)


def decode_message(content_type: int, content: bytes | str | None,
                   extra_content: bytes | None = None) -> dict:
    """Decode a WeCom message body into a stable presentation structure.

    The return value always contains ``kind``, ``text``, ``summary``,
    ``quote``, ``files``, ``card`` and ``items``.  This function never raises;
    on unexpected input an ``unknown`` result is returned.
    """
    try:
        try:
            message_type = int(content_type)
        except (TypeError, ValueError):
            message_type = -1
        return _decode_message(message_type, content, extra_content)
    except Exception:
        return _empty("unknown")
