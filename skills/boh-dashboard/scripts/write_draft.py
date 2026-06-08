#!/usr/bin/env python3
"""
Write a draft item to the builder's approval queue.

Usage:
  python3 write_draft.py \
    --project-id <uuid> \
    --type change-order|email|sms|invoice|daily-log|needs-info \
    --title "CO-006 · Deck Addition" \
    --meta "To: Sarah Harlow · $8,200 add" \
    --draft-type plaintext|structured \
    --draft '{"content": "..."}' \
    [--escalated] [--escalate-reason "..."]

Draft format:
  plaintext:  --draft '"Email body text here"'
  structured: --draft '{"fields": [{"label": "Amount", "value": "$4,800"}]}'

Email drafts (--type email) MUST use structured format with:
  --draft '{"to": "Name <email@example.com>", "subject": "...", "body": "..."}'
  The "to" field MUST contain valid email addresses.
  Multiple recipients: "Name <a@b.com>, Other <c@d.com>"

SMS drafts (--type sms) MUST use structured format with:
  --draft '{"to": "+15551234567", "body": "Your message here"}'
  The "to" field MUST be a phone number (E.164 preferred, 10-digit US accepted).
  The phone MUST match a contact in this firm with sms_consent=true.
  If you don't have a consenting contact for that number, draft a
  --type needs-info instead and ask the builder to add the contact.
  Outbound SMS to anyone other than the firm owner ALWAYS requires
  the builder's per-message approval — there is no autonomy tier or
  builder instruction that overrides this.

Outputs: JSON with the created queue_item row (includes id). For --type sms,
also creates a linked pending_outbound_sms row; that row's id and short_ref
are included in the output under "pending_sms".
"""
import sys, os, json, argparse, re, random
sys.path.insert(0, os.path.dirname(__file__))
import client as SB

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# 30-char alphabet for short_ref. Excludes 0/O/1/I/L to avoid lookalikes
# when builders type the ref back via SMS. Matches the plugin's
# SmsApprovalParser.generateShortRef alphabet exactly.
SHORT_REF_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def normalize_us_phone(raw):
    """Normalize a phone string to E.164 (+1XXXXXXXXXX). Returns None
    if the input doesn't look like a valid US number."""
    if not raw:
        return None
    trimmed = str(raw).strip()
    if trimmed.startswith("+"):
        digits = re.sub(r"\D", "", trimmed[1:])
        if len(digits) == 11 and digits.startswith("1"):
            return "+" + digits
        return None
    digits = re.sub(r"\D", "", trimmed)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def generate_short_ref():
    """4-char alphanumeric ID, e.g. 'A4B7'. Caller retries on collision
    against pending_outbound_sms's partial unique index."""
    return "".join(random.choice(SHORT_REF_ALPHABET) for _ in range(4))


def validate_email_draft(draft):
    """Validate that an email draft has required fields with valid email addresses.
    Returns (ok, error_message)."""
    if not isinstance(draft, dict):
        return False, (
            "Email drafts must be structured JSON with: to, subject, body.\n"
            'Example: --draft \'{"to": "Name <email@example.com>", "subject": "...", "body": "..."}\''
        )

    to = draft.get("to", "")
    subject = draft.get("subject", "")
    body = draft.get("body", "")

    errors = []

    if not to:
        errors.append('"to" field is required and must contain an email address.')
    elif not EMAIL_REGEX.search(to):
        errors.append(
            f'"to" field must contain a valid email address. Got: "{to}"\n'
            'Use format: "Name <email@example.com>" or just "email@example.com"'
        )

    if not subject:
        errors.append('"subject" field is required.')

    if not body:
        errors.append('"body" field is required.')

    if errors:
        return False, "Email draft validation failed:\n- " + "\n- ".join(errors)

    return True, ""


