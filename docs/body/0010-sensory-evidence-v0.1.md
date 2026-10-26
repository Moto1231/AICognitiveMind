# Body — Sensory Evidence Artifacts V0.1

**Status:** Durable evidence layer for deliberate See/Hear observations.

## Corrected boundary

The earlier Body rule treated all raw sensory media as transient. That was too broad.

The corrected rule is:

> Continuous sensory streams are transient. The exact observation deliberately admitted into cognition becomes durable evidence.

This distinguishes three layers:

```text
raw sensory stream
      ↓
deliberate observation
      ↓
Sensory Evidence Artifact
      ↓
Mind-side interpretation
      ↓
Memory Steward / belief / response
```

Evidence is not interpretation, and interpretation is not memory.

## What becomes an evidence artifact

Today:

- **See** admits the JPEG frame actually sent for visual interpretation.
- **Hear** admits the recorded audio clip actually sent for transcription.

The artifact is preserved **before** interpretation begins.

If interpretation fails, the evidence still exists and its admission remains journaled.

When Eyes later admits a short video clip rather than a still frame, that exact video clip should
be preserved through the same contract. V0.1 does not fabricate video evidence for a visual
operation that currently interpreted only one image frame.

## Artifact contents

Each `SensoryEvidenceArtifact` contains:

- capture timestamp;
- sensory modality;
- Body source;
- media type;
- SHA-256 content hash;
- exact byte length;
- exact media payload encoded as base64;
- physical capture metadata such as dimensions or duration.

There is no artificial cognitive primary key.

The durable reference is content-addressed by SHA-256 together with capture time, which preserves
the distinction between identical media observed at different moments.

## Immutability

Evidence storage exposes only:

- `preserve()`;
- exact retrieval by SHA-256 and capture time.

There is no update operation.

If the same exact hash/capture-time pair is preserved again, the existing artifact is returned.

## Journal provenance

Before interpretation, `MindBodyBridge` writes a `sensory_evidence` journal entry with:

- admission status;
- Body source;
- evidence reference;
- safe capture metadata.

After interpretation, the normal interaction journal entry includes the same evidence reference
inside the input context.

Raw media bytes are not copied into journal documents.

## Evidence retrieval

The authenticated application exposes:

```text
GET /v1/evidence/{sha256}?captured_at=<timestamp>
GET /v1/evidence/{sha256}/metadata?captured_at=<timestamp>
```

The first returns the original media bytes with their media type.

The second returns the immutable evidence reference.

The whole Render application remains protected by the existing application access authentication.

## Live Body

### Automatic interpretation routing

Dedicated Vision and Audio/Transcription model endpoints are optional. When a specialist task is
configured, automatic observations use that task's ordered provider/model routing. A specialist
failure remains an interpretation error; it does not silently switch to a different route.

When no specialist is configured, automatic observations use a verified `sensory.ready`
subscription when available, or the attached reasoning host's queue.
The preserved artifact's trusted hash and capture time accompany the request, including when the
inline media is too large for the text handoff. The host retrieves the original evidence and may
delegate independent interpretation to parallel workers. These workers share the existing reasoning
owner and claim each request independently; they do not attach another reasoning owner.

Automatic requests use the `sensory_interpretation` task context and remain lower priority than
human text. Their completion returns an observation to the Body bridge, which writes the sensory
interpretation and updates presence. It does not start a separate conscious conversation or speech
for every frame or audio clip. The observation endpoint returns its normal result after the host
completes interpretation; a queued request is never represented as an interpretation.

An attached host still needs an active queue consumer. A connected client can instead register a
verified callback for `sensory.ready`, so a newly admitted observation wakes its processing task
without waiting for another human chat message. A host registration alone does not install that
subscription or a persistent worker. If neither route is available, admission fails promptly after
preserving the artifact and its admitted journal record. A bounded host camera request delivers
its native frame before awaiting automatic interpretation, so the requesting host can consume
the sensory work instead of waiting on itself.

