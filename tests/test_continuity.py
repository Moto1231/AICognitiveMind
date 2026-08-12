import unittest

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import CognitiveActor, EventType
from aicognitive_mind.engines import EchoReasoningEngine
from aicognitive_mind.storage import InMemoryBeingStore, InMemoryEventStore


class ContinuityTests(unittest.IsolatedAsyncioTestCase):
    async def test_identity_and_history_survive_engine_swap(self) -> None:
        beings = InMemoryBeingStore()
        events = InMemoryEventStore()

        core_a = CognitiveCore(
            beings=beings,
            events=events,
            engine=EchoReasoningEngine(engine_id="engine-a", prefix="A considered"),
        )
        being = await core_a.create_being(
            name="Genesis-1",
            host_id="william-enright",
            values=("understanding-before-recommending",),
        )
        first = await core_a.interact(being.being_id, "Remember how we began.")

        core_b = CognitiveCore(
            beings=beings,
            events=events,
            engine=EchoReasoningEngine(engine_id="engine-b", prefix="B considered"),
        )
        second = await core_b.interact(being.being_id, "Who is thinking now?")

        restored = await beings.get(being.being_id)
        history = await core_b.history(being.being_id)

        self.assertEqual(restored, being)
        self.assertEqual(first.engine_id, "engine-a")
        self.assertEqual(second.engine_id, "engine-b")
        self.assertEqual(history[0].event_type, EventType.BEING_CREATED)
        self.assertEqual(len(history), 7)

        proposals = [event for event in history if event.event_type == EventType.REASONING_PROPOSED]
        self.assertEqual(
            [event.payload["engine_id"] for event in proposals],
            ["engine-a", "engine-b"],
        )
        self.assertTrue(
            all(event.source == CognitiveActor.REASONING_ENGINE for event in proposals)
        )
        self.assertTrue(
            all(event.recorded_by == CognitiveActor.CONSCIOUS_WORKSPACE for event in proposals)
        )


if __name__ == "__main__":
    unittest.main()