def validate_sms_draft(draft, firm_id):
    """Validate that an SMS draft has a phone + body, and that the phone
    resolves to a consenting contact for this firm.

    Returns (ok, error_message, normalized_phone, contact_row_or_None).
    contact_row is None when validation failed; non-None when ok=True.

    Why the consent check is enforced HERE: write_draft.py is the ONLY
    legitimate path for the agent to compose outbound SMS to anyone
    other than the firm owner (see docs/sms-safety-hardening-spec.md
    in hazel-plugin). Refusing to draft for a contact without consent
    keeps the safety promise — and the safety promise is what's keeping
    Hazel out of trouble with Carrier compliance, too.
    """
    if not isinstance(draft, dict):
        return False, (
            "SMS drafts must be structured JSON with: to, body.\n"
            'Example: --draft \'{"to": "+15551234567", "body": "Your message"}\''
        ), None, None

    to_raw = draft.get("to", "")
    body = draft.get("body", "")

    errors = []
    if not to_raw:
        errors.append('"to" field is required and must contain a phone number.')
    if not body:
        errors.append('"body" field is required.')
    if errors:
        return False, "SMS draft validation failed:\n- " + "\n- ".join(errors), None, None

    normalized = normalize_us_phone(to_raw)
    if not normalized:
        return False, (
            f'"to" field must be a valid US phone number (E.164 preferred). Got: "{to_raw}"\n'
            'Use format: "+15551234567" or "555-123-4567".'
        ), None, None

    if len(body) > 1400:
        return False, (
            f'"body" is {len(body)} chars; max 1400 (Telnyx hard cap). '
            "Trim before drafting."
        ), None, None

    # Look up the contact in this firm by last-10 digit match.
    if not firm_id:
        return False, (
            "Cannot resolve contact: no firm_id available for this project. "
            "This is a data issue, not a draft issue — surface to builder."
        ), None, None

    last10 = re.sub(r"\D", "", normalized)[-10:]
    try:
        contacts = SB.get("contacts", {
            "firm_id": f"eq.{firm_id}",
            "phone": f"ilike.%{last10}%",
            "select": "id,name,type,sms_consent",
            "limit": "1",
        })
    except Exception as e:
        return False, (
            f"Failed to look up contact for {normalized}: {e}. "
            "Try again later."
        ), None, None

    if not contacts:
        return False, (
            f"No contact in this firm has the phone {normalized}.\n"
            "The builder needs to add this contact before Hazel can draft "
            "SMS to them. Use --type needs-info to ask the builder to add "
            "the contact, then re-draft once they have."
        ), None, None

    contact = contacts[0]
    if not contact.get("sms_consent"):
        return False, (
            f'Contact "{contact.get("name") or normalized}" is in your '
            "roster but has sms_consent=false. The builder needs to flip "
            "SMS consent on this contact (in the contact card on the "
            "dashboard) before Hazel can text them. SMS consent is a "
            "carrier compliance requirement, not just a Hazel rule."
        ), None, None

    return True, "", normalized, contact


