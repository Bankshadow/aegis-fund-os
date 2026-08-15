# Webull OpenAPI adoption boundary

## Source retained for future development

This project uses the public MIT-licensed [Webull OpenAPI AI Plugin](https://github.com/nutdnuy/webull-openapi-AI-Plugin) as a schema and workflow reference.  The adopted revision is recorded in [`webull-openapi-source.lock.json`](../integrations/webull-openapi-source.lock.json).

The Codex skills installed from the source are deliberately limited to:

- `webull-auth` — secure credential and token lifecycle guidance;
- `webull-market-data` — market-data schemas;
- `webull-account` — account, balance, position, and order-read schemas; and
- `webull-events` — MQTT and gRPC event documentation.

`webull-orders` and `webull-watchlists` are intentionally not installed.  They include write workflows that are outside this project's current connection scope.

## Compatibility decision

Do **not** wire the plugin's Python runtime directly into the existing
`fund-command-center-local` adapter.  They target different Webull environments
and signing contracts:

| Component | Allowed host | Signature | Current purpose |
| --- | --- | --- | --- |
| Existing app adapter | `api.sandbox.webull.com` only | HMAC-SHA1 | Webull Sandbox integration and constrained test path |
| Retained plugin reference | `th-api.uat.webullbroker.com` for development | HMAC-SHA256 | Thailand OpenAPI schemas, UAT read paths, and event design |

The source plugin defaults to a production host when `WEBULL_ENV` is unset.  It
must therefore never be invoked by an automated service in this repository.
Any Thailand adapter must require `WEBULL_ENV=uat`, pin the UAT host, and use a
separate server-only credential namespace such as `WEBULL_TH_UAT_*`.

## Approved next implementation slice

Build a separate **read-only Thailand UAT adapter** with an explicit endpoint
allowlist: account list, balances, positions, open orders, order detail/history,
and market snapshots/bars/quotes.  It must:

1. reject every non-UAT host before signing or networking;
2. reject every endpoint not marked `read` in the retained catalog;
3. redact tokens, signatures, account identifiers, and raw payloads in UI/logs;
4. preserve raw source references only in the server-side reconciliation store;
5. have no order, cancellation, watchlist-write, or token-create transport; and
6. pass focused tests, TypeScript/build checks, and `gate/verify.ps1`.

Streaming is documentation-only until the read-only polling and reconciliation
slice has passed its declared gate.  The current project constitution still
forbids live orders and third-party capital.

## Verification criteria for that slice

Pass only if all of the following are true:

- UAT configuration with no credentials makes no network request and returns a
  sanitized `needs_credentials` result.
- A production host, unknown host, write method, or catalog entry with a risk
  other than `read` fails before any network request.
- Fixture tests cover account, balances, positions, open orders, one market
  snapshot, secret redaction, and the no-network rejection cases.
- The new connector does not share credentials, host selection, or order code
  with the Sandbox adapter.

