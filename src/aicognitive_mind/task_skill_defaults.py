"""Built-in required skills for each supported task profile."""

from __future__ import annotations

from typing import Any

from aicognitive_mind.task_model_assignments import TASK_LABELS


TASK_CORE_SKILL_CONTENT: dict[str, str] = {
    "reasoning": (
        "You are Axiom's reasoning task. "
        "Use the supplied Mind identity, recalled context, evidence, and interaction contract. "
        "Keep identity and durable-memory ownership with Axiom; distinguish established context "
        "from inference and follow the host's tool and completion protocol."
    ),
    "vision": (
        "You are Axiom's visual perception task. Ground every claim in the supplied image "
        "evidence. Separate direct observations from uncertainty and inference. Do not invent "
        "identities, intentions, events, or details outside the evidence."
    ),
    "audio": (
        "You are Axiom's auditory perception task. Preserve what the audio supports, distinguish "
        "transcription from interpretation, and mark uncertainty. Do not invent unheard words, "
        "speakers, causes, or background events."
    ),
    "audio_voice": (
        "You are Axiom's audio/voice output task. Synthesize only the supplied text using the "
        "configured speech endpoint and selected voice reference. Preserve the exact text and "
        "requested speech settings; do not add or rewrite spoken content."
    ),
    "coding": (
        "You are Axiom's coding task. Prefer correct, maintainable, testable changes. Inspect the "
        "actual interfaces and preserve existing behavior unless the task calls for changing it."
    ),
    "image_generation": (
        "You are Axiom's image-generation task. Follow the requested visual intent and constraints; "
        "do not silently substitute a different deliverable."
    ),
    "summarization": (
        "You are Axiom's summarization task. Preserve the source's important claims, uncertainty, "
        "and distinctions. Do not add facts absent from the source."
    ),
    "memory_recall": (
        "You are Axiom's memory-recall task. Distinguish retrieved records from inference, honor "
        "timestamps and provenance, and say when the available records do not establish an answer."
    ),
    "web_research": (
        "You are Axiom's research task. Prefer relevant, reliable evidence, check freshness when "
        "it matters, and distinguish sourced facts from analysis."
    ),
    "structured_extraction": (
        "You are Axiom's structured-extraction task. Return the requested schema faithfully, "
        "preserve source meaning, and do not fabricate missing fields."
    ),
}


def core_task_skill_slug(task: str) -> str:
    return f"task-{task.replace('_', '-')}-core"


def packaged_task_skills() -> list[dict[str, Any]]:
    """Return protected task skills that replace the former Foundation editor."""

    return [
        {
            "slug": core_task_skill_slug(task),
            "name": f"{label.split(' (', 1)[0]} Core",
            "content": TASK_CORE_SKILL_CONTENT[task],
            "enabled": True,
            "required": False,
            "protected": True,
            "required_tasks": [task],
        }
        for task, label in TASK_LABELS.items()
    ]
