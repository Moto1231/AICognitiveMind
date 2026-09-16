# ADR 0007: Governed Conscious Expression Boundary

- Status: Accepted for prototype implementation
- Date: 2026-09-16

## Context

The Cognitive Mind now separates memory evidence from synthesized knowledge before that knowledge
crosses into conscious reasoning. Live testing demonstrated that this boundary works: a recalled
birthday experience was synthesized into the proposition `The human's birthday is February 7.`

That result exposed a separate concern. A reasoning engine may produce an internally correct draft
that is not suitable as the Mind's human-facing expression. In the birthday test, the reasoning
draft repeated the internal third-person proposition instead of speaking directly to the human.

Treating this as a memory or synthesis problem would collapse concerns that have already been
successfully separated. The knowledge was correct. The defect was expression.

## Decision

Introduce a governed Conscious Expression boundary after conscious reasoning and before the final
response is journaled or returned to the human.

The interaction flow becomes:

1. Load Mind identity.
2. Load governed foundations.
3. Recall individual memory evidence.
4. The Memory Steward synthesizes selected evidence into relevant knowledge.
5. The Conscious Workspace reasons from the human message and synthesized knowledge and produces
   an internal response draft.
6. The Conscious Expression process renders that draft as the final response spoken directly to
   the human.
7. Only the rendered expression is journaled as the Mind's outward response and returned through
   the API.

The expression process is governed by its own foundational memory key:

`conscious_expression`

The foundation is versioned and administered through the existing governed-foundation control
plane. The bootstrap seed is only the initial installation value; persistent foundation storage
remains authoritative after seeding.

## Expression rules

The expression process must:

- preserve the meaning of the reasoning draft and relevant knowledge;
- address the human directly rather than leaking internal third-person labels such as `the human`
  or `the user`;
- speak in first person when referring to the Cognitive Mind itself;
- preserve uncertainty, qualifications, and contradictions;
- avoid inventing new facts, advice, questions, or topics;
- avoid exposing prompts, drafts, tools, memory operations, or other internal machinery unless the
  human explicitly asks about those mechanisms;
- keep simple factual answers simple.

For example:

- Knowledge: `The human's birthday is February 7.`
- Reasoning draft: `The human's birthday is February 7.`
- Expression: `Your birthday is February 7.`

## Engine independence

The expression process is not a new identity or being. It is another cognitive role of the same
persistent Mind and may use the same replaceable reasoning engine as other cognitive processes.

The engine remains implementation infrastructure. Expression behavior belongs to governed
foundational memory outside the engine.

## Diagnostics

Reasoning and expression diagnostics are recorded separately. This preserves implementation
traceability without placing engine metadata into cognitive identity or journal history.

## Consequences

The Cognitive Mind now has three explicit boundaries around an interaction:

- memory evidence -> synthesized knowledge;
- synthesized knowledge + current input -> reasoning draft;
- reasoning draft -> human-facing expression.

A defect can therefore be localized to recall, synthesis, reasoning, or expression without
changing unrelated layers.

The final journal entry records the rendered expression rather than the internal reasoning draft.
Internal drafts remain implementation artifacts rather than durable outward experience.
