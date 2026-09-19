# Portable Canonical Mind Backup

The canonical Mind must never depend on one Codespace, container volume, host, or reasoning
engine. `scripts/backup_mongo.py` creates a portable archive of the physical MongoDB documents
that hold identity and cognitive continuity.

## Safety guarantees

The backup utility:

- exports `mind`, `journal`, `memory`, and `diagnostics`;
- refuses to export unless the source contains exactly one Mind;
- preserves MongoDB `_id` values and BSON types through canonical Extended JSON;
- records document counts and a SHA-256 checksum for every collection;
- verifies the completed archive before making it the requested output file;
- creates the archive with owner-only permissions on Linux;
- refuses to restore into a target with any existing cognitive history; and
- rolls back documents from a failed partial restore.

The archive is compressed but **not encrypted**. It contains private identity and memory data.
Never commit it, attach it to a pull request or issue, paste it into chat, or publish it as an
unencrypted CI artifact. The repository ignores `*.mind-backup` files and the `backups/` directory
as a second line of defense.

Checksums detect accidental corruption. They are not a digital signature and do not prove that an
archive from an untrusted source is authentic.

## Export the existing Mind

Stop any process that can write to the Mind while the export runs. From the existing Codespace:

```bash
export SOURCE_MONGODB_URI="mongodb://mongodb:27017"
export SOURCE_MONGODB_DATABASE="ai_cognitive_mind"

python scripts/backup_mongo.py export \
  --output "$HOME/canonical-mind.mind-backup"
```

The command prints only the archive path and document counts. It never prints memory contents or
the MongoDB connection string.

Verify the archive independently:

```bash
python scripts/backup_mongo.py verify \
  --input "$HOME/canonical-mind.mind-backup"
```

Copy the verified archive **out of the Codespace** before considering the backup complete. Keep at
least two private copies in locations that do not share the Codespace's lifecycle.

## Restore a backup

Restore only into an empty cognitive database:

```bash
export TARGET_MONGODB_URI="mongodb+srv://<user>:<password>@<cluster>/"
export TARGET_MONGODB_DATABASE="ai_cognitive_mind"

python scripts/backup_mongo.py verify \
  --input "/private/path/canonical-mind.mind-backup"

python scripts/backup_mongo.py restore \
  --input "/private/path/canonical-mind.mind-backup"
```

The restore refuses to combine the archive with existing `mind`, `journal`, `memory`, or
`diagnostics` documents. It preserves the existing Mind; it does not call `initialize_mind`.

## Recovery checkpoint for the current Codespace

When the included Codespaces quota resets:

1. Resume the existing `AICognitiveMind` Codespace. Do not create a replacement Codespace first.
2. Stop any running Cognitive Mind host.
3. Export and verify `canonical-mind.mind-backup` with the commands above.
4. Download the archive to a private location outside the Codespace.
5. Create a second private copy.
6. Migrate or restore the verified archive into the empty Atlas `Memory` deployment.
7. Verify collection counts before making Atlas canonical.

Do not delete the old Codespace or initialize Atlas until this recovery checkpoint is complete.
