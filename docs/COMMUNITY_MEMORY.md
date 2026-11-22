# Community Memory: initial synthetic verification

The initial candidate catalog contains two fixed synthetic lessons for exercising
the workflow. It does not yet discover or learn new real-world lessons. It has
no input for raw journal entries, personal sleep reports, credentials, customer
data, user identifiers, or free-form draft text. The curator may only select or
decline the provided candidate. New lessons require a separately reviewed,
isolated source that validates origin, product/release, applicability, evidence
and observed result before any prepared text can be considered for publication.

An account/Mind's single opt-in governs both publishing and the ability to read
Community Memory. Each operation also requires separate group membership.
Unknown accounts/groups and unset preferences are denied by default. Revocation
stops recall and invalidates contributions and pending approvals from that grant;
rejoining does not restore old content. Published results do not include names or
other private identifiers, and are not written back into the private memory store.

The trusted caller must finish personal sleep successfully before handing fixed
candidates to the optional curator. A declined, malformed or failed decision
does not publish. Authorization is checked again atomically at publication and
when reading. The synthetic store is in process, not a shareable persistence
service; it is not an authentication layer, a scheduler, or a consent UI.

## Staged application integration

The authenticated ChatGPT MCP flow supports one reciprocal preference per
account/Mind via `get_community_memory_setting` and
`set_community_memory_setting`. The server derives the principal from the
existing verified account scope; the tools do not accept a Mind selector.
The setting defaults off. The deployment itself is also off by default.

To stage the existing synthetic catalog, configure a dedicated absolute
`COMMUNITY_MEMORY_DB_PATH` on retained storage, a
`COMMUNITY_MEMORY_GROUP`, and a comma-separated
`COMMUNITY_MEMORY_ALLOWED_MINDS` list. Do not reuse a private datastore
file. Configure the Mind's **Structured Extraction** task provider to make
the publish-or-skip decision. No provider means no AI publication. The
provider receives only the built-in synthetic candidate, never the personal
sleep report or journal. The staging path uses a separate SQLite file and one
server-managed group; it is not a production multi-tenant provisioning layer.

An authenticated `run_sleep_cycle` completes the normal private phase before
curation. No nightly scheduler or real-world lesson source is installed by this
change. At `begin_interaction`, currently eligible, opted-in members may see
relevant references under `community_memory`. The server does not append the
references to the diagnostic trace, host working context, or personal
memory. A host or recipient can independently retain a previously delivered
answer; authorization can block future recalls but cannot retract prior
disclosures.

The separate file and account checks do not provide cryptographic protection
against the host or database operator. Do not feed real private records to
this implementation. A private-data source requires a separate design whose
keys and authorization are not controlled by those operators.
