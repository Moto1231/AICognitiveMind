# AI Cognitive Mind — Build Journey, Operating Model, and Path to Use

**Living document**  
**Current checkpoint:** September 19, 2026  
**Current main baseline when this document was started:** `730f483`

This document records **how the AI Cognitive Mind was conceived, what was built, why the architecture changed, what has been proven, what is still experimental, and what has to happen before the Mind is used as an everyday reasoning substrate**.

It is intentionally different from the ADRs in `docs/architecture/`. The ADRs record individual technical decisions. This document records the **whole development journey and the evolving cognitive model**.

---

## 1. The original problem

The project began with a simple but consequential question:

> What if identity, memory, continuity, and cognitive governance do not belong to the reasoning model?

Modern AI systems commonly place reasoning, conversational context, memory, persona, and policy inside one model/session/product boundary.

Digital Genesis takes the opposite position:

> **A reasoning engine produces thought. It must not own identity.**

The Cognitive Mind is therefore a persistent system that owns:

- identity;
- durable memory;
- cognitive history;
- Memory Steward policy;
- values/governance boundaries;
- continuity across reasoning-engine changes.

The connected reasoning engine is replaceable.

This is the central architectural claim of the project.

---

## 2. Foundational principles

The implementation has been repeatedly constrained by several principles.

### One Mind

The system represents one persistent Mind, not a population of agents.

Different cognitive roles may eventually run as separate processes or reasoning contexts, but they belong to the **same Mind**.

### Model independence

No ChatGPT-, Claude-, Gemini-, Ollama-, or other vendor-specific reasoning adapter is allowed to own the Mind.

The external integration boundary is MCP.

### Understanding before Recommending

The system should retrieve relevant context, evidence, history, and unresolved tensions before settling on a recommendation or conclusion.

### Preserve continuity of identity

A reasoning-engine replacement must not imply the creation of a new identity.

### Preserve evidence instead of rewriting history

New knowledge may supersede an old belief, but the evidence that produced the old belief remains part of the Mind's history.

### KISS before ontology

The project deliberately avoided a permanent relational proposition schema and application-level cognitive IDs.

Cognitive distinctions are added through evolvable Memory Artifacts instead of forcing every future idea into a fixed database ontology.

---

## 3. Phase 1 — One persistent Mind

The earliest implementation established:

- one root Mind;
- identity and foundational values;
- append-only journal;
- durable memory;
- diagnostic information separated from cognition;
- MongoDB as the initial persistence substrate.

The project explicitly avoided:

- mind registries;
- application-level primary keys;
- agent populations;
- reasoning-model ownership of identity.

Relevant ADRs:

- `0001-initial-stack.md`
- `0002-one-instance-one-mind.md`

---

## 4. Phase 2 — Memory Steward V0.1

The next architectural separation was the Memory Steward.

The reasoning engine no longer writes durable memory directly.

Instead:

```text
Experience
    ↓
Conscious Workspace
    ↓
Memory Steward
    ↓
accepted durable learning / rejected proposal
```

The Steward owns memory policy.

Initial responsibilities included:

- recall relevant durable memory;
- distinguish experience from durable knowledge;
- decide whether proposed learning should persist;
- protect identity and values from ordinary memory writes;
- journal the full interaction independently.

Relevant ADR:

- `0003-memory-steward-tool-v0.1.md`

---

## 5. Phase 3 — MCP becomes the only external integration boundary

The project initially explored several ways to attach reasoning engines.

That was simplified into a locked architectural rule:

> **We stay MCP only.**

The Mind exposes four external MCP tools:

1. `initialize_mind`
2. `mind_status`
3. `begin_interaction`
4. `complete_interaction`

The intended cycle is:

```text
Human
  ↓
begin_interaction
  ↓
Memory Steward recall
  ↓
replaceable reasoning engine
  ↓
complete_interaction
  ↓
Memory Steward validation / persistence
  ↓
journal
```

This made reasoning hosts replaceable while preserving the Mind.

---

## 6. First continuity proof

The first meaningful continuity experiment was completed using VS Code as the MCP host.

The Mind:

