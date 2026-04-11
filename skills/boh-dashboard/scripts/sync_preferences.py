#!/usr/bin/env python3
"""
sync_preferences.py — Fetch firm_preferences from Supabase and write to workspace.

Writes a human-readable PREFERENCES.md file that Hazel reads on startup.
Run on session start or periodically to keep preferences current.

Usage:
  python3 sync_preferences.py [--output PREFERENCES.md]
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import client as SB


def format_preferences(prefs):
    """Convert preferences row to human-readable markdown."""
    lines = ["# Builder Preferences", ""]

    # Authority thresholds
    lines.append("## Authority Thresholds")
    auto_send = prefs.get("auto_send_threshold_dollars", 0)
    co_review = prefs.get("change_order_review_threshold", 500)
    lines.append(f"- Auto-send threshold: ${auto_send:.0f} (you can send without approval below this)")
    lines.append(f"- Change order review threshold: ${co_review:.0f} (always ask above this)")

    blackout_days = prefs.get("blackout_days", [])
    blackout_start = prefs.get("blackout_start_time", "20:00")
    blackout_end = prefs.get("blackout_end_time", "08:00")
    if blackout_days:
        lines.append(f"- Blackout window: {', '.join(blackout_days)} from {blackout_start} to {blackout_end}")
        lines.append(f"  (Do NOT send anything during blackout hours)")
    else:
        lines.append(f"- Blackout window: none set")
    lines.append("")

    # Communication voice
    lines.append("## Communication Voice")
    tone = prefs.get("tone", "conversational")
    lines.append(f"- Tone: {tone}")
    phrases = prefs.get("custom_phrases", [])
    if phrases:
        lines.append(f"- Custom phrases to use: {', '.join(f'"{p}"' for p in phrases)}")
    follow_up = prefs.get("client_follow_up_days", 3)
    lines.append(f"- Client follow-up cadence: {follow_up} days")
    lines.append("")

    # Jurisdictions
    lines.append("## Jurisdictions")
    primary = prefs.get("primary_jurisdiction")
    jurisdictions = prefs.get("jurisdictions", [])
    if primary:
        lines.append(f"- Primary: {primary}")
    if jurisdictions:
        lines.append(f"- All: {', '.join(jurisdictions)}")
    if not primary and not jurisdictions:
        lines.append("- None set")
    lines.append("")

    # Digest
    digest = prefs.get("daily_digest_enabled", True)
    digest_time = prefs.get("daily_digest_time", "07:30")
    lines.append("## Daily Digest")
    lines.append(f"- Enabled: {'yes' if digest else 'no'}")
    if digest:
        lines.append(f"- Time: {digest_time}")
    lines.append("")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="PREFERENCES.md", help="Output file path")
    args = p.parse_args()

    # Look up firm_id
    try:
        firms = SB.get("firm_users", {"select": "firm_id", "limit": "1"})
        firm_id = firms[0]["firm_id"] if firms else None
    except Exception:
        firm_id = None

    if not firm_id:
        print("Could not determine firm_id", file=sys.stderr)
        sys.exit(1)

    # Fetch preferences
    try:
        prefs_list = SB.get("firm_preferences", {
            "firm_id": f"eq.{firm_id}",
            "limit": "1"
        })
        if not prefs_list:
            print("No preferences found", file=sys.stderr)
            sys.exit(1)
        prefs = prefs_list[0]
    except Exception as e:
        print(f"Failed to fetch preferences: {e}", file=sys.stderr)
        sys.exit(1)

    # Write to file
    content = format_preferences(prefs)

    # Resolve output path relative to workspace root
    output_path = args.output
    if not os.path.isabs(output_path):
        # Walk up from script dir to find workspace root (where AGENTS.md lives)
        d = os.path.dirname(os.path.abspath(__file__))
        for _ in range(10):
            if os.path.exists(os.path.join(d, "AGENTS.md")):
                output_path = os.path.join(d, output_path)
                break
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent

    with open(output_path, "w") as f:
        f.write(content)

    print(f"Preferences written to {output_path}")
    print(content)


if __name__ == "__main__":
    main()
