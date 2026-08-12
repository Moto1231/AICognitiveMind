import unittest

from aicognitive_mind.domain import CognitiveActor
from aicognitive_mind.permissions import (
    CognitiveOperation,
    CognitivePermissionError,
    PermissionPolicy,
)


class PermissionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PermissionPolicy()

    def test_reasoning_engine_can_propose_but_not_write_memory(self) -> None:
        self.policy.assert_allowed(
            CognitiveActor.REASONING_ENGINE,
            CognitiveOperation.PROPOSE_MEMORY,
        )

        with self.assertRaises(CognitivePermissionError):
            self.policy.assert_allowed(
                CognitiveActor.REASONING_ENGINE,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            )

        with self.assertRaises(CognitivePermissionError):
            self.policy.assert_allowed(
                CognitiveActor.REASONING_ENGINE,
                CognitiveOperation.RECORD_JOURNAL,
            )

    def test_reasoning_engine_cannot_revise_identity(self) -> None:
        with self.assertRaises(CognitivePermissionError):
            self.policy.assert_allowed(
                CognitiveActor.REASONING_ENGINE,
                CognitiveOperation.APPROVE_IDENTITY_REVISION,
            )


if __name__ == "__main__":
    unittest.main()
