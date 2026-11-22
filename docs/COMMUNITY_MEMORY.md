# Community Memory staged local handoff

Community Memory is disabled by default. The initial catalog contains only two
fixed synthetic lessons to test the path. It cannot discover or publish real
private lessons. A separate source and release policy would be needed before
using real data.

## Reciprocal participation

The authenticated ChatGPT MCP tools `get_community_memory_setting` and
`set_community_memory_setting` operate on the signed-in account and its
verified Mind. Their one opt-in governs contribution and recall, and the
server-managed group must also allow the Mind. Opting out removes published
contributions and unsettled receipts. Rejoining does not restore them.

For staging, configure a dedicated absolute `COMMUNITY_MEMORY_DB_PATH` on
retained storage, one `COMMUNITY_MEMORY_GROUP`, and a comma-separated
`COMMUNITY_MEMORY_ALLOWED_MINDS` list. Do not reuse a private datastore
file. This app-layer community store is plain SQLite, not a private key store.

## Local host testing

1. Sign in to the staging MCP service. Use synthetic data only. Opt in using
   the authenticated setting.
2. Call `run_sleep_cycle`. Existing personal consolidation runs first. Only
   after it succeeds will an opted-in Mind receive a short-lived
   `community_memory.handoff_receipt`. The server does not run an AI curator.
3. Run a Steward locally within the owner's key boundary. Keep the key,
   source material, free-form reasoning, and drafts on that side. If the
   local Steward selects a catalog lesson, use the owner-side
   `private_community_steward.curate_and_submit_locally` helper and call
   `submit_community_memory_candidate` with the receipt and the fixed
   `lesson` identifier (`check_bindings` or `validate_import`). Use a
   trusted local MCP client, not a hosted model, to relay the receipt.
4. Confirm that a relevant question in an opted-in member's subsequent
   `begin_interaction` can return the lesson under `community_memory`.
   The transport trace, host working context, and private durable memory
   omit direct copies of the shared reference.

Receipts expire after five minutes, are single-use, and cannot be transferred
to another Mind. Issuing one invalidates the prior receipt for that account
and group. The staging DB retains only the receipt hash and grant metadata.
Receipt redemption, opt-in verification, and publication occur in one store
transaction. The receipt confirms completed personal sleep, not that a local
model selected the ID; the catalog is the server-side content boundary.

No automatic local-host bridge, nightly scheduler, real memory source, or
production key provisioning is included. This handoff does not encrypt or
otherwise change the existing server journal. The operator-resistant
boundary applies only to inputs encrypted and processed on the owner side;
the community lesson itself remains readable at the app layer. Revoking
access blocks future recalls but does not retract prior disclosures.
