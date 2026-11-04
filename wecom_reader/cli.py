"""CLI entry point for wecom-reader.

All commands output JSON by default. Use --table for human-readable tables.

JSON is emitted as UTF-8 regardless of the Windows console code page, so piping
the output into other tools (or an agent) yields valid, readable Chinese. Set
``WECOM_READER_ENCODING=native`` to keep the console's own encoding instead.
"""

import json
import os
import sys

import click

from .reader import WeComReader


def _ensure_utf8_stdout():
    """Switch stdout to UTF-8 unless the caller asked for native encoding."""
    if os.environ.get("WECOM_READER_ENCODING", "").lower() == "native":
        return
    encoding = (sys.stdout.encoding or "").lower().replace("-", "")
    if encoding in ("utf8", "utf_8"):
        return
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape")
    except (OSError, ValueError):
        pass


def _json_output(data, pretty=True):
    """Print JSON to stdout."""
    kwargs = {"ensure_ascii": False}
    if pretty:
        kwargs["indent"] = 2
    click.echo(json.dumps(data, **kwargs))


def pass_db_options(f):
    """Let --db-dir / --decrypted-dir be given after a subcommand too.

    Click only accepts group-level options before the subcommand name
    (``cli --db-dir X init``). This decorator adds equivalent options to
    each command so the documented form ``cli init --db-dir X`` also works.
    """

    f = click.option(
        "--db-dir",
        envvar="WXWORK_DB_DIR",
        default=None,
        help="WeCom data directory",
    )(f)
    f = click.option(
        "--decrypted-dir",
        default=None,
        help="Decrypted DB output directory",
    )(f)
    return f


def _get_reader(ctx, db_dir=None, decrypted_dir=None, process_name=None):
    """Return the reader for this command, honoring subcommand options."""
    reader = ctx.obj.get("reader")
    names = [process_name] if process_name else None
    if db_dir is not None or decrypted_dir is not None or names is not None:
        reader = WeComReader(
            db_dir=db_dir if db_dir is not None else reader.db_dir,
            decrypted_dir=(
                decrypted_dir if decrypted_dir is not None else reader.decrypted_dir
            ),
            process_names=names,
        )
    return reader


@click.group()
@click.option("--db-dir", envvar="WXWORK_DB_DIR", help="WeCom data directory")
@click.option("--decrypted-dir", default="wxwork_decrypted", help="Decrypted DB output directory")
@click.pass_context
def main(ctx, db_dir, decrypted_dir):
    """wecom-reader — Read WeCom (企业微信) local chat history.

    Agent-reusable tool for querying WeCom chat data.
    All commands output JSON by default.
    """
    _ensure_utf8_stdout()
    ctx.ensure_object(dict)
    ctx.obj["reader"] = WeComReader(db_dir=db_dir, decrypted_dir=decrypted_dir)


@main.command()
@click.option("--timeout", default=120, help="Memory scan timeout (seconds)")
@click.option("--verbose", "-v", is_flag=True, help="Print progress")
@click.option(
    "--process-name",
    default=None,
    envvar="WXWORK_PROCESS_NAME",
    help="Client executable to scan for the key. Auto-detected by default "
    "(WXWork.exe, or a private-deployment binary such as airchina.exe).",
)
@pass_db_options
@click.pass_context
def init(ctx, timeout, verbose, process_name, db_dir, decrypted_dir):
    """Extract keys and decrypt all WeCom databases.

    Requires: the client running, admin privileges.
    """
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir, process_name)
    try:
        result = reader.init(timeout=timeout, verbose=verbose)
        _json_output(result)
    except Exception as e:
        _json_output({"success": False, "error": str(e)})
        sys.exit(1)


@main.command()
@pass_db_options
@click.pass_context
def status(ctx, db_dir, decrypted_dir):
    """Check status of decrypted WeCom data."""
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir)
    _json_output(reader.status())


@main.command()
@click.option("--limit", "-n", default=50, help="Max results")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--keyword", "-k", help="Filter by keyword")
@click.option("--type", "session_type", help="Filter by type (R/S/M/O/Y)")
@pass_db_options
@click.pass_context
def sessions(ctx, limit, offset, keyword, session_type, db_dir, decrypted_dir):
    """List WeCom sessions/conversations."""
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir)
    result = reader.list_sessions(
        limit=limit, offset=offset, keyword=keyword, session_type=session_type
    )
    _json_output({"count": len(result), "sessions": result})


@main.command()
@click.argument("session_id")
@click.option("--limit", "-n", default=50, help="Max results")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--since", type=int, help="Unix timestamp filter (>=)")
@click.option("--until", type=int, help="Unix timestamp filter (<)")
@pass_db_options
@click.pass_context
def messages(ctx, session_id, limit, offset, since, until, db_dir, decrypted_dir):
    """Get messages for a conversation.

    SESSION_ID: Conversation ID (e.g. R:12345, S:1_2, O:67890)
    """
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir)
    result = reader.get_messages(
        session_id, limit=limit, offset=offset, since=since, until=until
    )
    _json_output({"count": len(result), "messages": result})


@main.command()
@click.argument("keyword")
@click.option("--limit", "-n", default=50, help="Max results")
@click.option("--session", "session_id", help="Filter by session ID")
@pass_db_options
@click.pass_context
def search(ctx, keyword, limit, session_id, db_dir, decrypted_dir):
    """Search messages by keyword."""
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir)
    result = reader.search_messages(keyword, conversation_id=session_id, limit=limit)
    _json_output({"count": len(result), "results": result})


@main.command()
@click.option("--keyword", "-k", help="Filter by name/account")
@click.option("--limit", "-n", default=100, help="Max results")
@click.option("--offset", default=0, help="Pagination offset")
@pass_db_options
@click.pass_context
def contacts(ctx, keyword, limit, offset, db_dir, decrypted_dir):
    """List WeCom contacts."""
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir)
    result = reader.contacts(keyword=keyword, limit=limit, offset=offset)
    _json_output({"count": len(result), "contacts": result})


@main.command()
@click.argument("session_id")
@pass_db_options
@click.pass_context
def group_members(ctx, session_id, db_dir, decrypted_dir):
    """Get group members for a conversation."""
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir)
    result = reader.group_members(session_id)
    _json_output({"count": len(result), "members": result})


@main.command()
@click.argument("session_id")
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json")
@click.option("--output", "-o", help="Output file path")
@pass_db_options
@click.pass_context
def export(ctx, session_id, fmt, output, db_dir, decrypted_dir):
    """Export a conversation to JSON or CSV."""
    reader: WeComReader = _get_reader(ctx, db_dir, decrypted_dir)
    messages = reader.get_messages(session_id, limit=10000)

    if fmt == "json":
        data = json.dumps(messages, ensure_ascii=False, indent=2)
    elif fmt == "csv":
        import csv
        import io
        buf = io.StringIO()
        if messages:
            writer = csv.DictWriter(buf, fieldnames=messages[0].keys())
            writer.writeheader()
            writer.writerows(messages)
        data = buf.getvalue()

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(data)
        _json_output({"success": True, "output": output, "count": len(messages)})
    else:
        click.echo(data)


if __name__ == "__main__":
    main()
