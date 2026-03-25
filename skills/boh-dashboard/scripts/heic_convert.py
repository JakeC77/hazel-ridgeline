#!/usr/bin/env python3
"""
heic_convert.py — Hazel HEIC-to-JPEG conversion worker (Flow 2)

Polls Supabase for `files` rows where:
  - storage_path ends in .heic or .heif (case-insensitive)
  - converted_path IS NULL   (not yet converted)
  - archived = false

For each file:
  1. Download original HEIC from Supabase Storage (service role)
  2. Convert to JPEG using pillow-heif + Pillow (quality 85)
  3. Upload JPEG to project-files/{project_id}/photos/<stem>_converted.jpg
  4. Write storage path back to files.converted_path

Error handling: on failure, logs and leaves converted_path NULL.
The dashboard shows a graceful camera-icon placeholder for NULL converted_path.

Install deps on droplet (one-time):
    pip install pillow-heif Pillow

Usage:
    python3 skills/boh-dashboard/scripts/heic_convert.py          # run once
    python3 skills/boh-dashboard/scripts/heic_convert.py --daemon  # poll every 30s
    python3 skills/boh-dashboard/scripts/heic_convert.py --daemon --interval 60
"""

import argparse
import io
import logging
import os
import sys
import time
from pathlib import Path

# ── add script dir to path so client.py can be imported ───────────────────────
sys.path.insert(0, os.path.dirname(__file__))
import client as SB  # noqa: E402 — local import after path setup

import requests  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [heic_convert] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("heic_convert")

STORAGE_BUCKET = "project-files"
POLL_INTERVAL_SECONDS = 30
JPEG_QUALITY = 85

STORAGE_BASE = f"{SB.SUPABASE_URL}/storage/v1/object"
STORAGE_HEADERS = {
    "apikey": SB.SUPABASE_KEY,
    "Authorization": f"Bearer {SB.SUPABASE_KEY}",
}


# ── Supabase helpers ───────────────────────────────────────────────────────────

MIGRATION_SQL = "ALTER TABLE files ADD COLUMN IF NOT EXISTS converted_path TEXT;"


def check_schema():
    """Verify converted_path column exists. Raises RuntimeError with migration SQL if not."""
    try:
        SB.get("files", params={"select": "converted_path", "limit": "1"})
    except Exception as exc:
        if "converted_path" in str(exc):
            raise RuntimeError(
                "DB schema migration required — 'converted_path' column missing.\n"
                "Run the following in the Supabase SQL editor "
                "(https://supabase.com/dashboard/project/zrolyrtaaaiauigrvusl/sql):\n\n"
                f"  {MIGRATION_SQL}\n\n"
                "Then retry heic_convert.py."
            )
        raise


def fetch_pending_files():
    """Return list of files needing HEIC conversion."""
    rows = SB.get(
        "files",
        params={
            "select": "id,project_id,name,storage_path,category,converted_path",
            "archived": "eq.false",
            "converted_path": "is.null",
            "storage_path": "not.is.null",
        },
    )
    heic_exts = {".heic", ".heif"}
    return [
        r for r in rows
        if Path(r.get("storage_path", "")).suffix.lower() in heic_exts
    ]


def download_from_storage(storage_path: str) -> bytes:
    """Download raw bytes from Supabase Storage (authenticated)."""
    url = f"{STORAGE_BASE}/{STORAGE_BUCKET}/{storage_path}"
    resp = requests.get(url, headers=STORAGE_HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.content


def upload_to_storage(storage_path: str, data: bytes, content_type: str = "image/jpeg"):
    """Upload bytes to Supabase Storage, overwriting if exists."""
    url = f"{STORAGE_BASE}/{STORAGE_BUCKET}/{storage_path}"
    headers = {**STORAGE_HEADERS, "Content-Type": content_type, "x-upsert": "true"}
    resp = requests.post(url, headers=headers, data=data, timeout=60)
    resp.raise_for_status()


def write_converted_path(file_id: str, converted_path: str):
    """Persist converted_path back to the files row."""
    SB.update("files", {"converted_path": converted_path}, {"id": file_id})


# ── Conversion ─────────────────────────────────────────────────────────────────

def convert_heic_to_jpeg(heic_bytes: bytes) -> bytes:
    """Convert HEIC/HEIF bytes → JPEG bytes using pillow-heif + Pillow."""
    try:
        import pillow_heif
        from PIL import Image, ImageOps
    except ImportError:
        raise RuntimeError(
            "pillow-heif / Pillow not installed. Run: pip install pillow-heif Pillow"
        )

    pillow_heif.register_heif_opener()
    img = Image.open(io.BytesIO(heic_bytes))

    # Honour EXIF orientation (common on iPhone photos)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # JPEG doesn't support alpha — flatten to RGB
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


# ── Per-file orchestration ─────────────────────────────────────────────────────

def process_file(row: dict) -> bool:
    """Download, convert, upload, and update one HEIC file. Returns True on success."""
    file_id = row["id"]
    project_id = row["project_id"]
    storage_path = row["storage_path"]
    name = row["name"]

    log.info(f"Processing [{file_id}] {name}")

    try:
        # 1. Download original
        heic_bytes = download_from_storage(storage_path)
        log.info(f"  Downloaded {len(heic_bytes):,} bytes from {storage_path}")

        # 2. Convert to JPEG
        jpeg_bytes = convert_heic_to_jpeg(heic_bytes)
        log.info(f"  Converted to JPEG ({len(jpeg_bytes):,} bytes, quality={JPEG_QUALITY})")

        # 3. Upload JPEG — deterministic path, idempotent on retry
        stem = Path(storage_path).stem
        dest_path = f"{project_id}/photos/{stem}_converted.jpg"
        upload_to_storage(dest_path, jpeg_bytes)
        log.info(f"  Uploaded to {dest_path}")

        # 4. Write back converted_path
        write_converted_path(file_id, dest_path)
        log.info(f"  ✅ Done — converted_path set on files row {file_id}")
        return True

    except Exception as exc:
        log.error(f"  ❌ Failed to convert {name}: {exc}", exc_info=True)
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def run_once() -> tuple:
    """Process all pending HEIC files. Returns (success_count, fail_count)."""
    check_schema()
    pending = fetch_pending_files()
    if not pending:
        log.info("No HEIC files pending conversion.")
        return 0, 0

    log.info(f"Found {len(pending)} file(s) to convert.")
    success = fail = 0
    for row in pending:
        if process_file(row):
            success += 1
        else:
            fail += 1

    return success, fail


def main():
    parser = argparse.ArgumentParser(description="Hazel HEIC conversion worker")
    parser.add_argument("--daemon", action="store_true",
                        help="Poll indefinitely instead of running once")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL_SECONDS,
                        help="Poll interval in seconds (daemon mode)")
    args = parser.parse_args()

    log.info(f"Supabase: {SB.SUPABASE_URL}")

    if args.daemon:
        log.info(f"Daemon mode — polling every {args.interval}s. Ctrl-C to stop.")
        while True:
            try:
                run_once()
            except Exception as exc:
                log.error(f"Unhandled error: {exc}", exc_info=True)
            time.sleep(args.interval)
    else:
        success, fail = run_once()
        log.info(f"Complete — {success} converted, {fail} failed.")
        sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