def insert_pending_outbound_sms(queue_item_id, firm_id, project_id,
                                  contact_id, to_phone, body):
    """Insert a pending_outbound_sms row linked to a queue_items row.
    Retries up to 3 times on short_ref collision (the partial unique
    index in migration 037 — same firm + still-actionable status).
    Returns the inserted row, or raises on persistent failure."""
    for attempt in range(3):
        short_ref = generate_short_ref()
        row = {
            "firm_id": firm_id,
            "project_id": project_id,
            "queue_item_id": queue_item_id,
            "contact_id": contact_id,
            "short_ref": short_ref,
            "to_phone": to_phone,
            "body": body,
            "source": "initiated",  # agent-initiated outbound (vs 'reply' / 'voice_fallback')
            # status, created_at, expires_at default in the DB.
        }
        try:
            result = SB.insert("pending_outbound_sms", row)
            return result[0] if isinstance(result, list) else result
        except Exception as e:
            # 23505 is Postgres unique-constraint violation; PostgREST
            # surfaces it via 409 with that code in the body. Retry with
            # a new ref. Any other failure is fatal.
            msg = str(e)
            if "23505" in msg or "duplicate key" in msg.lower():
                if attempt < 2:
                    continue
            raise
    raise RuntimeError("insert_pending_outbound_sms: short_ref collision after 3 attempts")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--type", required=True,
                   choices=["change-order","email","sms","invoice","daily-log","needs-info"])
    p.add_argument("--title", required=True)
    p.add_argument("--meta", default="")
    p.add_argument("--draft-type", default="plaintext", choices=["plaintext","structured"])
    p.add_argument("--draft", required=True, help="JSON-encoded draft content")
    p.add_argument("--escalated", action="store_true")
    p.add_argument("--escalate-reason", default=None)
    args = p.parse_args()

    draft = json.loads(args.draft)

    # Look up firm_id from project (needed for SMS validation too)
    try:
        proj = SB.get("projects", {"id": f"eq.{args.project_id}", "select": "firm_id", "limit": "1"})
        firm_id = proj[0]["firm_id"] if proj else None
    except Exception:
        firm_id = None

    # Validate type-specific drafts. SMS validation also resolves the contact.
    sms_contact = None
    sms_normalized_phone = None
    if args.type == "email":
        ok, err = validate_email_draft(draft)
        if not ok:
            print(json.dumps({"error": err}), file=sys.stderr)
            sys.exit(1)
    elif args.type == "sms":
        # SMS drafts are always structured.
        if args.draft_type != "structured":
            print(json.dumps({"error": "SMS drafts must use --draft-type structured"}), file=sys.stderr)
            sys.exit(1)
        ok, err, sms_normalized_phone, sms_contact = validate_sms_draft(draft, firm_id)
        if not ok:
            print(json.dumps({"error": err}), file=sys.stderr)
            sys.exit(1)
        # Persist the normalized phone back into the draft so the dashboard
        # preview shows E.164 even if the agent passed dashes/parens.
        draft["to"] = sms_normalized_phone

    row = {
        "project_id": args.project_id,
        "type": args.type,
        "title": args.title,
        "meta": args.meta,
        "status": "active",
        "draft_type": args.draft_type,
        "current_draft": draft,
        "original_draft": draft,
        "versions": [{"version": 1, "editor": "hazel", "createdAt": "now"}],
        "escalated": args.escalated,
        "escalate_reason": args.escalate_reason,
    }

    if firm_id:
        row["firm_id"] = firm_id

    result = SB.insert("queue_items", row)
    # Insert returns a list when using return=representation
    item = result[0] if isinstance(result, list) else result

    # For SMS drafts, also create the pending_outbound_sms row linked to
    # this queue_items row. The dashboard's approval flow updates BOTH
    # (queue_item.status='approved' AND pending.status='approved'), then
    # the server-side dispatch endpoint sends via the plugin.
    pending_sms = None
    if args.type == "sms" and item and item.get("id") and firm_id and sms_contact:
        try:
            pending_sms = insert_pending_outbound_sms(
                queue_item_id=item["id"],
                firm_id=firm_id,
                project_id=args.project_id,
                contact_id=sms_contact["id"],
                to_phone=sms_normalized_phone,
                body=draft["body"],
            )
            # Surface the short_ref + pending_id in the item shape returned
            # to the caller — agents that read this output can mention the
            # ref to the builder ("I queued SMS to Sarah, #A4B7 in your queue").
            item["pending_sms"] = {
                "id": pending_sms.get("id"),
                "short_ref": pending_sms.get("short_ref"),
                "to_phone": pending_sms.get("to_phone"),
                "expires_at": pending_sms.get("expires_at"),
            }
        except Exception as e:
            # Roll back the queue_item — without the pending row the
            # dashboard can render the card but the dispatcher has nothing
            # to send. Better to fail-loud than leave a half-staged draft.
            try:
                SB.update("queue_items", {"status": "rejected"}, {"id": item["id"]})
            except Exception:
                pass
            print(json.dumps({
                "error": f"queue_item created but pending_outbound_sms insert failed: {e}. "
                         "Queue item was rolled back to status='rejected'."
            }), file=sys.stderr)
            sys.exit(1)

    # Log to audit_log
    audit = {
        "project_id": args.project_id,
        "icon": "❓" if args.type == "needs-info" else "🤖",
        "message": f"Hazel drafted {args.type}: {args.title}",
        "actor": "Hazel",
        "actor_type": "agent",
        "action_type": "queue_created",
        "triggered_by": "inbound_message",
        "related_entity_type": "queue_item",
    }
    if firm_id:
        audit["firm_id"] = firm_id
    if item and item.get("id"):
        audit["related_entity_id"] = item["id"]
    SB.insert("audit_log", audit)

    print(json.dumps(item, indent=2))

if __name__ == "__main__":
    main()
