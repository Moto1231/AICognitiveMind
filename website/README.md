# Axiom website and subscriber preview

Private Sites project: `appgprj_6ade9371c8688191994b9b27a3520bc1`.
Expected origin: https://axiom-continuity-portal.snowydeer18.chatgpt.site (deployment success must be checked separately).

## Scope

This is a new website, not a replacement Mind or a change to the existing Render runtime. Routes: `/`, `/guide`, `/portal`, `/account`, `/preview/checkout`. Native Sites sign-in identifies this site's visitor only. Existing Axiom signup/login links navigate directly to the established service. No credentials are collected here. No runtime secrets are configured. No model provider is called.

The subscriber portal is explicitly illustrative: sample access states and simulated checkout. Sample state selection is not a production entitlement. `/api/interaction` and `/api/billing/{checkout,manage,webhook}` always return 503. The browser cannot unlock a real Mind using a flag, a forged account id or a success redirect.

## Source review

Reviewed main `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25:
- `accounts.py`: new account Mind allocation, password authentication, canonical subject validation.
- `api.py`: portal sessions, tenant runtime selection, explicit scoped Body/backup denial.
- `deployment.py`: `/portal`, `/signup`, login/logout, production middleware.
- `account_mcp.py`, `tenancy.py`, `mcp_server.py`: account context and MCP interfaces.
- `static/portal.js`, README and `docs/DEVELOPMENT_WORKFLOW.md`: actual UI actions and branch/PR/check conventions.
- Root `AGENTS.md` returned 404; root listing confirmed none. `.agents` contains plugins only. This new website directory did not exist.

Manual PR324 remains open/unmerged at `dc58c906b81c7e38b8f90c784ddf3068c303e319`. Links explicitly use the draft branch. No manual files were changed and no maintenance schedule was created.

## Development

Uses the native Sites Vinext server-capable starter, preserving `sites()` integration. Install with the Sites dependency helper; build with the Sites build helper. The complete native source is versioned in the Site source repository. Portable application source is mirrored in AICognitiveMind on a separate branch/PR.

```
node --test tests/access.test.mjs
node node_modules/typescript/bin/tsc --noEmit
```

`tests/http-check.mjs` can run against an accessible local preview origin. Its initial-release transport attempt in the managed environment failed before completion; do not count it as passing. Initial-release browser QA covered the homepage, model swap, the former conversation example and expired denial. That historical exercise does not establish browser coverage for the revised account/access-only portal. Responsive CSS is included; no physical mobile device verification is claimed.

## Billing core and limits

`lib/billing.mjs` implements raw-body Stripe-style HMAC verification with timestamp tolerance, explicit test/live-mode checks, account/customer/subscription binding checks and a transactional event receipt/update contract. It refetches current provider state instead of trusting out-of-order event snapshots. `authorizeMind` refuses unlinked identities, a root/legacy Mind, cross-account data, unpaid/expired records and absent mapping.

Tests use synthetic signed events and a serialized in-memory transactional adapter. This proves policy and interface behavior only. There is NO durable billing database adapter, actual Stripe API adapter, authenticated account-linking bridge or end-to-end provider verification in this edition. No webhook route is enabled. A private Sites URL cannot directly receive Stripe's unauthenticated service webhook; use an explicitly provisioned service endpoint without weakening owner-private access.

Authoritative protocol references consulted:
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/billing/subscriptions/overview

## Exact launch work remaining

1. Will chooses commercial capability scope, approved plan/pricing, business identity, customer support contact, retention/privacy/refund/subscription terms. No price or customer claim was invented.
2. Connect Stripe (discovered available, not installed), configure a test-mode account/product/price, and provision secrets through a supported secure environment-variable path. Never put credentials in source or chat. Stripe is proposed, not an approved vendor commitment.
3. Implement verified Axiom account ownership linking to Site identity; never use email equality. Store a unique server-owned Site-subject → Axiom-subject → Stripe customer/subscription mapping. No root credential delegation.
4. Add durable serializable receipt/entitlement storage and real provider adapters. Integrate server-created Checkout and customer billing portal; no client-owned customer/price identifiers. Extend event coverage to paid invoices and reconcile period/payment evidence. Use the provider's current API schema.
5. Enforce subscription access at the existing service boundary as well as the website (prevent direct API/MCP bypass), preserving tenant routing, model configuration and Administrator authority. Make this a separately reviewed product change; the first website preview does not alter the live service.
6. Provision a supported signature-checked webhook receiver reachable by Stripe without opening the private preview. Test real provider retries, duplicate/concurrent delivery, failed writes, stale event ordering, renewals, canceled/expired/pending/unavailable access and two-account isolation end to end. Verify account sign-in/sign-out and accessibility/mobile journeys.
7. Only after these checks and Will's public-launch approval, configure live billing and audience/domain. No live charging, domain purchase or Render deployment is authorized by this preview.
