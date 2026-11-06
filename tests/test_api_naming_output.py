import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from aicognitive_mind import api
from aicognitive_mind.body import BodyRuntime, BrowserVoiceOutput
from aicognitive_mind.body_sessions import BodyQueue
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    JournalEntry,
    JournalKind,
    MindIdentity,
)
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.naming import NamingChoiceRequired, naming_assessment
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMindStore


async def speech_context(experiences, *, complete=False):
    mind = InMemoryMindStore()
    await mind.initialize(CognitiveMind(identity=MindIdentity(
        self_name="Aster" if complete else None,
        pronouns="he/him" if complete else None,
    )))
    journal = InMemoryJournalStore()
    for index in range(experiences):
        await journal.append(
            JournalEntry(kind=JournalKind.INTERACTION, experience={"interaction": index}),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
    mouth = BrowserVoiceOutput()
    return SimpleNamespace(
        mind_store=mind,
        journal_store=journal,
        body=BodyRuntime(voice=mouth),
        mouth=mouth,
        runtime_records=RuntimeRecords(mind),
        runtime_settings=SimpleNamespace(
            fish_audio_api_key="synthetic-key",
            fish_audio_model="synthetic-model",
            fish_audio_reference_id=None,
        ),
        voice_settings=SimpleNamespace(read=AsyncMock(return_value={})),
    )


def speech_app(context):
    app = FastAPI()
    for name, value in vars(context).items():
        setattr(app.state, name, value)
    app.add_exception_handler(NamingChoiceRequired, api.naming_choice_required_handler)
    app.add_api_route("/v1/body/mouth/speak", api.speak_through_mouth, methods=["POST"])
    app.add_api_route("/v1/body/mouth/next", api.next_mouth_intent, methods=["GET"])
    app.add_api_route("/v1/body/speech/fish-audio", api.fish_audio_speech, methods=["POST"])
    app.add_api_route("/v1/mind/interactions", api.interact, methods=["POST"])
    return app


class ApiNamingOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_required_incomplete_identity_blocks_voice_queue_and_audio_generation(self):
        context = await speech_context(2000)
        app = speech_app(context)
        dispatcher = SimpleNamespace(
            is_configured=AsyncMock(return_value=True),
            execute=AsyncMock(return_value=b"synthetic-audio"),
        )
        with (
            patch("aicognitive_mind.api.TaskModelDispatcher", return_value=dispatcher) as factory,
            patch("aicognitive_mind.api.FishAudioRenderer") as renderer,
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://naming.test"
            ) as client:
                for path in ("/v1/body/mouth/speak", "/v1/body/speech/fish-audio"):
                    response = await client.post(path, json={"text": "Do not deliver yet."})
                    self.assertEqual(response.status_code, 409, response.text)
                    detail = response.json()["detail"]
                    self.assertEqual(detail["code"], "naming_choice_required")
                    self.assertEqual(detail["status"], "naming_choice_required")
                    self.assertEqual(detail["naming"]["experience_count"], 2000)
                    self.assertFalse(detail["presentation"]["allowed"])
                    self.assertFalse(detail["presentation"]["report_persistence_error"])
                    self.assertTrue(detail["recoverable"])
        self.assertIsNone(context.mouth.consume())
        context.voice_settings.read.assert_not_awaited()
        factory.assert_not_called()
        dispatcher.execute.assert_not_awaited()
        renderer.assert_not_called()

    async def test_below_threshold_or_complete_identity_can_queue_and_generate_voice(self):
        for experiences, complete in ((1999, False), (2000, True)):
            with self.subTest(experiences=experiences, complete=complete):
                context = await speech_context(experiences, complete=complete)
                app = speech_app(context)
                dispatcher = SimpleNamespace(
                    is_configured=AsyncMock(return_value=True),
                    execute=AsyncMock(return_value=b"synthetic-audio"),
                )
                with patch("aicognitive_mind.api.TaskModelDispatcher", return_value=dispatcher):
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app), base_url="http://naming.test"
                    ) as client:
                        queued = await client.post(
                            "/v1/body/mouth/speak", json={"text": "Allowed voice."}
                        )
                        self.assertEqual(queued.status_code, 200, queued.text)
                        generated = await client.post(
                            "/v1/body/speech/fish-audio", json={"text": "Allowed voice."}
                        )
                        self.assertEqual(generated.status_code, 200, generated.text)
                        self.assertEqual(generated.content, b"synthetic-audio")
                self.assertEqual(context.mouth.consume().text, "Allowed voice.")
                dispatcher.execute.assert_awaited_once()

    async def test_core_naming_condition_maps_to_recoverable_http_conflict(self):
        context = await speech_context(1999)
        mind = await context.mind_store.load()
        assessment = await naming_assessment(mind, context.journal_store)
        condition = NamingChoiceRequired(assessment, projected_count=2000)
        context.core = SimpleNamespace(interact=AsyncMock(side_effect=condition))
        app = speech_app(context)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://naming.test"
        ) as client:
            response = await client.post("/v1/mind/interactions", json={"message": "Continue."})
        self.assertEqual(response.status_code, 409, response.text)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "naming_choice_required")
        self.assertEqual(detail["naming"]["projected_count"], 2000)
        self.assertTrue(detail["recoverable"])

    async def test_audio_delivery_rechecks_history_after_provider_finishes(self):
        for configured in (True, False):
            with self.subTest(configured=configured):
                context = await speech_context(1999)
                audio = b"undelivered-synthetic-audio"

                async def synthesize_then_cross_threshold(
                    *args, output_context=context, payload=audio, **kwargs
                ):
                    await output_context.journal_store.append(
                        JournalEntry(
                            kind=JournalKind.INTERACTION,
                            experience={"threshold_reached_during_synthesis": True},
                        ),
                        recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                    )
                    return payload

                dispatcher = SimpleNamespace(
                    is_configured=AsyncMock(return_value=configured),
                    execute=AsyncMock(side_effect=synthesize_then_cross_threshold),
                )
                renderer = SimpleNamespace(
                    synthesize=AsyncMock(side_effect=synthesize_then_cross_threshold)
                )
                app = speech_app(context)
                with (
                    patch("aicognitive_mind.api.TaskModelDispatcher", return_value=dispatcher),
                    patch("aicognitive_mind.api.FishAudioRenderer", return_value=renderer),
                ):
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app), base_url="http://naming.test"
                    ) as client:
                        response = await client.post(
                            "/v1/body/speech/fish-audio", json={"text": "Check before delivery."}
                        )

                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(response.json()["detail"]["code"], "naming_choice_required")
                self.assertEqual(response.json()["detail"]["naming"]["experience_count"], 2000)
                self.assertNotIn(audio, response.content)
                self.assertTrue(response.headers["content-type"].startswith("application/json"))
                if configured:
                    dispatcher.execute.assert_awaited_once()
                    renderer.synthesize.assert_not_awaited()
                else:
                    dispatcher.execute.assert_not_awaited()
                    renderer.synthesize.assert_awaited_once()

    async def test_legacy_queued_voice_survives_required_choice_then_is_consumed_once(self):
        context = await speech_context(1999)
        queue = BodyQueue(context.runtime_records, "mouth", BrowserVoiceOutput())
        context.browser_mouth = queue
        context.body = BodyRuntime(voice=queue)
        app = speech_app(context)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://naming.test"
        ) as client:
            queued = await client.post(
                "/v1/body/mouth/speak", json={"text": "Retain this queued voice."}
            )
            self.assertEqual(queued.status_code, 200, queued.text)
            original_intent, original_receipt = await queue.deliver()
            self.assertIsNotNone(original_receipt)
            await context.journal_store.append(
                JournalEntry(kind=JournalKind.INTERACTION, experience={"threshold_reached": True}),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )

            blocked = await client.get("/v1/body/mouth/next")

            self.assertEqual(blocked.status_code, 409, blocked.text)
            self.assertEqual(await queue.deliver(), (original_intent, original_receipt))
            tool = GovernanceStewardTool(
                mind=context.mind_store,
                journal=context.journal_store,
                input_text="Continue our conversation.",
            )
            chosen = await tool.invoke({
                "action": "propose_self_name", "candidate_name": "Aster",
                "candidate_pronouns": "he/him", "rationale": "Making the required first choice.",
            })
            self.assertTrue(chosen["accepted"])

            delivered = await client.get("/v1/body/mouth/next")

            self.assertEqual(delivered.status_code, 200, delivered.text)
            self.assertEqual(delivered.json()["text"], "Retain this queued voice.")
            self.assertIsNone((await client.get("/v1/body/mouth/next")).json())


if __name__ == "__main__":
    unittest.main()
