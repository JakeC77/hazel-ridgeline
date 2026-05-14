#!/usr/bin/env python3
"""
fetch_file.py — Pull a file from Supabase Storage into Hazel's sandbox.

Use when Hazel wants to see file contents (image, doc, etc.). Downloads the
bytes from Supabase Storage into the current working directory under
./inbox/<file_id>.<ext>, then prints the local path. Pipe the path into the
Read tool to actually view the content (Read returns images as multimodal
content blocks the LLM can see; PDFs/text as text).

Usage:
    python3 skills/boh-dashboard/scripts/fetch_file.py --file-id <uuid>
    python3 skills/boh-dashboard/scripts/fetch_file.py --storage-path <path>

Examples:
    # When Hazel knows the file_id from the SMS attachment context:
    python3 skills/boh-dashboard/scripts/fetch_file.py --file-id abc-123
    # → prints: ./inbox/abc-123.jpg
    # Then: Read("./inbox/abc-123.jpg") to view it.

    # When Hazel only has the storage_path (e.g. from a files row):
    python3 skills/boh-dashboard/scripts/fetch_file.py --storage-path inbox/firmA/2026-05-14/v3_msg_1.jpg

Output:
  Success: prints the relative local path on stdout, exit 0.
  Failure: prints an error message on stderr, exit 1.

Notes:
- Files go to ./inbox/ relative to CWD. Cleanup happens via cleanup_fetched_files.py
  (or just delete the directory contents periodically — they're a cache).
- For HEIC photos (iPhone), follow up with heic_convert.py to convert before Read.
- Service-role auth via SUPABASE_SERVICE_KEY env var (same as all other skills).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import client as SB  # noqa: E402

import requests  # noqa: E402

BUCKET = "project-files"


def _ext_from_storage_path(path: str) -> str:
    """Pick an extension from the storage_path tail."""
    name = path.rsplit("/", 1)[-1]
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    return "bin"


def _resolve_storage_path(file_id: str) -> tuple[str, str] | None:
    """Look up the storage_path + file_type for a file_id. Returns (path, ext) or None."""
    rows = SB.get(
        "files",
        {"id": f"eq.{file_id}", "select": "storage_path,file_type", "limit": "1"},
    )
    if not rows:
        return None
    row = rows[0]
    path = row.get("storage_path")
    if not path:
        return None
    ext = (row.get("file_type") or _ext_from_storage_path(path)).lstrip(".")
    return path, ext


def _download_to(storage_path: str, local_path: Path) -> int:
    """Stream the object from Supabase Storage to local_path. Returns bytes written."""
    url = f"{SB.SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    headers = {
        "apikey": SB.SUPABASE_KEY,
        "Authorization": f"Bearer {SB.SUPABASE_KEY}",
    }
    r = requests.get(url, headers=headers, stream=True, timeout=60)
    if not r.ok:
        raise RuntimeError(
            f"Storage download failed: HTTP {r.status_code} {r.text[:300]}"
        )
    total = 0
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
    return total


def main():
    p = argparse.ArgumentParser(description=__doc__)
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--file-id", help="UUID of the row in the files table")
    grp.add_argument("--storage-path", help="Direct storage path (skips DB lookup)")
    p.add_argument(
        "--name",
        help="Local filename to save under (default: <file_id>.<ext> or basename of storage path)",
    )
    args = p.parse_args()

    if args.file_id:
        resolved = _resolve_storage_path(args.file_id)
        if not resolved:
            print(f"error: file_id {args.file_id} not found in files table", file=sys.stderr)
            sys.exit(1)
        storage_path, ext = resolved
        local_name = args.name or f"{args.file_id}.{ext}"
    else:
        storage_path = args.storage_path
        ext = _ext_from_storage_path(storage_path)
        # Use the storage tail as the local name unless overridden
        local_name = args.name or storage_path.rsplit("/", 1)[-1]

    local_path = Path("inbox") / local_name

    try:
        size = _download_to(storage_path, local_path)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    # Print just the local path so it pipes cleanly into the next tool call.
    print(f"./{local_path}")
    # Side-info on stderr so it doesn't pollute stdout for piping.
    print(
        f"  saved {size} bytes from {storage_path} (.{ext})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
