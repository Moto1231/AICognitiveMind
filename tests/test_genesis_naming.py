import unittest

from aicognitive_mind.domain import CognitiveMind, MindIdentity


class GenesisNamingTests(unittest.TestCase):
    def test_new_mind_may_begin_unnamed(self) -> None:
        mind = CognitiveMind(identity=MindIdentity())
        self.assertIsNone(mind.identity.self_name)
        self.assertEqual(mind.developmental_state, "genesis")


if __name__ == "__main__":
    unittest.main()
