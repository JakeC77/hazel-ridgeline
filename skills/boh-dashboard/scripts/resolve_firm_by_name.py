#!/usr/bin/env python3
"""
resolve_firm_by_name.py — Find a firm by display name (fuzzy substring match).

Used on inbound voice calls where ClawdTalk does not pass caller ID (as of
2026-04-20; they're working on it upstream). Since Hazel can't silently look
up the caller by phone, she asks conversationally which contractor they're
calling about, then passes the heard name here to resolve firm_id.

Matching strategy:
  1. Case-insensitive exact match on display_name → if one hit, unique.
  2. Otherwise ilike substring match — matches rows where the provided name
     is contained in the stored display_name (catches "Stone Creek" matching
     "Stone Creek Builders").
  3. If still nothing, try matching individual word tokens from the input
     against display_name (catches "stone creek builders construction" vs
     "Stone Creek Builders").

Returns:
  unique    — exactly one firm matched; safe to proceed.
  multiple  — multiple firms matched; Hazel should read back the candidates
              and ask the caller to clarify.
  unmatched — no firm matched; take a message, don't attempt firm-scoped
              actions.

Usage:
  python3 resolve_firm_by_name.py --name "Stone Creek"
  python3 resolve_firm_by_name.py --name "TestCo"
"""
import argparse, json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import client as SB


def _clean(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()


def main():
    p = argparse.ArgumentParser(description="Resolve a firm by display name.")
    p.add_argument(
        "--name",
        required=True,
        help="What the caller said when asked which contractor (free text).",
    )
    p.add_argument(
        "--max-candidates",
        type=int,
        default=5,
        help="Cap on candidates returned for 'multiple' case (default 5).",
    )
    args = p.parse_args()

    raw = (args.name or "").strip()
    if not raw:
        print(json.dumps({"kind": "unmatched", "reason": "empty name"}))
        sys.exit(0)

    # ── Strategy 1: case-insensitive exact match ──────────────────────────
    try:
        exact = SB.get(
            "firms",
            {
                "display_name": f"ilike.{raw}",
                "select": "id,display_name",
                "limit": "2",
            },
        )
    except Exception as e:
        print(json.dumps({"kind": "unmatched", "error": str(e)}), file=sys.stderr)
        sys.exit(1)

    if len(exact) == 1:
        f = exact[0]
        print(
            json.dumps(
                {
                    "kind": "unique",
                    "firm_id": f["id"],
                    "display_name": f["display_name"],
                    "match_type": "exact",
                }
            )
        )
        return

    # ── Strategy 2: ilike substring — input contained in display_name ─────
    # PostgREST ilike needs the % wildcards literal in the pattern.
    try:
        substring = SB.get(
            "firms",
            {
                "display_name": f"ilike.%{raw}%",
                "select": "id,display_name",
                "limit": str(args.max_candidates + 3),
            },
        )
    except Exception:
        substring = []

    # ── Strategy 3: token-based — any significant input word in display_name
    cleaned_input = _clean(raw)
    tokens = [t for t in cleaned_input.split() if len(t) >= 3]
    token_hits = []
    if tokens and not substring:
        # For each significant token, run an ilike and union results
        seen_ids = set()
        for tok in tokens[:4]:  # cap token queries
            try:
                rows = SB.get(
                    "firms",
                    {
                        "display_name": f"ilike.%{tok}%",
                        "select": "id,display_name",
                        "limit": str(args.max_candidates),
                    },
                )
            except Exception:
                rows = []
            for r in rows:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    token_hits.append(r)

    candidates = substring or token_hits

    if not candidates:
        print(json.dumps({"kind": "unmatched", "input": raw}))
        return

    # Deduplicate by id (shouldn't be needed but safe)
    uniq = {c["id"]: c for c in candidates}.values()
    uniq = list(uniq)[: args.max_candidates]

    if len(uniq) == 1:
        f = uniq[0]
        print(
            json.dumps(
                {
                    "kind": "unique",
                    "firm_id": f["id"],
                    "display_name": f["display_name"],
                    "match_type": "substring" if substring else "token",
                }
            )
        )
        return

    print(
        json.dumps(
            {
                "kind": "multiple",
                "candidates": [
                    {"firm_id": c["id"], "display_name": c["display_name"]}
                    for c in uniq
                ],
                "note": (
                    "Multiple firms matched. Read the display_names back to the "
                    "caller and ask which one they mean. Do not guess."
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