Passive host interpretation has an overall deadline (120 seconds by default). If no observation
arrives before it expires, the endpoint returns an interpretation error and removes the request
from pending work; the original evidence remains preserved. Cancelling the waiting task also
cancels its passive request. Human reasoning requests retain their existing persistent lifetime.
Legacy passive requests without a deadline are reconciled against their original creation time;
reconnecting does not grant old observations a fresh processing lifetime.
The browser separately bounds sensory requests, releases their busy state on failure, and cancels
in-flight capture work when that sensor is turned off. A late result from an earlier sensor
generation cannot overwrite the current display.

### Sensory-ready callbacks

`sensory.ready` is separate from `message.created`. It identifies a passive camera or microphone
request with its account, Body session, modality, source, and immutable evidence reference. It does
not copy original media into the event or represent the observation as a human message.

The receiving task reads and claims that exact request with `read_incoming_sensory` and
`claim_incoming_sensory`, retrieves its original evidence, and submits a grounded observation with
`complete_incoming_sensory`. The private event claim token replaces the live-host lease for this
request. Duplicate claims and completion retries retain the existing claim/result; the receiver
can use `release_incoming_sensory` when an attempt fails. Expired or cancelled observations do not
receive a fresh lifetime when an event arrives late.

Subscription discovery and storage, request claims, evidence retrieval, and completion all use the
authenticated account's Mind. The existing verified HTTPS callback and signed durable outbox
protocol applies. Completing a passive request does not emit another ready event, begin a conscious
interaction, or request speech; the awaiting Body bridge still owns interpreted journaling and
presence updates.

An end-to-end acceptance check needs a real registered receiver and a new Body input that starts
reasoning while the chat is idle. Server regression tests can exercise authenticated media ingress,
signed webhook delivery, claim/evidence/completion, and the resulting HTTP response with synthetic
media and a synthetic callback receiver. Those checks do not establish that a particular ChatGPT
or Codex client has registered its own receiver or resumed the target chat.

### Local host readiness channel

A registered local receiver can keep a bounded wait open on `POST /v1/host-events/ready` when it
cannot accept incoming webhooks. The request supplies the exact Mind selector, its private host
lease token, and optional `after_request_ids`. The capability is checked against that selected
Mind; the selector alone grants no access. Other portal and Body endpoints keep their normal
authentication.

The response contains only ready request IDs, kind, creation time, and deadline, with human work
ordered first. It renews the host registration without claiming requests or returning human text,
media, evidence, or credentials. The receiving bridge must wake the intended chat and use the
ordinary host tools to claim and complete its work. Keep the private lease outside model prompts
and diagnostic output. A successful readiness response alone does not prove the chat resumed or
the Body received an interpretation.

After a completed See/Hear cycle, `/body/live` displays:

- media type;
- SHA-256;
- capture time;
- a direct authenticated link to the preserved visual or audio evidence.

This makes the distinction visible:

```text
Evidence:
  what physically entered cognition

Interpretation:
  what the Mind currently thinks it means

Response / memory:
  what cognition did with that interpretation
```

## Storage

The current Atlas implementation stores the bounded V0.1 media artifact in the `evidence`
collection.

Current sensory limits keep artifacts below MongoDB's single-document size ceiling:

- Eyes: bounded JPEG observation;
- Ears: maximum 30-second / 8 MB audio observation.

Longer video evidence should move to a large-object mechanism such as GridFS or object storage while
keeping the same evidence-reference contract.

## Re-evaluation

V0.1 preserves and retrieves the original evidence needed for future reconsideration.

A later slice should give the reasoning process an explicit evidence-review tool so, when a memory
or interpretation is challenged, the Mind can deliberately retrieve and reinterpret the original
artifact rather than trusting only the prior transcription or description.

## Memory authority

Preserving evidence does **not** allow the Body to write cognitive memory.

The Memory Steward remains responsible for deciding whether an interpretation, fact, relationship,
or belief should influence the Mind beyond the immediate interaction.


## Implemented review slice

[0011 — Sensory Evidence Review V0.1](0011-sensory-evidence-review-v0.1.md) gives the conscious
reasoning process a focused, integrity-checked path back to the original evidence while preserving
every interpretation as separate history.
