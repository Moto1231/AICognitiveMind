import unittest

from aicognitive_mind.body import (
    BodyRuntime,
    DeviceStatus,
    ExpressionIntent,
    ExpressionModality,
    Percept,
    SensoryModality,
)


class FakeVision:
    async def status(self) -> DeviceStatus:
        return DeviceStatus(device="eyes", available=True)

    async def observe(self) -> Percept:
        return Percept(
            modality=SensoryModality.VISION,
            source="test-camera",
            summary="A person is standing in front of the camera.",
        )


class FakeAudio:
    async def status(self) -> DeviceStatus:
        return DeviceStatus(device="ears", available=True)

    async def listen(self) -> Percept:
        return Percept(
            modality=SensoryModality.AUDIO,
            source="test-microphone",
            summary="Hello Mind.",
        )


class FakeVoice:
    def __init__(self) -> None:
        self.intents: list[ExpressionIntent] = []

    async def status(self) -> DeviceStatus:
        return DeviceStatus(device="mouth", available=True)

    async def speak(self, intent: ExpressionIntent) -> None:
        self.intents.append(intent)


class FakeAvatar:
    def __init__(self) -> None:
        self.intents: list[ExpressionIntent] = []

    async def status(self) -> DeviceStatus:
        return DeviceStatus(device="face", available=True)

    async def render(self, intent: ExpressionIntent) -> None:
        self.intents.append(intent)


class BodyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_body_reports_attached_faculties(self) -> None:
        runtime = BodyRuntime(
            vision=FakeVision(),
            audio=FakeAudio(),
            voice=FakeVoice(),
            avatar=FakeAvatar(),
        )

        statuses = await runtime.status()

        self.assertEqual(
            [(status.device, status.available) for status in statuses],
            [
                ("eyes", True),
                ("ears", True),
                ("mouth", True),
                ("face", True),
            ],
        )

    async def test_body_see_and_hear_return_transient_percepts(self) -> None:
        runtime = BodyRuntime(
            vision=FakeVision(),
            audio=FakeAudio(),
        )

        seen = await runtime.see()
        heard = await runtime.hear()

        self.assertEqual(seen.modality, SensoryModality.VISION)
        self.assertEqual(seen.source, "test-camera")
        self.assertEqual(
            seen.summary,
            "A person is standing in front of the camera.",
        )
        self.assertEqual(heard.modality, SensoryModality.AUDIO)
        self.assertEqual(heard.source, "test-microphone")
        self.assertEqual(heard.summary, "Hello Mind.")

    async def test_body_accepts_full_voice_intent(self) -> None:
        voice = FakeVoice()
        runtime = BodyRuntime(voice=voice)
        intent = ExpressionIntent(
            modality=ExpressionModality.VOICE,
            text="Hello.",
            metadata={"rate": 0.9},
        )

        await runtime.speak_intent(intent)

        self.assertEqual(voice.intents, [intent])

    async def test_body_expression_drives_mouth_and_face(self) -> None:
        voice = FakeVoice()
        avatar = FakeAvatar()
        runtime = BodyRuntime(voice=voice, avatar=avatar)

        await runtime.express("Good morning.")

        self.assertEqual(len(voice.intents), 1)
        self.assertEqual(voice.intents[0].modality, ExpressionModality.VOICE)
        self.assertEqual(voice.intents[0].text, "Good morning.")
        self.assertEqual(len(avatar.intents), 1)
        self.assertEqual(avatar.intents[0].modality, ExpressionModality.AVATAR)
        self.assertEqual(avatar.intents[0].text, "Good morning.")

    async def test_missing_faculty_fails_explicitly(self) -> None:
        runtime = BodyRuntime()

        with self.assertRaisesRegex(RuntimeError, "No eyes are attached"):
            await runtime.see()
        with self.assertRaisesRegex(RuntimeError, "No ears are attached"):
            await runtime.hear()
        with self.assertRaisesRegex(RuntimeError, "No mouth is attached"):
            await runtime.speak("Hello")
        with self.assertRaisesRegex(RuntimeError, "No face is attached"):
            await runtime.present("Hello")

    def test_percept_contains_no_durable_memory_authority(self) -> None:
        percept = Percept(
            modality=SensoryModality.VISION,
            source="test-camera",
            summary="Transient observation.",
        )

        self.assertNotIn("memory", percept.model_fields)
        self.assertNotIn("belief", percept.model_fields)
        self.assertNotIn("identity", percept.model_fields)


if __name__ == "__main__":
    unittest.main()
