#!/usr/bin/env python3
"""
get_firm_context.py — Print the [FIRM CONTEXT] block for a given firm_id.

On dashboard chat and email, hazel-plugin prepends a [FIRM CONTEXT] block to
every agent turn automatically. SMS doesn't go through hazel-plugin, so the
block isn't injected — Hazel has to fetch it herself after resolving firm_id
(via resolve_firm_by_phone.py). This script is that fetch.

The output format is identical to the plugin's buildFirmContext() so Hazel
operates on consistent context regardless of which channel a turn came from.

Usage:
  python3 get_firm_context.py --firm-id <firm_uuid>

Output (stdout): the [FIRM CONTEXT] block, plain text, suitable for reading
directly into your working context for the current turn.

Exits non-zero if firm_id isn't found, so callers can detect the error.
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import client as SB


def build_firm_context_block(firm_id: str) -> str:
    """Return the [FIRM CONTEXT] block as a single string. Raises on lookup failure."""
    firm_rows = SB.get(
        "firms",
        {
            "id": f"eq.{firm_id}",
            "select": "id,display_name,city,state,sign_off_name,sign_off_title",
            "limit": "1",
        },
    )
    if not firm_rows:
        raise LookupError(f"No firm row for firm_id={firm_id}")
    firm = firm_rows[0]

    # Preferences are best-effort — firm row alone is enough to start.
    prefs = {}
    try:
        pref_rows = SB.get(
            "firm_preferences",
            {"firm_id": f"eq.{firm_id}", "limit": "1"},
        )
        if pref_rows:
            prefs = pref_rows[0]
    except Exception:
        pass

    lines = ["[FIRM CONTEXT]"]

    loc_parts = [p for p in (firm.get("city"), firm.get("state")) if p]
    loc = ", ".join(loc_parts)
    if firm.get("display_name"):
        if loc:
            lines.append(f"- Firm: {firm['display_name']} ({loc})")
        else:
            lines.append(f"- Firm: {firm['display_name']}")
    lines.append(f"- Firm ID: {firm_id}")

    if firm.get("sign_off_name"):
        title = f", {firm['sign_off_title']}" if firm.get("sign_off_title") else ""
        lines.append(f"- Primary contact: {firm['sign_off_name']}{title}")

    tone = prefs.get("tone")
    if tone:
        lines.append(f"- Communication tone: {tone}")

    auto_send = prefs.get("auto_send_threshold_dollars")
    if isinstance(auto_send, (int, float)):
        lines.append(
            f"- Auto-send threshold: ${auto_send:.0f} "
            f"(below this you may send without approval, per TRUST.md constraints)"
        )

    co_review = prefs.get("change_order_review_threshold")
    if isinstance(co_review, (int, float)):
        lines.append(
            f"- Change order review threshold: ${co_review:.0f} (always ask above this)"
        )

    follow_up = prefs.get("client_follow_up_days")
    if isinstance(follow_up, (int, float)):
        lines.append(f"- Client follow-up cadence: {int(follow_up)} days")

    blackout_days = prefs.get("blackout_days") or []
    if blackout_days:
        start = prefs.get("blackout_start_time") or "20:00"
        end = prefs.get("blackout_end_time") or "08:00"
        lines.append(
            f"- Blackout window: {', '.join(blackout_days)} from {start} to {end} "
            f"— do NOT send during blackout"
        )

    primary_jurisdiction = prefs.get("primary_jurisdiction")
    if primary_jurisdiction:
        lines.append(f"- Primary jurisdiction: {primary_jurisdiction}")

    jurisdictions = prefs.get("jurisdictions") or []
    if jurisdictions:
        lines.append(f"- All jurisdictions: {', '.join(jurisdictions)}")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Print the [FIRM CONTEXT] block for a firm.")
    p.add_argument(
        "--firm-id",
        required=True,
        help=(
            "Firm UUID. REQUIRED — do not guess. If you don't know it yet and "
            "you're processing an SMS, call resolve_firm_by_phone.py first."
        ),
    )
    args = p.parse_args()

    try:
        block = build_firm_context_block(args.firm_id)
    except LookupError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"get_firm_context failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(block)


if __name__ == "__main__":
    main()