- loaded its existing identity;
- recalled persisted durable memory;
- retained the user's birthday;
- survived a reasoning-model switch;
- correctly supplied the same remembered information to the replacement model.

The important result was not that two models knew the same fact.

The result was:

> **The model changed. The Mind did not.**

This was the first operational proof of the core architecture.

---

## 7. Phase 4 — Bounded recall and recursive-history failure

A major implementation defect exposed an important cognitive-storage rule.

Early journal entries embedded recalled journal entries inside later Steward traces. Those traces were then recalled and embedded again.

The result was recursive historical growth and eventually MongoDB's document-size limit.

The fix introduced compact recalled experience:

- journal kind;
- timestamp;
- bounded excerpt.

The lesson became architectural:

> **Rich recall is transient. Persisted traces must remain compact and non-recursive.**

This distinction remains fundamental to the system.

---

## 8. Phase 5 — The portal

A dark-mode administrative portal was added to make the Mind inspectable.

The portal provides visibility into:

- identity;
- foundational values;
- memory;
- journal history;
- memory revision;
- evidence appraisal;
- semantic tensions;
- deliberation;
- belief transitions;
- belief reframes.

Pagination and server-side search were added because neither memory nor journal inspection should require loading the full persisted collection into the browser.

A core invariant was established:

> **Filter/search the full persisted collection first, then paginate the matching results.**

---

## 9. Phase 6 — Storage-neutral persistence

MongoDB was intentionally retained as the working demo substrate.

A provider-neutral persistence boundary was introduced:

```text
Portal / MCP
      ↓
Storage Contracts
      ↓
Provider Factory
   ↙       ↘
Mongo     Surreal
```

SurrealDB was added as a parallel adapter without changing the cognitive architecture.

The storage provider is selectable, while the September demo configuration remains explicitly Mongo-backed.

Important constraint:

> Database-native record IDs are persistence details, not cognitive identity.

---

## 10. Phase 7 — Evolvable Memory Artifacts

A major conceptual turn occurred when semantic interpretation became necessary.

The project rejected the temptation to introduce a permanent proposition table/schema.

Instead, durable memories can carry **Memory Artifacts**.

Artifacts add interpretation without replacing the original evidence.

This allows future cognitive distinctions to evolve without migrating every historical memory into a new ontology.

Relevant ADR:

- `0008-evolvable-memory-artifacts.md`

---

## 11. Phase 8 — Semantic interpretation and equivalence

Raw language is not enough to identify meaning.

For example:

- "My birthday is February 7."
- "William's birthday is February 7th."
- "Your birthday is February 7."

may refer to the same proposition even though the text differs.

A semantic interpretation artifact was introduced:

```text
subject
attribute
value
```

This lets the Steward recognize semantically equivalent evidence while preserving each original encounter.

Relevant ADR:

- `0009-semantic-interpretation-and-equivalence.md`

---

## 12. Phase 9 — Unresolved semantic tension

Once the Mind could recognize propositions, it also had to recognize contradiction.

Competing values for the same semantic slot are no longer silently overwritten.

Instead:

```text
Evidence A
    ↓
semantic interpretation
    ↓
value A

Evidence B
    ↓
semantic interpretation
    ↓
value B

same subject + attribute
different values
    ↓
UNRESOLVED SEMANTIC TENSION
```

Both evidence memories remain durable.

Relevant ADR:

- `0010-unresolved-semantic-tension.md`

---

## 13. Phase 10 — Confidence, Weight, and provenance

Evidence required more structure than "true / false."

Two dimensions were deliberately kept separate:

### Confidence

How strongly the evidence itself is believed.

### Weight

How much influence/significance the evidence deserves in the present deliberation.

These values are **not combined into one credibility score**.

Evidence also carries provenance as a chain:

```text
immediate source
    ↓
source's source
    ↓
upstream source
```

Context and condition may be recorded at each hop.

Relevant ADR:

- `0011-evidence-appraisal.md`

---

## 14. Phase 11 — Bounded investigation

Recall is not always a simple lookup.

Sometimes the Mind must "go down the rabbit hole" to determine what supporting evidence exists.

Evidence deliberation was added to identify:

- support counts;
- provenance overlap;
- appraisal gaps;
- material context differences;
- investigation questions.

