import asyncio
import contextlib
import copy
import importlib.util
import io
import json
import logging
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from surrealdb import AsyncSurreal, RecordID

from aicognitive_mind.surreal_preflight import preflight


TABLES = (
    "mind", "journal", "memory", "diagnostics", "evidence",
    "runtime_records", "commit_receipts", "commit_state",
)
PRIVATE = "private-fixture-password-token-payload"


def settings(**changes):
    values = {
        "surrealdb_uri": "wss://database.example.invalid/rpc",
        "surrealdb_namespace": "fixture_namespace",
        "surrealdb_database": "fixture_database",
        "surrealdb_username": "fixture_user",
        "surrealdb_password": PRIVATE,
        "surrealdb_auth_level": "database",
    }
    values.update(changes)
    return SimpleNamespace(**values)


class RpcFixture:
    def __init__(self):
        self.requests = []
        self.clients = []
        self.client_options = []
        self.table_names = set(TABLES)
        self.counts = {table: (0, 0, 0) for table in TABLES}
        self.duplicate_mind_scopes = 0
        self.account_counts = (0, 0, 0, 0)
        self.override = None

    def factory(self, **options):
        self.client_options.append(options)
        client = httpx.AsyncClient(transport=httpx.MockTransport(self.handle), **options)
        self.clients.append(client)
        return client

    async def handle(self, request):
        body = json.loads(request.content)
        self.requests.append((request, body))
        if self.override is not None:
            response = await self.override(request, body)
            if response is not None:
                return response
        if body["method"] == "signin":
            result = "synthetic-" + PRIVATE
        elif body["method"] == "query":
            result = self.query_result(body["params"][0])
        else:
            raise AssertionError("Unexpected RPC method: " + body["method"])
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    def query_result(self, sql):
        if sql.strip().rstrip(";") == "INFO FOR DB":
            return [{"status": "OK", "result": {"tables": {
                table: "DEFINE TABLE " + PRIVATE for table in self.table_names
            }}}]
        results = []
        for statement in filter(str.strip, sql.split(";")):
            self.assert_read_count(statement)
            table = next(table for table in TABLES if re.search(r"\bFROM\s+" + table + r"\b", statement))
            rows, tenants, unscoped = self.counts[table]
            if "GROUP BY key" in statement:
                total = self.account_counts[3]
            elif "kind = 'account'" in statement:
                index = 1 if "string::trim" in statement else (2 if "key = NONE" in statement else 0)
                total = self.account_counts[index]
            elif "copies > 1" in statement:
                total = self.duplicate_mind_scopes
            elif "GROUP BY mind_id" in statement:
                total = tenants
            elif "mind_id" in statement:
                total = unscoped
            else:
                total = rows
            results.append({"status": "OK", "result": [{"total": total}]})
        return results

    @staticmethod
    def assert_read_count(sql):
        if not sql.lstrip().startswith("SELECT ") or "count()" not in sql:
            raise AssertionError("Expected aggregate SELECT only")
        if re.search(r"\b(?:CREATE|UPDATE|DELETE|DEFINE|REMOVE|INSERT|UPSERT|USE)\b", sql, re.I):
            raise AssertionError("Preflight attempted a write")


