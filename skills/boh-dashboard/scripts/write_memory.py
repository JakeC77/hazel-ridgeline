#!/usr/bin/env python3
"""
Write a session log entry to memory/<firm-id>/YYYY-MM-DD.md
Optionally update memory/<firm-id>/MEMORY.md with a long-term fact.

Multi-tenant: --firm-id is REQUIRED. Memory is firm-scoped so writes from
one firm's turn cannot leak into another firm's memory. The agent reads
the current firm's ID from the [FIRM CONTEXT] block in the user message
prefix and passes it here. For the Ridgeline dev persona (no real firm
row in Supabase) pass the literal string "ridgeline".

Usage:
  python3 write_memory.py \\
    --firm-id <firm_uuid_or_ridgeline> \\
    --date "2026-03-21" \\
    --channel "dashboard" \\
    --summary "Marcus asked about framing schedule on Harlow. Told him 4 days behind." \\
    --notes "He prefers direct numbers, no hedging." \\
    [--memory-update "Marcus prefers Net 30 on all change orders"]
"""
import sys, os, argparse
from datetime import datetime
from pathlib import Path

BUILDER_DIR = Path(
    os.getenv("HAZEL_BUILDER_DIR", "/home/openclaw/.openclaw/workspace/hazel/builders/ridgeline")
)

def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--firm-id",
        required=True,
        help=(
            "Firm identifier for the memory directory (UUID for real firms, "
            "'ridgeline' for the dev persona). REQUIRED — do not guess."
        ),
    )
    p.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--channel", default="unknown", help="whatsapp|clawdtalk|dashboard")
    p.add_argument("--summary", required=True, help="What happened this session")
    p.add_argument("--notes",   default="", help="Anything worth remembering long-term")
    p.add_argument("--memory-update", default="", help="One-liner to add to MEMORY.md")
    args = p.parse_args()

    # Firm-scope the memory directory so writes cannot cross firm boundaries.
    memory_dir = BUILDER_DIR / "memory" / args.firm_id
    memory_dir.mkdir(parents=True, exist_ok=True)

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

    print(f"✅ Daily log written: memory/{args.firm_id}/{log_path.name}")

    # ── MEMORY.md update ─────────────────────────────────────────────────────
    if args.memory_update.strip():
        mem_path = memory_dir / "MEMORY.md"
        ts = datetime.now().strftime("%Y-%m-%d")
        fact = f"- [{ts}] {args.memory_update.strip()}\n"
        if mem_path.exists():
            mem_path.write_text(mem_path.read_text() + fact)
        else:
            mem_path.write_text(f"# Hazel — Long-Term Memory (firm {args.firm_id})\n\n{fact}")
        print(f"✅ MEMORY.md updated")

if __name__ == "__main__":
    main()
