# SurrealDB Storage Spike

Branch: `codex/surreal-storage-engine`

This branch evaluates SurrealDB as a parallel persistence substrate for the Cognitive Mind while the MongoDB route continues independently.

## Boundary

The cognitive architecture is unchanged. `CognitiveCore` still depends on the existing storage protocols (`MindStore`, `FoundationStore`, `JournalStore`, `MemoryStore`, and `DiagnosticStore`). SurrealDB is implemented as a second adapter behind those interfaces.

## Current goal

Establish behavioral storage parity first:

- one persistent Cognitive Mind root document
- governed foundation history
- append-only journal behavior
- Memory Steward durable memory writes
- implementation diagnostics
- the same API surface above storage

The initial tests use SurrealDB's embedded `mem://` engine so CI exercises the real database without requiring a second database service.

## Runtime selection

This branch defaults to:

```text
STORAGE_PROVIDER=surreal
SURREALDB_URI=surrealkv://.surreal/cognitive_mind
SURREALDB_NAMESPACE=mir_ai
SURREALDB_DATABASE=ai_cognitive_mind
```

Set `STORAGE_PROVIDER=mongo` to use the existing MongoDB adapter on this branch.

Remote SurrealDB instances can be used by setting `SURREALDB_URI`, `SURREALDB_USERNAME`, and `SURREALDB_PASSWORD`.

## Deliberately deferred

This first spike does not yet exploit SurrealDB-native graph relationships, vector indexes, live queries, or time-series modeling. Those are the capabilities we want to evaluate after basic storage parity is proven. Introducing them before parity would make it impossible to tell whether differences come from the database or from a changed cognitive model.

No decision to replace MongoDB is implied by this branch. The two routes are intentionally allowed to evolve in parallel until evidence supports a storage decision.
