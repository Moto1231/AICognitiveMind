# Scheduled journal review

The Memory Steward owns two protected Functions under Administration →
Instructions → Faculties → Memory Steward → Functions. Neither changes when
Reasoning responds or runs the existing interaction Save.

- **Current State Review** checks each original human observation against the
  interaction's ledger snapshot and the latest ledger. It flags missed or
  mishandled changes with a verified verbatim quote; it never patches Current
  State or sends a message. Reasoning sees unresolved findings on a later begin
  and uses fresh evidence to reconcile. Findings older than the current field's
  recorded evidence do not enter the active interaction.
- **Memory Review** independently reconsiders durable omissions even where the
  original review succeeded. It reuses the configured Steward provider and
  governed memory writes, with the journal entry and confirmed original speaker
  (when captured on that turn) as provenance. This is not a claim that the
  speaker is the subject of every memory. Receipt keys
  make repeating a recovered write safe and existing memory is checked again
  at the write boundary. It does not replay the original interaction or invoke
  any external actions.

An opted-in application process runs one scheduler. Both Functions share a
bounded journal read when their cursors match, and each cursor advances only
after that Function succeeds for the entry. A failed Function resumes on the
next pass without repeating successful work in the other Function. Only
committed human interactions are candidates; a short cutoff keeps newly staged
turns away from the cursor boundary. On first run, each Function starts one day
back; this is not a full archive backfill. The scheduler does not run Sleep or
scan community memory. Pause a Function by saving a blank override; its progress
is not advanced while paused.

Set `JOURNAL_REVIEW_INTERVAL_SECONDS` on a single always-on process (0, the
default, disables it; nonzero intervals have a 60-second floor). Set
`JOURNAL_REVIEW_MIND_ID` to the verified account Mind ID, or omit it to use
the deployment's configured root Mind. The job does not enumerate accounts.
Render's sleeping free service cannot guarantee cadence. Use one scheduler
process to avoid unnecessary duplicate model calls. On an enabled Mind,
conversation reads completed findings at most 200 ms; it never awaits the job.
