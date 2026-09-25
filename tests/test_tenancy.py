import unittest

from aicognitive_mind.config import Settings
from aicognitive_mind.domain import CognitiveMind, MindIdentity
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.tenancy import verify_live_tenancy


class LiveTenancyProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_surreal_probe_proves_isolation_and_cleans_up(self) -> None:
        settings = Settings(
            storage_provider="surreal",
            surrealdb_uri="mem://",
            surrealdb_namespace="tenancy_probe",
            surrealdb_database="cognitive_mind",
            axiom_mind_id="axiom",
        )
        storage = await create_storage(settings)
        try:
            await storage.mind.initialize(
                CognitiveMind(identity=MindIdentity(self_name="Axiom"))
            )
            result = await verify_live_tenancy(storage)

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["provider"], "surreal")
            self.assertEqual(result["primary_mind_id"], "axiom")
            self.assertEqual(
                set(result["verified_collections"]),
                {
                    "mind",
                    "memory",
                    "journal",
                    "diagnostics",
                    "evidence",
                    "runtime_records",
                },
            )
            self.assertEqual(
                (await storage.mind.load()).identity.self_name,
                "Axiom",
            )

            probe_id = result["probe_mind_id"]
            for table in (
                "mind",
                "memory",
                "journal",
                "diagnostics",
                "evidence",
                "runtime_records",
                "commit_receipts",
                "commit_state",
            ):
                rows = await storage.runtime.database.query(
                    f"SELECT * FROM {table} WHERE mind_id = $mind_id;",
                    {"mind_id": probe_id},
                )
                self.assertEqual(rows, [], table)
        finally:
            await storage.runtime.close()


if __name__ == "__main__":
    unittest.main()
