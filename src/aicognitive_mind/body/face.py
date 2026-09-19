from __future__ import annotations

from dataclasses import dataclass, field

from aicognitive_mind.body.domain import (
    DeviceStatus,
    ExpressionIntent,
    ExpressionModality,
)


@dataclass(slots=True)
class BrowserAvatarOutput:
    """Transient browser-facing output adapter for the Body's Face."""

    _pending: ExpressionIntent | None = field(default=None, init=False, repr=False)

    async def status(self) -> DeviceStatus:
        return DeviceStatus(
            device="face",
            available=True,
            detail="browser VRM avatar output ready",
        )

    async def render(self, intent: ExpressionIntent) -> None:
        if intent.modality != ExpressionModality.AVATAR:
            raise ValueError("Browser avatar accepts avatar ExpressionIntent only")

        metadata = dict(intent.metadata)
        expression = str(metadata.get("expression", "neutral")).strip() or "neutral"
        raw_weight = metadata.get("weight", 1.0)
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as exc:
            raise ValueError("Avatar expression weight must be numeric") from exc
        if not 0.0 <= weight <= 1.0:
            raise ValueError("Avatar expression weight must be between 0 and 1")

        metadata["expression"] = expression
        metadata["weight"] = weight
        self._pending = intent.model_copy(update={"metadata": metadata})

    def consume(self) -> ExpressionIntent | None:
        intent = self._pending
        self._pending = None
        return intent
