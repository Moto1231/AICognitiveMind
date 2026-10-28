# Appendix: operator reference and documentation maintenance

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

## Deployment reference, not an instruction to redeploy

The reviewed `render.yaml` describes a Python web service on branch `main`, build command `pip install .`, and startup:

```text
uvicorn aicognitive_mind.deployment:app --host 0.0.0.0 --port $PORT
```

Its health-check path is `/health`, and its declared storage provider is SurrealDB. Secret values are supplied separately for settings marked `sync: false`. A committed Blueprint is not proof of the live service's applied settings or deployed revision.

The deployment derives its public URL from `AXIOM_PUBLIC_URL`, Render URL/hostname information, or a local fallback. The integrated OAuth MCP resource is `/axiom-mcp`. A standalone MCP smoke-test server's `/mcp` path is a separate context.

Documentation maintenance does not require a manual Render deploy.

## Root initialization is an operator decision

The CLI/root initialization route and portal account signup create different targets. Read [FRESH_START_SETUP.md](../FRESH_START_SETUP.md) before initializing anything. Opening storage can bootstrap tables; a “read-only investigation” that starts a runtime may therefore write infrastructure records.

Do not use root initialization as a troubleshooting step for an existing account's missing history. Verify backend, namespace/database and account scope privately. Never copy live credentials into a manual example.

## Windows checkpoint example

From the intended repository checkout, with authorized runtime access and Git/`tar.exe` available:

```powershell
.\scripts\backup-axiom.ps1 -Destination @(
    "$env:USERPROFILE\Documents\AxiomBackups",
    "E:\AxiomBackups"
)
```

The second path is an example destination, not an assumption that an E: drive exists. The script can use `AXIOM_MIND_URL`, `AXIOM_MIND_USERNAME`, `AXIOM_MIND_PASSWORD` and `AXIOM_ADMIN_PIN`; required missing values prompt rather than being embedded in this example.

Check the reported validation and destination hash verification. Preserve private recovery credentials separately. See [recovery](recovery.md) for the account-scope restriction and archive distinctions.

## Maintain this manual

This manual's source review baseline is recorded in [review-record.md](review-record.md). On each authorized maintenance run:

1. Read live GitHub main and its commit SHA.
2. Compare main with the recorded review revision, including UI, handlers, skills, configuration, tests and operational docs.
3. Identify which chapters the changed files affect.
4. Read those changes and their surrounding implementation; update affected workflows and examples.
5. Continue any open writing/verification work in the gap register.
6. Update each affected chapter's review revision/date and the review matrix. Leave unchanged chapter pins honest.
7. Validate local links, headings, source paths, examples and absence of secrets.
8. Use a dedicated `docs/...` branch and draft PR.
9. Let the normal GitHub checks run; fix documentation defects on that branch.
10. Mark ready/merge only through the established review/check workflow after green validation.

If main advances during review, compare again before finalizing. An unchanged page can be marked reviewed at a newer revision only after its relevant source changes were checked.

Do not create another maintenance schedule when one is already attached to the authoring chat. No schedule is installed by this document. Report meaningful updates, milestones and blockers; no-change runs need no announcement.

## Validation reference

> This workflow description was reviewed against `56dd9a5faefcc6adde578ed49a6aaad30e968153` on 2026-10-27.

The reviewed **Project validation** workflow runs on pull requests targeting main. The authoritative `test` job sets `STORAGE_PROVIDER=surreal` and covers Python tests, all Node portal checks, MCP import/deployment assembly, the canonical Surreal utility, two-process handoff, and stdio/HTTP continuity smoke tests on SurrealDB. A separate `mongo-retrieval` job is legacy compatibility coverage for existing Mongo history; do not present that job as proof of the current Surreal deployment.

Useful existing commands include:

```bash
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
```

These commands require the project's dependencies. The manual's initial authoring uses GitHub checks rather than repurposing another product checkout. Tests passing on synthetic data do not authorize a claim of a successful production account login, external-provider task, cloud restore or physical-device workflow.

## Historical documents

Older architecture, Body and setup notes can explain design history without describing every current screen. Keep their revision/evidence scope visible. In particular:

- The root README's original “four tools” description is not a complete current MCP catalog.
- The older installation note's single-skill description omits companion startup protocols.
- “Task Profiles” is still a menu label, but Task Configuration is the current page heading.
- Mongo-specific recovery instructions are not Surreal restore instructions.
- Older Body statements that all raw observations remain transient were refined by preserved sensory-evidence support.

When a historical note conflicts with implementation, update the user-facing workflow from the source and record the conflict. Do not silently change application behavior to fit documentation.

## Source references

- [render.yaml](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/render.yaml)
- [.github/workflows/mcp-validation.yml](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/.github/workflows/mcp-validation.yml)
- [docs/DEVELOPMENT_WORKFLOW.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/DEVELOPMENT_WORKFLOW.md)
- [docs/FRESH_START_SETUP.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/FRESH_START_SETUP.md)
- [docs/BACKUPS.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/BACKUPS.md)
- [scripts/backup-axiom.ps1](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/scripts/backup-axiom.ps1)
- [src/aicognitive_mind/deployment.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/deployment.py)