The Mind can therefore recall not only a disagreement, but also **what still needs to be investigated**.

Investigation is bounded: continue only while additional evidence can materially change or clarify the conclusion.

Relevant ADR:

- `0012-evidence-deliberation-and-bounded-investigation.md`

---

## 15. Phase 12 — Re-deliberation

Current research evidence can be semantically attached to a prior unresolved tension.

The Steward then creates a new deliberation revision instead of rewriting the previous one.

This produces an auditable cognitive path:

```text
Tension
  ↓
Deliberation revision 1
  ↓
new evidence
  ↓
Deliberation revision 2
  ↓
new evidence
  ↓
Deliberation revision 3
```

The Mind remembers how its reasoning changed.

Relevant ADR:

- `0013-tension-redeliberation.md`

---

## 16. Phase 13 — Resolution readiness

The next problem was deciding when evidence is sufficiently developed to permit a belief change.

The Steward now classifies resolution readiness as:

- `blocked`
- `candidate_ready`
- `reframe_required`

A candidate is not selected by majority vote or by combining Confidence and Weight.

The initial gate requires:

- complete appraisal;
- verified source independence;
- matching timeframe;
- matching context;
- independent corroboration;
- strict dominance on the separate Confidence and Weight dimensions.

If evidence shows the values belong to different times or contexts, the result is `reframe_required`, not a forced winner.

Relevant ADR:

- `0014-resolution-readiness-before-belief-transition.md`

---

## 17. Phase 14 — Governed belief transition

`candidate_ready` does not automatically change belief.

The Conscious Workspace must explicitly propose a transition.

The Memory Steward revalidates the latest eligible deliberation before committing it.

On acceptance:

- supporting evidence for the new value is marked `current`;
- supporting evidence for the prior value is marked `superseded`;
- neither evidence memory is deleted;
- a dedicated belief-transition artifact is written;
- a dedicated journal event records the change.

Important distinction:

> **Superseded belief does not mean invalid evidence.**

Relevant ADR:

- `0015-governed-belief-transition.md`

---

## 18. Phase 15 — Scoped belief reframing

Some contradictions are not contradictions.

Example:

```text
service.owner = Alice before September 1
service.owner = Bob on/after September 1
```

or:

```text
invoice.approval_route = Alpha for Customer A
invoice.approval_route = Beta for Customer B
```

If evidence establishes the scopes, the Steward can commit a belief reframe.

Neither value becomes current or superseded.

Both become `valid_in_scope`.

The scope descriptions themselves must be evidence-backed. The reasoning host is not allowed to invent them merely to close a tension.

Relevant ADR:

- `0016-scoped-belief-reframing.md`

---

## 19. Phase 16 — Scope-aware semantic interpretation

The next refinement made scope part of proposition identity itself.

The active proposition signature is now:

```text
subject + attribute + value + scope
```

Therefore:

- same value + same scope → corroboration;
- different value + same scope → tension;
- different scope → distinct proposition.

After a committed belief reframe, the Steward-owned `scoped_belief` artifact becomes the active semantic interpretation. The original unscoped interpretation remains preserved for audit.

Research, deliberation, and belief transition are also scope-aware.

Relevant ADR:

- `0017-scope-aware-semantic-interpretation.md`

---

## 20. Current cognitive cycle

The Mind can now perform the following cycle:

```text
Experience
   ↓
Recall
   ↓
Durable Evidence
   ↓
Semantic Interpretation
   ↓
Evidence Appraisal
   ↓
Semantic Tension
   ↓
Bounded Investigation
   ↓
Re-deliberation
   ↓
Resolution Readiness
   ├───────────────┐
   ↓               ↓
Candidate Ready    Reframe Required
   ↓               ↓
Belief Transition Scoped Belief Reframe
   └───────┬───────┘
           ↓
Future Recall / New Evidence
```

All of this remains outside the replaceable reasoning engine.

---

## 21. What has been proven

### Proven

