import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QCoreApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from services.ai_manager import AIChatManager
from services.audiogenerate import VocuAudioGenerator
from services.audio_player import NetworkStreamPlayer
from services.workers import split_initial_tts_segment, split_next_tts_segment
from services.workers import ChatWorker


class ModelAdapterTests(unittest.TestCase):
    def test_preconnected_stream_waits_for_explicit_activation(self):
        device_created = threading.Event()

        class FakeResponse:
            @staticmethod
            def raise_for_status():
                pass

            @staticmethod
            def iter_content(chunk_size):
                del chunk_size
                return iter([b"fake-mp3-data"])

            @staticmethod
            def close():
                pass

        class FakeSession:
            @staticmethod
            def get(*_args, **_kwargs):
                return FakeResponse()

        class FakeStreamableSource:
            pass

        def fake_stream_any(*_args, **_kwargs):
            requested = yield b"first-frame"
            del requested
            yield b"last-frame"

        class FakePlaybackDevice:
            def __init__(self, **_kwargs):
                device_created.set()

            @staticmethod
            def start(callback):
                try:
                    while True:
                        callback.send(1024)
                except StopIteration:
                    pass

            @staticmethod
            def stop():
                pass

        fake_miniaudio = types.SimpleNamespace(
            StreamableSource=FakeStreamableSource,
            FileFormat=types.SimpleNamespace(MP3="mp3"),
            SampleFormat=types.SimpleNamespace(SIGNED16="signed16"),
            PlaybackDevice=FakePlaybackDevice,
            stream_any=fake_stream_any,
        )
        player = NetworkStreamPlayer(
            "https://stream.example/audio.mp3",
            session=FakeSession(),
            start_paused=True,
        )
        with patch.dict(sys.modules, {"miniaudio": fake_miniaudio}):
            runner = threading.Thread(target=player.run, daemon=True)
            runner.start()
            try:
                self.assertTrue(player._prepared_event.wait(1))
                self.assertFalse(device_created.wait(0.05))
                player.activate()
                self.assertTrue(device_created.wait(1))
                runner.join(1)
            finally:
                player.stop()

        self.assertFalse(runner.is_alive())

    def test_responses_conversion_uses_output_text_for_assistant(self):
        instructions, items = AIChatManager._to_responses_input(
            "system",
            [
                {"role": "system", "content": "memory"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "image"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
                    ],
                },
            ],
        )
        self.assertIn("memory", instructions)
        self.assertEqual(items[0]["content"][0]["type"], "input_text")
        self.assertEqual(items[1]["content"][0]["type"], "output_text")
        self.assertEqual(items[2]["content"][1]["type"], "input_image")

    def test_realtime_audio_is_preferred_without_enabling_async_mode(self):
        generator = object.__new__(VocuAudioGenerator)
        calls = []
        generator._simple_generate = lambda *args, **kwargs: calls.append(("simple", kwargs)) or {
            "data": {"streamUrl": "https://stream.example/audio.mp3"}
        }
        generator._extract_simple_audio_url = VocuAudioGenerator._extract_simple_audio_url.__get__(generator)
        generator._create_task = lambda *args, **kwargs: calls.append(("task", kwargs))

        result = generator.generate_audio(
            "こんにちは",
            "market:test",
            async_mode=False,
            realtime_mode=True,
        )
        self.assertEqual(result, "https://stream.example/audio.mp3")
        self.assertEqual([call[0] for call in calls], ["simple"])

    def test_tts_splits_first_natural_sentence_from_remainder(self):
        head, remainder = split_initial_tts_segment(
            "[happy]こんばんは。今日もお疲れさまね。"
        )
        self.assertEqual(head, "こんばんは。")
        self.assertEqual(remainder, "今日もお疲れさまね。")

    def test_tts_does_not_split_short_unfinished_clause(self):
        head, remainder = split_initial_tts_segment("[normal]それは興味深い")
        self.assertEqual(head, "")
        self.assertEqual(remainder, "それは興味深い")

    def test_tts_limits_a_long_unpunctuated_segment(self):
        head, remainder = split_next_tts_segment("あ" * 40, max_chars=32)
        self.assertEqual(head, "あ" * 32)
        self.assertEqual(remainder, "あ" * 8)

    def test_audio_worker_supports_many_segments_with_bounded_parallel_order(self):
        app = QCoreApplication.instance() or QCoreApplication([])

        class FakeAI:
            BILINGUAL_GENERATION_PROMPT = "prompt"

            @staticmethod
            def append_message(*_args):
                pass

            @staticmethod
            def context_messages():
                return []

            @staticmethod
            def stream_text(*_args, **_kwargs):
                return iter([
                    "[happy]こんばんは。",
                    "今日は調子がいいわ。",
                    "処理も順調よ。",
                    "もう心配はいらないわ。|晚",
                    "上好，系统运行正常。",
                ])

            @staticmethod
            def _translate_to_japanese(_text):
                return ""

            @staticmethod
            def _translate_to_chinese(_text):
                return ""

            @staticmethod
            def schedule_memory_compaction():
                pass

            @staticmethod
            def schedule_fact_extraction(_text):
                pass

        class FakeAudioGenerator:
            def __init__(self):
                self.lock = threading.Lock()
                self.active = 0
                self.peak_active = 0
                self.calls = []

            def generate_audio(self, **kwargs):
                text = kwargs["text"]
                with self.lock:
                    self.active += 1
                    self.peak_active = max(self.peak_active, self.active)
                    self.calls.append(kwargs)
                delays = {
                    "こんばんは。": 0.05,
                    "今日は調子がいいわ。": 0.005,
                    "処理も順調よ。": 0.03,
                    "もう心配はいらないわ。": 0.001,
                }
                try:
                    time.sleep(delays[text])
                    return f"segment-{list(delays).index(text) + 1}"
                finally:
                    with self.lock:
                        self.active -= 1

        audio_generator = FakeAudioGenerator()

        worker = ChatWorker(
            FakeAI(),
            "hello",
            audio_generator=audio_generator,
            voice_id="voice",
            enable_audio=True,
            max_tokens=100,
        )
        text_chunks = []
        audio_sources = []
        worker.chunk_ready.connect(text_chunks.append)
        worker.audio_ready.connect(audio_sources.append)

        worker.run()
        deadline = time.monotonic() + 2
        while len(audio_sources) < 4 and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)

        self.assertEqual("".join(text_chunks), "晚上好，系统运行正常。")
        self.assertEqual(audio_sources, ["segment-1", "segment-2", "segment-3", "segment-4"])
        self.assertLessEqual(audio_generator.peak_active, 2)
        self.assertTrue(all(not call["async_mode"] for call in audio_generator.calls))


if __name__ == "__main__":
    unittest.main()
