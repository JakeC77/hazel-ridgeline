#!/usr/bin/env python3
"""
resolve_firm_by_phone.py — Given a caller phone number, find which firm owns
the relationship via a cross-firm `contacts` lookup.

This is the first step in the SMS/voice pathway. Unlike dashboard chat (where
firm context arrives in the [FIRM CONTEXT] message prefix) or email (where the
hazel-plugin resolves firm before forwarding), SMS arrives via ClawdTalk with
no firm attribution. Hazel has to resolve it herself before she can do anything
firm-scoped.

The output mirrors the plugin's matchEmailGlobally logic:

  unique      — exactly one firm has this phone in contacts. Safe to route.
  firm_owner  — no contact match, but the phone matches a firm's own phone
                field (i.e. the builder is texting directly). firm_id and
                user_id (owner) are returned.
  ambiguous   — multiple firms have this phone. Do not guess; ask the caller
                or route to triage.
  unmatched   — no contact row and no firm match. Unknown caller; handle per
                the unknown-sender rules in AGENTS.md.

Usage:
  python3 resolve_firm_by_phone.py --phone "+12069631303"
  python3 resolve_firm_by_phone.py --phone "12069631303"

Outputs JSON:
  { "kind": "unique", "firm_id": "...", "contact_id": "...",
    "name": "...", "email": "...", "project_id": "..." }
  { "kind": "ambiguous", "firm_ids": ["...", "..."] }
  { "kind": "unmatched" }
"""
import argparse, json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import client as SB


def normalize_last10(phone: str) -> str:
    """Strip to digits, return the last 10 (the NANP subscriber portion).

    We match on the last 10 to avoid formatting drift (+1 vs 1 vs bare, parens,
    dashes, spaces). This is an NANP-centric assumption — extend if Hazel ever
    handles non-NANP numbers.
    """
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def main():
    p = argparse.ArgumentParser(
        description="Resolve a caller phone to a firm via cross-firm contacts lookup."
    )
    p.add_argument("--phone", required=True, help="Caller phone number (any format)")
    p.add_argument(
        "--max-firms",
        type=int,
        default=10,
        help="Cap on distinct firms considered before declaring ambiguous (default 10).",
    )
    args = p.parse_args()

    last10 = normalize_last10(args.phone)
    if not last10:
        print(json.dumps({"kind": "unmatched", "reason": "phone has no digits"}))
        sys.exit(0)

    # Cross-firm match on contacts. No firm_id filter — this is the one place
    # where cross-firm read is legitimate, because firm attribution is what
    # we're trying to learn. All DOWNSTREAM reads after this point must be
    # firm-scoped.
    try:
        contacts = SB.get(
            "contacts",
            {
                "phone": f"ilike.%{last10}%",
                "select": "id,name,email,firm_id",
                "limit": str(max(args.max_firms * 2, 20)),
            },
        )
    except Exception as e:
        print(json.dumps({"kind": "unmatched", "error": str(e)}), file=sys.stderr)
        sys.exit(1)

    if not contacts:
        # Fallback: check firms.phone — this catches builders texting directly,
        # since auth.users phone fields are empty (email-only signup).
        try:
            firms = SB.get(
                "firms",
                {
                    "phone": f"ilike.%{last10}%",
                    "select": "id,display_name,phone",
                    "limit": "5",
                },
            )
        except Exception as e:
            print(json.dumps({"kind": "unmatched", "error": str(e)}), file=sys.stderr)
            sys.exit(1)

        if not firms:
            print(json.dumps({"kind": "unmatched", "phone_last10": last10}))
            return

        if len(firms) > 1:
            print(
                json.dumps(
                    {
                        "kind": "ambiguous",
                        "firm_ids": [f["id"] for f in firms],
                        "phone_last10": last10,
                        "note": (
                            "Caller's phone matches multiple firm records directly. "
                            "Ask the caller which firm they're calling about."
                        ),
                    }
                )
            )
            return

        firm = firms[0]
        # Resolve the owner user_id for the matched firm
        owner_result = {"kind": "firm_owner", "firm_id": firm["id"], "phone_last10": last10}
        try:
            fu = SB.get(
                "firm_users",
                {
                    "firm_id": f"eq.{firm['id']}",
                    "role": "eq.owner",
                    "select": "user_id",
                    "limit": "1",
                },
            )
            if fu:
                owner_result["user_id"] = fu[0]["user_id"]
        except Exception:
            pass
        print(json.dumps(owner_result, indent=2))
        return

    # Distinct firm_ids
    firm_ids = sorted({c["firm_id"] for c in contacts if c.get("firm_id")})

    if len(firm_ids) > 1:
        print(
            json.dumps(
                {
                    "kind": "ambiguous",
                    "firm_ids": firm_ids[: args.max_firms],
                    "phone_last10": last10,
                    "note": (
                        "Caller's phone matches contacts in multiple firms. "
                        "Do not guess — ask the caller which firm they're "
                        "calling about, or route to triage."
                    ),
                }
            )
        )
        return

    # Unique firm match — pick the first contact (if multiple rows in the same
    # firm, take the one with the most signal; for simplicity, first wins).
    contact = contacts[0]
    result = {
        "kind": "unique",
        "firm_id": contact["firm_id"],
        "contact_id": contact["id"],
        "name": contact.get("name"),
        "email": contact.get("email"),
        "phone_last10": last10,
    }

    # Try to find a linked project for the contact (first match wins; a single
    # contact can be on multiple projects — the agent can disambiguate from
    # conversation context if needed).
    try:
        pcs = SB.get(
            "project_contacts",
            {
                "contact_id": f"eq.{contact['id']}",
                "select": "project_id",
                "limit": "1",
            },
        )
        if pcs:
            result["project_id"] = pcs[0]["project_id"]
    except Exception:
        # Non-fatal — firm_id is enough to proceed.
        pass

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