- one persistent Mind can survive reasoning-engine replacement;
- durable identity and memory are external to the reasoning engine;
- MCP can serve as the host-neutral integration boundary;
- Memory Steward policy can govern durable learning;
- semantically equivalent evidence can be recognized;
- contradictions can be preserved instead of overwritten;
- evidence can be appraised by Confidence, Weight, and provenance;
- unresolved tensions can generate investigation questions;
- new research can revise an existing deliberation;
- evidence can become candidate-ready without automatically rewriting belief;
- belief transitions can be governed and audited;
- temporal/contextual reframing can preserve multiple valid values;
- semantic comparison can respect scope;
- Mongo and Surreal can implement the same cognitive storage contracts;
- MCP stdio and Streamable HTTP continuity tests pass.

### Not claimed

The project does **not** claim:

- consciousness;
- human-equivalent cognition;
- solved epistemology;
- perfect semantic normalization;
- perfect provenance evaluation;
- complete identity governance;
- complete subconscious architecture;
- production-grade multi-user security;
- production-grade distributed transactions.

---

## 22. When can a reasoning engine use the Mind?

**Now.**

A compatible MCP host can already use the Mind through:

```text
begin_interaction
complete_interaction
```

VS Code/Copilot has already been used to prove this architecture.

The remaining work is no longer "make the Mind usable."

The remaining work is:

> **Connect the Mind to the reasoning environment we actually want to use every day.**

---

## 23. When can ChatGPT use the Mind?

The Cognitive Mind already exposes MCP.

The remaining bridge is a ChatGPT-supported MCP connection.

Current integration target:

```text
AI Cognitive Mind
        ↓
Streamable HTTP MCP
        ↓
secure remote/tunneled endpoint
        ↓
ChatGPT custom MCP app
        ↓
ChatGPT reasoning model
```

The local stdio server remains useful for VS Code.

For ChatGPT, the MCP endpoint must be reachable through a supported remote connection or secure tunnel rather than existing only as a local Codespace/desktop process.

This is now the **highest-priority milestone**.

We should not continue adding cognitive sophistication merely because another interesting cognitive problem exists.

---

## 24. Immediate usage milestone

### Milestone: "Use the Mind"

Success means:

1. Start a ChatGPT conversation.
2. ChatGPT invokes the Cognitive Mind before reasoning.
3. The Mind supplies identity, memory, current beliefs, scoped beliefs, and unresolved work.
4. ChatGPT reasons using that context.
5. ChatGPT sends the completed interaction back through the Steward.
6. Accepted learning persists.
7. Start another ChatGPT conversation/model.
8. The same Mind continues.

This is the next project checkpoint.

---

## 25. Integration sequence from here

### Step 1 — Freeze the cognitive feature surface

No new cognitive subsystem is required for first everyday use.

The current implementation is sufficient for integration testing.

### Step 2 — Run the existing Streamable HTTP MCP server

The project already supports:

```bash
python -m aicognitive_mind.mcp_server \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8001
```

### Step 3 — Establish the secure ChatGPT-reachable boundary

Use an authenticated remote deployment or supported secure MCP tunnel.

Do not expose an unauthenticated development endpoint to the public internet.

### Step 4 — Register the Mind as a ChatGPT custom MCP app

The four Mind tools remain the app boundary.

### Step 5 — Run a real continuity experiment in ChatGPT

Teach something through ChatGPT, end the conversation, start a separate conversation/model, and verify that the same Mind recalls it.

### Step 6 — Use it for actual work

Only after the live connection works should the next cognitive refinements be prioritized from real observed behavior.

---

## 26. Why this checkpoint matters

Up to this point, most cognitive requirements have been derived through architecture discussions and controlled tests.

Once the Mind is used continuously, a different source of requirements becomes available:

> **Observed cognitive failure in real work.**

That is the correct source for the next round of sophistication.

Examples:

- Did recall bring too much or too little?
- Did scope become ambiguous?
- Did a Confidence/Weight appraisal behave poorly?
- Did the Steward save something it should not have?
- Did it fail to save something important?
- Did a belief transition happen too easily?
- Did a project relationship disappear from useful recall?

Those observations should drive future architecture.

---

## 27. Working rule from this checkpoint

**Use before expanding.**

Unless a defect prevents real use, the priority order is now:

1. integration;
2. daily use;
3. observation;
4. checkpoint;
5. cognitive refinement.

