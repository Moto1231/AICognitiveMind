# Axiom Backup Strategy

Copyright (c) 2026 William Enright. All rights reserved.

Axiom must be recoverable independently of any one laptop, GitHub repository,
Render deployment, or SurrealDB instance.

## What is backed up

Each checkpoint contains three independent recovery assets:

1. **repository.bundle** — complete Git history, branches, and refs;
2. **working-project.zip** — the current working project, including tracked and
   untracked project assets such as local Genesis Bodies, while excluding
   generated Unity caches and local secret files;
3. **axiom-mind.zip** — a portable snapshot produced by the running Mind,
   containing:
   - governed Mind identity;
   - append-only journal;
   - durable memory;
   - diagnostics;
   - sensory evidence metadata;
   - exact preserved image/audio evidence bytes.

The Mind archive intentionally contains no database credentials, API keys, app
passwords, or Admin PIN.

## Multiple locations

Run:

```powershell
.\scripts\backup-axiom.ps1
```

By default the script writes to:

- `%USERPROFILE%\Documents\AxiomBackups`;
- `%OneDrive%\AxiomBackups`, when OneDrive is configured.

If only one destination is available, the script warns. A second independent
destination can be supplied explicitly, for example an external drive:

```powershell
.\scripts\backup-axiom.ps1 -Destination @(
    "$env:USERPROFILE\Documents\AxiomBackups",
    "E:\AxiomBackups"
)
```

The script verifies the Git bundle, validates the Mind ZIP, calculates SHA-256
hashes, copies each checkpoint to every destination, and verifies copied file
hashes.

## Credentials

The backup script never writes runtime credentials into the checkpoint.

It can read these environment variables for unattended use:

- `AXIOM_MIND_URL`
- `AXIOM_MIND_USERNAME`
- `AXIOM_MIND_PASSWORD`
- `AXIOM_ADMIN_PIN`

When required values are absent, the script prompts instead of storing them.

## Sensitive data

The Mind backup contains personal cognitive history and potentially raw
camera/microphone evidence. Treat it as sensitive private data. Do not commit
Mind backup ZIP files to the public Git repository.

A later backup increment should add portable encryption before copying Mind
archives to storage that is not under the operator's physical control.

## Recovery rule

A backup is not considered complete merely because files were copied. The
checkpoint is complete only after the bundle/archive validation and destination
hash verification succeed.
