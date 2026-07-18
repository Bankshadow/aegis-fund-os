# Grid Bot Phase 2 — Durable Governance

## Acceptance criteria

1. Repeating a create request with the same idempotency key returns one bot.
2. Submission moves a draft to `PENDING_APPROVAL`.
3. The maker can never approve or reject their own request.
4. A different checker can approve or reject exactly once.
5. Every accepted mutation appends an immutable SHA-256-linked audit event.
6. Audit-chain verification fails after payload or link tampering.
7. Missing durable storage fails closed; it never falls back to claimed persistence.
8. No transition sends an exchange order. Testnet remains read-only.

## Storage

Cloudflare D1 is the Phase-2 system of record. Migration `0001_grid_bot_governance.sql`
creates bot, approval, idempotency and append-only audit tables. State transitions are
performed inside D1 batches with optimistic version checks.