Not:

1. imagine another cognitive subsystem;
2. implement it;
3. repeat indefinitely before using the Mind.

---

## 28. Documentation structure

The project documentation now has three levels.

### README

Fast orientation, development/runtime commands, and demo instructions.

### This document

The longitudinal project narrative:

- what we were trying to solve;
- how the architecture evolved;
- why major decisions were made;
- what has actually been proven;
- what happens next.

### Architecture ADRs

Detailed decisions in `docs/architecture/`.

The ADR sequence currently includes:

- 0001 — Initial Stack
- 0002 — One Instance, One Mind
- 0003 — Memory Steward Tool V0.1
- 0008 — Evolvable Memory Artifacts
- 0009 — Semantic Interpretation and Equivalence
- 0010 — Unresolved Semantic Tension
- 0011 — Evidence Appraisal
- 0012 — Evidence Deliberation and Bounded Investigation
- 0013 — Tension Re-deliberation
- 0014 — Resolution Readiness Before Belief Transition
- 0015 — Governed Belief Transition
- 0016 — Scoped Belief Reframing
- 0017 — Scope-Aware Semantic Interpretation

The missing numeric sequence reflects architecture work that existed on an earlier divergent development path and was not adopted wholesale into the current MCP architecture.

---

## 29. Future major areas — parked, not immediate

These remain legitimate future research areas, but they are **not prerequisites for using the Mind now**:

- semantic relationships between overlapping/equivalent scopes;
- richer Identity Memory;
- Identity Evidence versus Self Model;
- Social Memory / propagation of knowledge;
- subconscious role/process;
- Reflection Steward;
- Values/Governance Steward;
- Skills/Knowledge Steward;
- more sophisticated provenance-chain analysis;
- transactional hardening;
- long-term memory indexing/optimization;
- production authentication and authorization;
- multi-process cognitive scheduling.

They should be pulled forward when actual usage demonstrates the need.

---

## 30. Current project stance

The Cognitive Mind is no longer merely a storage prototype.

It is an operational cognitive architecture with:

- persistent identity;
- governed memory;
- evidence appraisal;
- semantic interpretation;
- contradiction handling;
- investigation;
- deliberation revision;
- belief transition;
- contextual/temporal reframing;
- scope-aware proposition identity;
- host-neutral MCP integration.

The next milestone is not another abstract cognitive mechanism.

> **The next milestone is to use the Mind.**


---

## 31. Parallel Body workstream

A second major development track was opened after the Mind reached the point where it could be used
through MCP.

The new track is deliberately called **Body**.

The project model is now:

```text
Mind
  +
Body
```

These are not separate identities or separate beings. They are two major systems of the same whole.

### Mind responsibility

The Mind owns:

- identity;
- durable memory;
- beliefs;
- reasoning;
- governance;
- continuity.

### Body responsibility

The Body owns:

- eyes — camera / visual input;
- ears — microphone / acoustic input;
- mouth — speech output;
- face — on-screen avatar;
- sensors;
- physical/computer interfaces;
- device lifecycle and health.

### Sensory-memory boundary

The Body does not write durable memory directly.

Raw camera frames, audio buffers, screen images, and other device data are transient sensory input.
The Mind may interpret those percepts and then use the existing Memory Steward boundary to decide
whether an experience should become durable memory.

This keeps identity and memory authority in one place.

### Parallel development rule

Mind and Body development are not sequential roadmap items.

They proceed concurrently:

```text
Mind work ───────┐
                 ├── same whole
Body work ───────┘
```

Each workstream should remain independently testable and should integrate through narrow contracts
rather than reaching into the other's internal implementation.

### Body foundation

The first Body slice introduces:

- transient sensory modalities;
- transient percepts;
- expression intents;
- device status;
- provider-neutral eyes / ears / mouth / face contracts;
- a `BodyRuntime` that coordinates attached faculties without owning cognitive state.

No camera, microphone, speech engine, or avatar vendor is selected at the foundation layer.

Body foundation details are documented in:

- `docs/body/0001-foundation.md`

The next Body slices may proceed independently: eyes, ears, mouth, face, and the Mind/Body perception
bridge.
