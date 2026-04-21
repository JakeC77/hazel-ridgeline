# Change Order Procedures

## Standard flow
1. Marcus mentions scope change (WhatsApp or voice)
2. Hazel queries graph for contract context, existing COs
3. Hazel drafts CO via write_draft.py → appears in dashboard queue
4. Hazel texts Marcus: "CO-XXX is in your queue — takes 30 seconds to approve."
5. Marcus edits if needed, approves on dashboard
6. Hazel executes: SMS CO to client via ClawdTalk, logs to graph

## CO numbering
- Pull latest CO number from graph before drafting
- Increment by 1

## Defaults (update as Marcus reveals preferences)
- Payment terms: Net 30 (assumed — confirm with Marcus)
- Client approval method: SMS

## Notes
- (add lessons learned from real COs)
