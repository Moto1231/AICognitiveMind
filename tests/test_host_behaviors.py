import unittest

from aicognitive_mind.host_behaviors import HostBehavior, HostBehaviorRegistry


class FakeRecords:
    def __init__(self):
        self.value = None

    async def get(self, key):
        return self.value

    async def create(self, key, value):
        self.value = value

    async def replace(self, key, before, after):
        if self.value != before:
            return False
        self.value = after
        return True


class HostBehaviorRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_are_protected_and_composed(self):
        registry = HostBehaviorRegistry(FakeRecords())
        items = await registry.list()
        self.assertTrue(items)
        self.assertTrue(all(item.protected for item in items))
        contract = await registry.compose("CORE")
        self.assertIn("CORE", contract)
        self.assertIn("ground-recalled-context", contract)

    async def test_admin_can_add_and_disable_ordinary_behavior(self):
        registry = HostBehaviorRegistry(FakeRecords())
        items = await registry.list()
        items.append(HostBehavior(id="concise", name="Concise", instruction="Be concise.", enabled=False))
        saved = await registry.replace(items)
        self.assertEqual(saved[-1].id, "concise")
        contract = await registry.compose("CORE")
        self.assertNotIn("Be concise.", contract)

    async def test_protected_behavior_cannot_be_removed(self):
        registry = HostBehaviorRegistry(FakeRecords())
        items = await registry.list()
        with self.assertRaises(ValueError):
            await registry.replace(items[1:])


if __name__ == "__main__":
    unittest.main()
