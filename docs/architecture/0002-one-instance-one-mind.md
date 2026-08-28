# ADR 0002: One instance, one document-native mind

**Status:** Accepted  
**Date:** August 11, 2026

## Context

The initial scaffold modeled multiple `Being` records, host and event identifiers, and correlated event rows. Although technically usable, that structure imported relational application concepts into a system intended to model one cognitive mind.

It also allowed reasoning-engine provenance to appear beside cognitive history, which blurred the boundary between the persona and the temporary mechanism used to produce a proposal.

## Decision

1. One deployed application instance contains exactly one cognitive mind.
2. The application exposes singular `/mind` behavior, not a collection of Beings.
3. Cognitive documents contain no domain primary keys, foreign keys, mind IDs, host IDs, journal-entry IDs, correlation IDs, or causation IDs.
4. MongoDB's automatic `_id` remains private physical storage metadata. It is projected out when documents enter the Cognitive Core.
5. The root `mind` document contains identity and current developmental state as one aggregate.
6. The `journal` stores whole experiences as append-only documents rather than normalized event fragments.
7. Reasoning-engine names, models, and proposal provenance live only in `diagnostics`; they are absent from the root mind and cognitive journal.
8. Steward-curated durable learning lives as whole documents in `memory`, without cognitive identifiers or references to normalized records.

## Consequences

- A second initialization is rejected because it would represent a second individual.
- Interactions require no individual identifier in the API.
- Cognitive history reads as experiences rather than database transactions.
- Diagnostic records can be removed, restricted, or replaced without changing the persona.
- If a future project needs a population, each individual mind should remain its own instance; population infrastructure belongs outside the mind.
