#!/usr/bin/env python3
"""
Write a session log entry to memory/YYYY-MM-DD.md
Optionally update MEMORY.md with a long-term fact.

Usage:
  python3 write_memory.py \\
    --date "2026-03-21" \\
    --channel "whatsapp" \\
    --summary "Marcus asked about framing schedule on Harlow. Told him 4 days behind." \\
    --notes "He prefers direct numbers, no hedging." \\
    [--memory-update "Marcus prefers Net 30 on all change orders"]
"""
import sys, os, argparse
from datetime import datetime
from pathlib import Path

BUILDER_DIR = Path(os.getenv("HAZEL_BUILDER_DIR", "/home/openclaw/boh/builders/ridgeline"))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--channel", default="unknown", help="whatsapp|clawdtalk|dashboard")
    p.add_argument("--summary", required=True, help="What happened this session")
    p.add_argument("--notes",   default="", help="Anything worth remembering long-term")
    p.add_argument("--memory-update", default="", help="One-liner to add to MEMORY.md")
    args = p.parse_args()

    memory_dir = BUILDER_DIR / "memory"
    memory_dir.mkdir(exist_ok=True)

    # ── Daily log ─────────────────────────────────────────────────────────────
    log_path = memory_dir / f"{args.date}.md"
    timestamp = datetime.now().strftime("%H:%M UTC")
    entry = f"\n## [{timestamp}] {args.channel.upper()}\n{args.summary.strip()}\n"
    if args.notes.strip():
        entry += f"\n_Notes: {args.notes.strip()}_\n"

    if log_path.exists():
        log_path.write_text(log_path.read_text() + entry)
    else:
        log_path.write_text(f"# Hazel — {args.date}\n{entry}")

    print(f"✅ Daily log written: {log_path.name}")

    # ── MEMORY.md update ─────────────────────────────────────────────────────
    if args.memory_update.strip():
        mem_path = memory_dir / "MEMORY.md"
        ts = datetime.now().strftime("%Y-%m-%d")
        fact = f"- [{ts}] {args.memory_update.strip()}\n"
        if mem_path.exists():
            mem_path.write_text(mem_path.read_text() + fact)
        else:
            mem_path.write_text(f"# Hazel — Long-Term Memory (Ridgeline Builders)\n\n{fact}")
        print(f"✅ MEMORY.md updated")

if __name__ == "__main__":
    main()
