# Canonical MongoDB / Atlas Migration

The Cognitive Mind must be moved, not reinitialized, when persistent storage changes.

## Safety rule

The migration utility copies the existing physical MongoDB documents for:

- `mind`
- `journal`
- `memory`
- `diagnostics`

It refuses to run unless the source contains exactly one Mind and the target cognitive
collections are empty. This prevents accidental merging of two identity histories.

MongoDB `_id` values are preserved as storage-level implementation details. They remain
outside the cognitive domain model.

## Move the existing Mind to Atlas

Resume or create the Atlas deployment and obtain its private MongoDB connection string.

From a machine that can reach both the current source MongoDB and Atlas:

```bash
export SOURCE_MONGODB_URI="mongodb://mongodb:27017"
export SOURCE_MONGODB_DATABASE="ai_cognitive_mind"

export TARGET_MONGODB_URI="mongodb+srv://<user>:<password>@<cluster>/"
export TARGET_MONGODB_DATABASE="ai_cognitive_mind"

python scripts/migrate_mongo.py
```

The script pings both databases, verifies the one-Mind invariant, verifies that the Atlas target
is empty, copies all cognitive collections, and checks the copied counts.

## Use Atlas as the canonical Mind

After the migration succeeds, the normal host configuration becomes:

```bash
export MONGODB_URI="$TARGET_MONGODB_URI"
export MONGODB_DATABASE="ai_cognitive_mind"
export OPENAI_API_KEY="..."
cognitive-mind
```

Do not call `initialize_mind` against the Atlas database after migration. The existing identity
has already moved with its memory and journal.
