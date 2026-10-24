import asyncio
import contextlib
import importlib.util
import io
import json
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from surrealdb import AsyncSurreal

from aicognitive_mind.surreal_preflight import ROOT_DIAGNOSTIC_HOST, preflight


APPROVED_HOST = "mir-ai-06gmqbgl1duq581garj3eabaq4.aws-use1.surreal.cloud"
PRIVATE = "synthetic-private-root-password-token-schema-payload"


def settings(**changes):
    values = {
        "surrealdb_uri": "wss://" + APPROVED_HOST + "/rpc",
        "surrealdb_namespace": "mir_ai",
        "surrealdb_database": "ai_cognitive_mind",
        "surrealdb_username": "synthetic-root-user",
        "surrealdb_password": PRIVATE,
        "surrealdb_auth_level": "root",
    }
    values.update(changes)
    return SimpleNamespace(**values)


class RootRpcFixture:
    def __init__(self):
        self.requests = []
        self.clients = []
        self.options = []
        self.namespace_exists = True
        self.database_exists = True
        self.override = None

    def factory(self, **options):
        self.options.append(options)
        client = httpx.AsyncClient(transport=httpx.MockTransport(self.handle), **options)
        self.clients.append(client)
        return client

    @staticmethod
    def reply(body, result):
        return httpx.Response(200, json={"id": body["id"], "result": result})

    async def handle(self, request):
        body = json.loads(request.content)
        self.requests.append((request, body))
        if self.override is not None:
            response = await self.override(request, body)
            if response is not None:
                return response
        if body["method"] == "signin":
            return self.reply(body, "synthetic-token-" + PRIVATE)
        if body["method"] != "query":
            raise AssertionError("Only signin and query are permitted")
        sql = body["params"][0]
        if sql == "INFO FOR ROOT;":
            result = {"namespaces": {"other-" + PRIVATE: PRIVATE}, "users": {PRIVATE: PRIVATE}}
            if self.namespace_exists:
                result["namespaces"]["mir_ai"] = "DEFINE NAMESPACE " + PRIVATE
        elif sql == "INFO FOR NS;":
            result = {"databases": {"other-" + PRIVATE: PRIVATE}, "users": {PRIVATE: PRIVATE}}
            if self.database_exists:
                result["databases"]["ai_cognitive_mind"] = "DEFINE DATABASE " + PRIVATE
        elif sql == "INFO FOR DB;":
            result = {"tables": {"memory": PRIVATE, "unknown-" + PRIVATE: PRIVATE}, "users": {PRIVATE: PRIVATE}}
        elif sql.startswith("SELECT count() AS total FROM ") and "FROM memory " in sql:
            count = 1 if "mind_id" in sql else 2
            result = [{"total": count}]
        else:
            raise AssertionError("Unexpected SQL in root diagnostic")
        return self.reply(body, [{"status": "OK", "result": result}])


class SurrealRootPreflightTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_root_signin_and_staged_read_only_headers(self):
        self.assertEqual(ROOT_DIAGNOSTIC_HOST, APPROVED_HOST)
        fixture = RootRpcFixture()
        with patch("aicognitive_mind.surreal_storage.SurrealRuntime.initialize", side_effect=AssertionError("No migrations")), patch(
            "aicognitive_mind.surreal_storage.AsyncSurreal", side_effect=AssertionError("No SDK initialization")
        ):
            result = await preflight(settings(), root_diagnostic=True, client_factory=fixture.factory)

        self.assertEqual(result["connection"], "ok")
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["auth_scope"], "root")
        self.assertTrue(result["authenticated"])
        self.assertTrue(result["namespace_exists"])
        self.assertTrue(result["database_exists"])
        self.assertEqual(result["tables"]["memory"], {
            "exists": True, "rows": 2, "tenant_count": 1, "unscoped_rows": 1,
        })
        self.assertTrue(result["conflicts"]["target_nonempty"])
        self.assertTrue(result["conflicts"]["source_not_compared"])
        self.assertEqual(result["other_table_count"], 1)
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertEqual(len(fixture.requests), 7)
        self.assertEqual([body["method"] for _, body in fixture.requests], ["signin"] + ["query"] * 6)
        self.assertEqual(fixture.requests[0][1]["params"], [{"user": "synthetic-root-user", "pass": PRIVATE}])
        self.assertEqual([body["params"][0] for _, body in fixture.requests[1:4]], [
            "INFO FOR ROOT;", "INFO FOR NS;", "INFO FOR DB;",
        ])
        for index, (request, body) in enumerate(fixture.requests):
            self.assertEqual(request.method, "POST")
            self.assertEqual(str(request.url), "https://" + APPROVED_HOST + "/rpc")
            self.assertEqual(request.headers.get("Surreal-NS"), "mir_ai" if index >= 2 else None)
            self.assertEqual(request.headers.get("Surreal-DB"), "ai_cognitive_mind" if index >= 3 else None)
            if index:
                self.assertEqual(request.headers["Authorization"], "Bearer synthetic-token-" + PRIVATE)
                self.assertNotIn(PRIVATE, body["params"][0])
            else:
                self.assertNotIn("Authorization", request.headers)
        self.assertFalse(fixture.options[0]["follow_redirects"])
        self.assertFalse(fixture.options[0]["trust_env"])
        self.assertTrue(fixture.clients[0].is_closed)

    async def test_root_mode_requires_explicit_flag_and_exact_approved_target(self):
        cases = [
            ({}, False),
            ({"surrealdb_auth_level": "database"}, True),
            ({"surrealdb_namespace": "other"}, True),
            ({"surrealdb_database": "other"}, True),
            ({"surrealdb_uri": "https://other.example.invalid/rpc"}, True),
            ({"surrealdb_uri": "https://" + APPROVED_HOST + ".evil.invalid/rpc"}, True),
            ({"surrealdb_uri": "https://" + APPROVED_HOST + ":8443/rpc"}, True),
            ({"surrealdb_uri": "https://" + APPROVED_HOST + "/prefix/rpc"}, True),
            ({"surrealdb_uri": "https://user:password@" + APPROVED_HOST + "/rpc"}, True),
            ({"surrealdb_uri": "https://" + APPROVED_HOST + "/rpc?token=" + PRIVATE}, True),
        ]
        for changes, enabled in cases:
            with self.subTest(changes=list(changes), enabled=enabled):
                fixture = RootRpcFixture()
                result = await preflight(settings(**changes), root_diagnostic=enabled, client_factory=fixture.factory)
                self.assertEqual(result["connection"], "error")
                self.assertEqual(result["stage"], "configuration")
                self.assertEqual(fixture.clients, [])
                self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_missing_namespace_or_database_stops_without_counts_or_fallback(self):
        for missing in ("namespace", "database"):
            with self.subTest(missing=missing):
                fixture = RootRpcFixture()
                fixture.namespace_exists = missing != "namespace"
                fixture.database_exists = missing != "database"
                result = await preflight(settings(), root_diagnostic=True, client_factory=fixture.factory)
                self.assertEqual(result["connection"], "error")
                self.assertTrue(result["authenticated"])
                self.assertEqual(result["stage"], missing + "_existence")
                self.assertEqual(result["error_kind"], missing + "_missing")
                self.assertEqual(result["namespace_exists"], missing != "namespace")
                if missing == "database":
                    self.assertFalse(result["database_exists"])
                self.assertNotIn("tables", result)
                self.assertEqual(len(fixture.requests), 2 if missing == "namespace" else 3)
                self.assertEqual(sum(body["method"] == "signin" for _, body in fixture.requests), 1)
                self.assertTrue(fixture.clients[0].is_closed)
                self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_malformed_inventory_fails_closed(self):
        for sql, collection, expected_stage in (
            ("INFO FOR ROOT;", "namespaces", "namespace_existence"),
            ("INFO FOR NS;", "databases", "database_existence"),
        ):
            for value in (None, {}, {collection: []}, {collection: PRIVATE}):
                with self.subTest(sql=sql, value_type=type(value).__name__):
                    fixture = RootRpcFixture()

                    async def malformed(request, body):
                        if body["method"] == "query" and body["params"][0] == sql:
                            return fixture.reply(body, [{"status": "OK", "result": value}])
                        return None

                    fixture.override = malformed
                    result = await preflight(settings(), root_diagnostic=True, client_factory=fixture.factory)
                    self.assertEqual(result["connection"], "error")
                    self.assertEqual(result["stage"], expected_stage)
                    self.assertEqual(result["error_kind"], "invalid_metadata_response")
                    self.assertNotIn("tables", result)
                    self.assertTrue(fixture.clients[0].is_closed)

    async def test_each_remote_failure_stops_after_one_signin_and_redacts_logs(self):
        stages = (
            ("signin", "authentication", 1),
            ("INFO FOR ROOT;", "namespace_existence", 2),
            ("INFO FOR NS;", "database_existence", 3),
            ("INFO FOR DB;", "metadata", 4),
            ("counts", "counts", 5),
        )
        for failing, stage, request_count in stages:
            with self.subTest(stage=stage):
                fixture = RootRpcFixture()

                async def fail(request, body):
                    operation = body["method"] if body["method"] == "signin" else body["params"][0]
                    if operation != failing and not (failing == "counts" and operation.startswith("SELECT")):
                        return None
                    print(PRIVATE)
                    logging.getLogger("httpx.root-fixture").critical(PRIVATE)
                    return httpx.Response(403, text=PRIVATE)

                fixture.override = fail
                captured = io.StringIO()
                handler = logging.StreamHandler(captured)
                logger = logging.getLogger()
                previous_disable = logger.manager.disable
                logger.addHandler(handler)
                try:
                    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                        result = await preflight(settings(), root_diagnostic=True, client_factory=fixture.factory)
                finally:
                    logger.removeHandler(handler)
                self.assertEqual(result["connection"], "error")
                self.assertEqual(result["stage"], stage)
                self.assertEqual(result["error_kind"], "http_403")
                self.assertEqual(result["authenticated"], failing != "signin")
                self.assertNotIn("tables", result)
                self.assertEqual(len(fixture.requests), request_count)
                self.assertEqual(sum(body["method"] == "signin" for _, body in fixture.requests), 1)
                self.assertTrue(fixture.clients[0].is_closed)
                self.assertEqual(logger.manager.disable, previous_disable)
                self.assertNotIn(PRIVATE, json.dumps(result) + captured.getvalue())

    async def test_structured_rpc_errors_expose_only_allowlisted_category_and_code(self):
        cases = (
            ({"code": -32002, "kind": "NotAllowed", "details": {
                "kind": "Auth", "details": {"kind": "InvalidAuth"},
            }}, "authentication_rejected", -32002),
            ({"code": -32603, "kind": "Validation", "details": {
                "kind": "InvalidParams",
            }}, "invalid_rpc_params", -32603),
            ({"code": -32000, "kind": "NotFound", "details": {"kind": "Namespace"}}, "namespace_missing", -32000),
            ({"code": -32000, "kind": "NotFound", "details": {"kind": "Database"}}, "database_missing", -32000),
            ({"code": -32002}, "authentication_or_authorization_rejected", -32002),
            ({"code": -32002, "kind": "Internal", "details": {"kind": "InvalidAuth"}}, "rpc_error", -32002),
            ({"code": -32603, "kind": {"private": PRIVATE}}, "rpc_error", -32603),
            ({"code": -32603, "kind": "NotAllowed", "details": {
                "kind": "Auth", "details": {"kind": "InvalidAuth"},
            }}, "rpc_error", -32603),
            ({"code": -32002, "kind": "Validation", "details": {"kind": "InvalidParams"}}, "rpc_error", -32002),
            ({"code": -32002, "kind": "InvalidAuth"}, "rpc_error", -32002),
            ({"code": -32603, "kind": "InvalidParams"}, "rpc_error", -32603),
            ({"code": 123456789, "kind": PRIVATE}, "rpc_error", None),
            ({"code": True, "kind": PRIVATE}, "rpc_error", None),
            ({"code": "-32002", "kind": PRIVATE}, "rpc_error", None),
        )
        for error, category, code in cases:
            with self.subTest(category=category, code_type=type(error["code"]).__name__):
                fixture = RootRpcFixture()

                async def rpc_error(request, body):
                    return httpx.Response(200, json={"id": body["id"], "error": {
                        **error, "message": "InvalidAuth " + PRIVATE, "data": {"token": PRIVATE},
                    }})

                fixture.override = rpc_error
                result = await preflight(settings(), root_diagnostic=True, client_factory=fixture.factory)
                self.assertEqual(result["connection"], "error")
                self.assertFalse(result["authenticated"])
                self.assertEqual(result["error_kind"], category)
                self.assertEqual(result.get("error_code"), code)
                self.assertNotIn(PRIVATE, json.dumps(result))
                self.assertEqual(len(fixture.requests), 1)
                self.assertTrue(fixture.clients[0].is_closed)

    async def test_database_mode_does_not_enumerate_root_or_namespace(self):
        fixture = RootRpcFixture()
        result = await preflight(settings(surrealdb_auth_level="database"), client_factory=fixture.factory)
        self.assertEqual(result["connection"], "ok")
        self.assertNotIn("auth_scope", result)
        self.assertNotIn("authenticated", result)
        self.assertEqual(fixture.requests[0][1]["params"], [{
            "user": "synthetic-root-user", "pass": PRIVATE,
            "NS": "mir_ai", "DB": "ai_cognitive_mind",
        }])
        self.assertEqual(fixture.requests[1][1]["params"][0], "INFO FOR DB;")
        self.assertEqual(len(fixture.requests), 5)
        for request, _ in fixture.requests:
            self.assertEqual(request.headers["Surreal-NS"], "mir_ai")
            self.assertEqual(request.headers["Surreal-DB"], "ai_cognitive_mind")

    async def test_root_cancellation_closes_without_retry_and_restores_logging(self):
        fixture = RootRpcFixture()
        entered = asyncio.Event()
        previous_disable = logging.root.manager.disable

        async def block(request, body):
            if body["method"] == "query":
                entered.set()
                await asyncio.Event().wait()
            return None

        fixture.override = block
        task = asyncio.create_task(preflight(settings(), root_diagnostic=True, client_factory=fixture.factory))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(len(fixture.requests), 2)
        self.assertTrue(fixture.clients[0].is_closed)
        self.assertEqual(logging.root.manager.disable, previous_disable)

    async def test_root_cli_passes_explicit_flag_and_missing_target_exits_one(self):
        spec = importlib.util.spec_from_file_location(
            "surreal_root_preflight_command_test",
            Path(__file__).resolve().parents[1] / "scripts" / "surreal_canonical.py",
        )
        command = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(command)
        configured = settings()
        report = {
            "connection": "error", "authenticated": True,
            "stage": "namespace_existence", "error_kind": "namespace_missing",
        }
        captured = io.StringIO()
        fake_preflight = AsyncMock(return_value=report)
        with patch.object(command, "preflight", fake_preflight), patch.object(
            command, "SurrealRuntime", side_effect=AssertionError("No runtime initialization")
        ), patch.object(command, "AsyncMongoClient", side_effect=AssertionError("No Mongo access")), contextlib.redirect_stdout(captured):
            with self.assertRaises(SystemExit) as exit_result:
                await command._check(configured, root_diagnostic=True)
        self.assertEqual(exit_result.exception.code, 1)
        fake_preflight.assert_awaited_once_with(configured, root_diagnostic=True)
        self.assertEqual(json.loads(captured.getvalue()), report)
        self.assertEqual(command.build_parser().parse_args(["check-root"]).command, "check-root")

    async def test_real_embedded_inventory_and_counts_leave_state_unchanged(self):
        database = AsyncSurreal("mem://")
        await database.connect()
        await database.use("mir_ai", "ai_cognitive_mind")
        fixture = RootRpcFixture()
        try:
            await database.create("memory", {"mind_id": "private-mind-" + PRIVATE, "payload": PRIVATE})
            await database.create("memory", {"payload": PRIVATE})
            before = await database.select("memory")
            schema_before = await database.query("INFO FOR DB;")
            query_errors = []

            async def embedded(request, body):
                if body["method"] != "query":
                    return None
                sql = body["params"][0]
                try:
                    result = await database.query(sql)
                except Exception as exc:
                    query_errors.append((sql, str(exc)))
                    raise
                return fixture.reply(body, [{"status": "OK", "result": result}])

            fixture.override = embedded
            result = await preflight(settings(), root_diagnostic=True, client_factory=fixture.factory)
            self.assertEqual(query_errors, [])
            self.assertEqual(result["connection"], "ok", result)
            self.assertTrue(result["namespace_exists"])
            self.assertTrue(result["database_exists"])
            self.assertEqual(result["tables"]["memory"]["rows"], 2)
            self.assertEqual(await database.select("memory"), before)
            self.assertEqual(await database.query("INFO FOR DB;"), schema_before)
            self.assertNotIn(PRIVATE, json.dumps(result))
        finally:
            await database.close()