class SurrealPreflightTests(unittest.IsolatedAsyncioTestCase):
    def test_workflow_credential_gate_applies_only_to_migration(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" /
                    "canonical-surreal.yml").read_text(encoding="utf-8")
        gate = workflow.split("- name: Require canonical Surreal secrets\n", 1)[1]
        gate = gate.split("\n      - name:", 1)[0]
        self.assertIn("if: ${{ inputs.operation == 'migrate-from-atlas' }}", gate)

    async def test_missing_credentials_report_host_without_any_network_request(self):
        factory = unittest.mock.Mock(side_effect=AssertionError("No network without credentials"))
        result = await preflight(
            settings(surrealdb_username=None, surrealdb_password=None), client_factory=factory,
        )
        factory.assert_not_called()
        self.assertEqual(result, {
            "endpoint_host": "database.example.invalid", "namespace": "fixture_namespace",
            "database": "fixture_database", "connection": "not_configured",
            "stage": "configuration", "error_kind": "missing_credentials",
        })

    async def test_reads_only_metadata_and_fixed_aggregate_queries(self):
        fixture = RpcFixture()
        fixture.table_names.add("private_table; DELETE mind; " + PRIVATE)
        fixture.counts["mind"] = (3, 2, 1)
        fixture.counts["runtime_records"] = (8, 2, 3)
        fixture.duplicate_mind_scopes = 1
        fixture.account_counts = (7, 2, 1, 1)

        with patch("aicognitive_mind.surreal_storage.SurrealRuntime.initialize", side_effect=AssertionError("Runtime initialization writes")), patch(
            "aicognitive_mind.surreal_storage.AsyncSurreal", side_effect=AssertionError("SDK must not create a target")
        ):
            result = await preflight(settings(), client_factory=fixture.factory)

        self.assertEqual(result["connection"], "ok")
        self.assertEqual(result["endpoint_host"], "database.example.invalid")
        self.assertEqual(result["namespace"], "fixture_namespace")
        self.assertEqual(result["database"], "fixture_database")
        self.assertEqual(result["tables"]["mind"], {"exists": True, "rows": 3, "tenant_count": 2, "unscoped_rows": 1})
        self.assertEqual(result["tables"]["runtime_records"], {"exists": True, "rows": 8, "tenant_count": 2, "unscoped_rows": 3})
        self.assertEqual(result["account_lookup_counts"], {
            "rows": 7, "missing_mind_mapping": 2,
            "legacy_missing_key": 1, "duplicate_global_keys": 1,
        })
        self.assertEqual(result["other_table_count"], 1)
        self.assertTrue(result["conflicts"]["target_nonempty"])
        self.assertEqual(result["conflicts"]["unscoped_rows"], 4)
        self.assertEqual(result["conflicts"]["duplicate_mind_scopes"], 1)
        self.assertTrue(result["conflicts"]["unknown_tables_present"])
        self.assertTrue(result["conflicts"]["account_lookup_review_required"])
        self.assertTrue(result["conflicts"]["source_not_compared"])
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertEqual(fixture.requests[0][1]["method"], "signin")
        self.assertEqual(fixture.requests[0][1]["params"], [{
            "NS": "fixture_namespace", "DB": "fixture_database",
            "user": "fixture_user", "pass": PRIVATE,
        }])
        self.assertTrue(all(body["method"] in {"signin", "query"} for _, body in fixture.requests))
        for request, body in fixture.requests:
            self.assertEqual(request.method, "POST")
            self.assertEqual(str(request.url), "https://database.example.invalid/rpc")
            self.assertEqual(request.headers["Surreal-NS"], "fixture_namespace")
            self.assertEqual(request.headers["Surreal-DB"], "fixture_database")
            if body["method"] == "query":
                self.assertEqual(request.headers["Authorization"], "Bearer synthetic-" + PRIVATE)
                self.assertNotIn(PRIVATE, body["params"][0])
        self.assertTrue(fixture.clients[0].is_closed)
        self.assertFalse(fixture.client_options[0].get("follow_redirects", False))
        self.assertFalse(fixture.client_options[0]["trust_env"])

    async def test_invalid_endpoints_are_rejected_before_constructing_client(self):
        for uri in (
            "ws://database.example.invalid/rpc",
            "http://database.example.invalid/rpc",
            "mem://",
            "surrealkv://fixture",
            "https:///rpc",
            "https://user:password@database.example.invalid/rpc",
            "https://database.example.invalid/rpc?token=" + PRIVATE,
            "https://database.example.invalid/rpc#" + PRIVATE,
        ):
            with self.subTest(uri=uri):
                fixture = RpcFixture()
                result = await preflight(settings(surrealdb_uri=uri), client_factory=fixture.factory)
                self.assertNotEqual(result["connection"], "ok")
                self.assertEqual(fixture.clients, [])
                self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_missing_credentials_and_broader_auth_are_rejected_without_requests(self):
        for changes in (
            {"surrealdb_username": None, "surrealdb_password": None},
            {"surrealdb_username": None},
            {"surrealdb_password": None},
            {"surrealdb_auth_level": "root"},
            {"surrealdb_auth_level": "namespace"},
        ):
            with self.subTest(changes=list(changes)):
                fixture = RpcFixture()
                result = await preflight(settings(**changes), client_factory=fixture.factory)
                self.assertNotEqual(result["connection"], "ok")
                self.assertEqual(fixture.requests, [])
                self.assertEqual(fixture.clients, [])

    async def test_authentication_and_query_failures_are_safe_and_close_client(self):
        for failure_at in ("signin", "info", "counts"):
            for failure in ("http", "rpc", "query", "malformed", "transport"):
                if failure == "query" and failure_at == "signin":
                    continue
                with self.subTest(stage=failure_at, failure=failure):
                    fixture = RpcFixture()

                    async def fail(request, body):
                        stage = "signin" if body["method"] == "signin" else (
                            "info" if body["params"][0].startswith("INFO") else "counts"
                        )
                        if stage != failure_at:
                            return None
                        print(PRIVATE)
                        logging.getLogger("surrealdb.fixture").critical(PRIVATE)
                        if failure == "transport":
                            raise httpx.ConnectError(PRIVATE, request=request)
                        if failure == "http":
                            return httpx.Response(401, text=PRIVATE)
                        if failure == "rpc":
                            return httpx.Response(200, json={"id": body["id"], "error": {"message": PRIVATE}})
                        if failure == "query":
                            return httpx.Response(200, json={"id": body["id"], "result": [{"status": "ERR", "result": PRIVATE}]})
                        return httpx.Response(200, content=PRIVATE)

                    fixture.override = fail
                    captured = io.StringIO()
                    handler = logging.StreamHandler(captured)
                    logger = logging.getLogger()
                    previous_disable = logger.manager.disable
                    logger.addHandler(handler)
                    try:
                        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                            result = await preflight(settings(), client_factory=fixture.factory)
                    finally:
                        logger.removeHandler(handler)
                    self.assertEqual(result["connection"], "error")
                    self.assertIn("error_kind", result)
                    self.assertNotIn(PRIVATE, json.dumps(result) + captured.getvalue())
                    self.assertTrue(fixture.clients[0].is_closed)
                    self.assertEqual(logger.manager.disable, previous_disable)

    async def test_redirect_is_not_followed(self):
        fixture = RpcFixture()

        async def redirect(request, body):
            return httpx.Response(307, headers={"Location": "https://other.example.invalid/" + PRIVATE})

        fixture.override = redirect
        result = await preflight(settings(), client_factory=fixture.factory)
        self.assertEqual(result["connection"], "error")
        self.assertEqual(len(fixture.requests), 1)
        self.assertTrue(fixture.clients[0].is_closed)
        self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_total_timeout_is_bounded_and_closes_client(self):
        fixture = RpcFixture()

        async def block(request, body):
            await asyncio.Event().wait()

        fixture.override = block
        result = await asyncio.wait_for(
            preflight(settings(), client_factory=fixture.factory, timeout_seconds=0.01),
            timeout=1,
        )
        self.assertEqual(result["connection"], "error")
        self.assertIn("timeout", result["error_kind"])
        self.assertTrue(fixture.clients[0].is_closed)

    async def test_cancellation_propagates_and_closes_client(self):
        fixture = RpcFixture()
        entered = asyncio.Event()
        previous_disable = logging.root.manager.disable

        async def block(request, body):
            entered.set()
            await asyncio.Event().wait()

        fixture.override = block
        task = asyncio.create_task(preflight(settings(), client_factory=fixture.factory))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(fixture.clients[0].is_closed)
        self.assertEqual(logging.root.manager.disable, previous_disable)

    async def test_tls_endpoint_preserves_proxy_prefix_but_report_contains_host_only(self):
        fixture = RpcFixture()
        result = await preflight(
            settings(surrealdb_uri="https://database.example.invalid:8443/private/" + PRIVATE),
            client_factory=fixture.factory,
        )
        self.assertEqual(result["connection"], "ok")
        self.assertEqual(result["endpoint_host"], "database.example.invalid")
        self.assertTrue(all(
            str(request.url) == "https://database.example.invalid:8443/private/" + PRIVATE + "/rpc"
            for request, _ in fixture.requests
        ))
        self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_invalid_signin_response_cannot_become_authenticated(self):
        for token in (None, 123, {}, {"unexpected": PRIVATE}):
            with self.subTest(token_type=type(token).__name__):
                fixture = RpcFixture()

                async def invalid_token(request, body):
                    return httpx.Response(200, json={"id": body["id"], "result": token})

                fixture.override = invalid_token
                result = await preflight(settings(), client_factory=fixture.factory)
                self.assertEqual(result["connection"], "error")
                self.assertEqual(result["error_kind"], "invalid_auth_response")
                self.assertEqual(len(fixture.requests), 1)
                self.assertTrue(fixture.clients[0].is_closed)
                self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_absent_tables_are_explicit_without_querying_them(self):
        fixture = RpcFixture()
        fixture.table_names = {"memory"}
        result = await preflight(settings(), client_factory=fixture.factory)
        self.assertEqual(result["connection"], "ok")
        self.assertEqual(result["tables"]["mind"], {
            "exists": False, "rows": 0, "tenant_count": 0, "unscoped_rows": 0,
        })
        self.assertTrue(result["tables"]["memory"]["exists"])
        self.assertFalse(result["conflicts"]["target_nonempty"])
        self.assertEqual(len(fixture.requests), 5)

    async def test_invalid_metadata_and_counts_cannot_become_empty_success(self):
        for invalid in (None, {"tables": []}, [{"total": -1}], [{"total": True}], [{"total": PRIVATE}]):
            with self.subTest(invalid_type=type(invalid).__name__):
                fixture = RpcFixture()

                async def malformed(request, body):
                    if body["method"] != "query":
                        return None
                    is_info = body["params"][0].startswith("INFO")
                    if is_info != (invalid is None or isinstance(invalid, dict)):
                        return None
                    return httpx.Response(200, json={"id": body["id"], "result": [{"status": "OK", "result": invalid}]})

                fixture.override = malformed
                result = await preflight(settings(), client_factory=fixture.factory)
                self.assertEqual(result["connection"], "error")
                self.assertNotIn("tables", result)
                self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_response_size_is_bounded(self):
        fixture = RpcFixture()

        async def oversized(request, body):
            return httpx.Response(200, content=b"x" * 1_048_577)

        fixture.override = oversized
        result = await preflight(settings(), client_factory=fixture.factory)
        self.assertEqual(result["connection"], "error")
        self.assertEqual(result["error_kind"], "response_too_large")
        self.assertTrue(fixture.clients[0].is_closed)

    async def test_cleanup_failure_cannot_publish_a_success_summary(self):
        fixture = RpcFixture()
        previous_disable = logging.root.manager.disable
        captured = io.StringIO()

        class FailingCloseTransport(httpx.MockTransport):
            async def aclose(self):
                await super().aclose()
                print(PRIVATE)
                logging.getLogger("httpx.fixture").critical(PRIVATE)
                raise RuntimeError(PRIVATE)

        def factory(**options):
            client = httpx.AsyncClient(transport=FailingCloseTransport(fixture.handle), **options)
            fixture.clients.append(client)
            return client

        handler = logging.StreamHandler(captured)
        logger = logging.getLogger()
        logger.addHandler(handler)
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                result = await preflight(settings(), client_factory=factory)
        finally:
            logger.removeHandler(handler)
        self.assertEqual(result["connection"], "error")
        self.assertEqual(result["error_kind"], "request_failed")
        self.assertNotIn("tables", result)
        self.assertNotIn("account_lookup_counts", result)
        self.assertNotIn(PRIVATE, json.dumps(result) + captured.getvalue())
        self.assertEqual(logging.root.manager.disable, previous_disable)
        self.assertTrue(fixture.clients[0].is_closed)

    async def test_actual_embedded_queries_leave_all_seeded_state_unchanged(self):
        database = AsyncSurreal("mem://")
        await database.connect()
        await database.use("preflight_test", "preflight_test")
        fixture = RpcFixture()
        try:
            for table in TABLES:
                await database.create(table, {"mind_id": "private_tenant_alpha", "payload": PRIVATE})
                legacy_id = RecordID(table, "root" if table == "commit_state" else "legacy_private_id")
                await database.create(legacy_id, {"payload": PRIVATE, "version": 7})
            await database.create("mind", {"mind_id": "private_tenant_alpha", "payload": PRIVATE})
            await database.create("mind", {"mind_id": "private_tenant_beta", "payload": PRIVATE})
            await database.create("mind", {"mind_id": None, "payload": PRIVATE})
            await database.create(RecordID("runtime_records", "account_legacy_private_id"), {
                "kind": "account", "payload": PRIVATE,
            })
            await database.create(RecordID("runtime_records", "account_blank_private_id"), {
                "kind": "account", "key": "account_blank_private_key",
                "mind_id": "  ", "payload": PRIVATE,
            })
            for tenant in ("private_tenant_alpha", "private_tenant_beta"):
                await database.create("runtime_records", {
                    "mind_id": tenant, "key": "account_same_private_key", "kind": "account",
                    "claim": PRIVATE, "oauth_access_token": PRIVATE,
                })
            await database.create("runtime_records", {
                "mind_id": "private_tenant_alpha", "key": "body_request_private_id",
                "kind": "body_request", "claim": PRIVATE, "claim_until": 123,
            })
            await database.create("extra_private_table", {"payload": PRIVATE})
            all_tables = TABLES + ("extra_private_table",)
            before = copy.deepcopy({table: await database.select(table) for table in all_tables})
            schema_before = await database.query("INFO FOR DB;")
            query_errors = []

            async def embedded(request, body):
                if body["method"] != "query":
                    return None
                sql = body["params"][0]
                if sql != "INFO FOR DB;":
                    RpcFixture.assert_read_count(sql)
                try:
                    result = await database.query(sql)
                except Exception as exc:
                    query_errors.append((sql, str(exc)))
                    raise
                return httpx.Response(200, json={"id": body["id"], "result": [{"status": "OK", "result": result}]})

            fixture.override = embedded
            result = await preflight(settings(), client_factory=fixture.factory)
            after = {table: await database.select(table) for table in all_tables}
            self.assertEqual(after, before)
            self.assertEqual(await database.query("INFO FOR DB;"), schema_before)
            self.assertEqual(query_errors, [])
            self.assertEqual(result["connection"], "ok", result)
            self.assertEqual(result["tables"]["mind"], {
                "exists": True, "rows": 5, "tenant_count": 2, "unscoped_rows": 2,
            })
            self.assertEqual(result["conflicts"]["duplicate_mind_scopes"], 1)
            self.assertEqual(result["account_lookup_counts"], {
                "rows": 4, "missing_mind_mapping": 2,
                "legacy_missing_key": 1, "duplicate_global_keys": 1,
            })
            self.assertEqual(result["other_table_count"], 1)
            serialized = json.dumps(result)
            for value in (PRIVATE, "private_tenant_alpha", "private_tenant_beta", "account_same_private_key", "legacy_private_id"):
                self.assertNotIn(value, serialized)
            self.assertTrue(fixture.clients[0].is_closed)
        finally:
            await database.close()

    async def test_check_command_prints_safe_report_and_never_constructs_runtime(self):
        spec = importlib.util.spec_from_file_location(
            "surreal_canonical_preflight_test",
            Path(__file__).resolve().parents[1] / "scripts" / "surreal_canonical.py",
        )
        command = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(command)
        configured = settings()
        for report in (
            {"connection": "ok", "stage": "complete"},
            {"connection": "error", "stage": "authentication", "error_kind": "http_401"},
        ):
            with self.subTest(connection=report["connection"]):
                captured = io.StringIO()
                fake_preflight = AsyncMock(return_value=report)
                with patch.object(command, "preflight", fake_preflight), patch.object(
                    command, "SurrealRuntime", side_effect=AssertionError("Runtime construction writes")
                ), patch.object(
                    command, "AsyncMongoClient", side_effect=AssertionError("Check must not contact Mongo")
                ), contextlib.redirect_stdout(captured):
                    if report["connection"] == "ok":
                        await command._check(configured)
                    else:
                        with self.assertRaises(SystemExit) as exit_result:
                            await command._check(configured)
                        self.assertEqual(exit_result.exception.code, 1)
                self.assertEqual(json.loads(captured.getvalue()), report)
                fake_preflight.assert_awaited_once_with(configured)

    async def test_check_configuration_failure_ignores_dotenv_and_redacts_exception(self):
        spec = importlib.util.spec_from_file_location(
            "surreal_canonical_configuration_test",
            Path(__file__).resolve().parents[1] / "scripts" / "surreal_canonical.py",
        )
        command = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(command)
        captured = io.StringIO()
        with patch.object(command, "Settings", side_effect=ValueError(PRIVATE)) as constructor, patch.object(
            command, "get_settings", side_effect=AssertionError("Cached dotenv settings must not be read")
        ), patch("sys.argv", ["surreal_canonical.py", "check"]), contextlib.redirect_stdout(captured):
            with self.assertRaises(SystemExit) as exit_result:
                command.main()
        self.assertEqual(exit_result.exception.code, 1)
        constructor.assert_called_once_with(_env_file=None)
        self.assertEqual(json.loads(captured.getvalue()), {
            "connection": "error", "error_kind": "invalid_configuration", "stage": "configuration",
        })
        self.assertNotIn(PRIVATE, captured.getvalue())
