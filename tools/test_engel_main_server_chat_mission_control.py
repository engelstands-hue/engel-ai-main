"""Unit tests for the Engel Main server chat service:
  1. Mission Control trigger only fires on explicit imperative create intent
     (status/read questions must NOT spawn a durable job).
  2. Mission Control in-flight guard coalesces duplicate/retry prompts.
  3. Persistent-memory fallback appends exactly once (never double-writes when
     an earlier route already saved the turn).

Run:  python tools/test_engel_main_server_chat_mission_control.py
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engel_main_server_chat_http_service as svc  # noqa: E402


class MissionControlTriggerTests(unittest.TestCase):
    def test_imperative_create_prompts_trigger(self):
        for prompt in (
            "Engel, create a Mission Control job: make a worker heartbeat proof "
            "artifact named ui_mission_control_demo, verify it, and tell me the "
            "final receipt path.",
            "create a mission control job to make a heartbeat proof",
            "run the mission control job",
            "please make a mission control job now",
        ):
            self.assertTrue(
                svc._prompt_requests_mission_control_job(prompt),
                f"expected create-intent prompt to trigger: {prompt!r}",
            )

    def test_status_and_read_questions_do_not_trigger(self):
        # These previously spawned real jobs (the over-eager bug).
        for prompt in (
            "did the mission control heartbeat receipt pass?",
            "what's the final receipt path?",
            "show me the heartbeat proof",
            "durable job",
            "engel-control status please",
            "what is the status of the mission control job?",
            "is the mission control artifact done yet",
        ):
            self.assertFalse(
                svc._prompt_requests_mission_control_job(prompt),
                f"status/read prompt must NOT spawn a job: {prompt!r}",
            )

    def test_meta_questions_with_a_create_verb_do_not_trigger(self):
        # A create verb inside a QUESTION must not spawn a real job (the residual
        # gap: create-verb-anywhere matched interrogatives/past tense/how-to).
        for prompt in (
            "why did you create a mission control job?",
            "did you create the mission control job?",
            "how do I create a mission control job?",
            "what happens when I create a mission control job?",
            "can you show me how to build a mission control job?",
            "what is the status of the mission control job you were told to create?",
        ):
            self.assertFalse(
                svc._prompt_requests_mission_control_job(prompt),
                f"meta-question with a create verb must NOT spawn a job: {prompt!r}",
            )

    def test_imperative_after_preamble_or_politeness_triggers(self):
        for prompt in (
            "I need a heartbeat proof. Create a mission control job named demo.",
            "can you create a mission control job named demo",
            "go ahead and make a mission control job",
        ):
            self.assertTrue(
                svc._prompt_requests_mission_control_job(prompt),
                f"imperative create should trigger: {prompt!r}",
            )

    def test_forbidden_storage_never_triggers(self):
        for prompt in (
            "create a mission control job on ct245",
            "make a mission control job in the offline CT245 vault",
            "run a mission control job on the offline CT245 vault",
        ):
            self.assertFalse(svc._prompt_requests_mission_control_job(prompt))


class MissionControlIdempotencyTests(unittest.TestCase):
    def setUp(self):
        with svc._MISSION_CONTROL_GUARD:
            svc._MISSION_CONTROL_INFLIGHT.clear()

    def test_claim_release_cycle(self):
        self.assertIsNone(svc._claim_mission_control_job("hashA"))          # granted
        again = svc._claim_mission_control_job("hashA")                     # duplicate
        self.assertIsNotNone(again)
        self.assertGreaterEqual(again, 0.0)
        svc._release_mission_control_job("hashA")
        self.assertIsNone(svc._claim_mission_control_job("hashA"))          # granted after release
        svc._release_mission_control_job("hashA")

    def test_distinct_prompts_are_independent(self):
        self.assertIsNone(svc._claim_mission_control_job("hashA"))
        self.assertIsNone(svc._claim_mission_control_job("hashB"))
        svc._release_mission_control_job("hashA")
        svc._release_mission_control_job("hashB")

    def test_stale_claim_expires(self):
        with svc._MISSION_CONTROL_GUARD:
            svc._MISSION_CONTROL_INFLIGHT["stale"] = (
                time.monotonic() - svc._MISSION_CONTROL_INFLIGHT_TTL_SECONDS - 10
            )
        # Claiming any key sweeps expired entries, so the stale key is released.
        self.assertIsNone(svc._claim_mission_control_job("fresh"))
        with svc._MISSION_CONTROL_GUARD:
            self.assertNotIn("stale", svc._MISSION_CONTROL_INFLIGHT)
        svc._release_mission_control_job("fresh")


class PersistentMemoryFallbackTests(unittest.TestCase):
    def setUp(self):
        self._orig = svc._append_final_chat_memory
        self.calls = []

        def _fake(prompt, reply, receipt, source):
            self.calls.append((prompt, reply, source))
            return True, ""

        svc._append_final_chat_memory = _fake

    def tearDown(self):
        svc._append_final_chat_memory = self._orig

    def test_appends_once_when_no_earlier_route(self):
        receipt = {}
        out = svc._ensure_final_chat_memory(receipt, "hi", "hello", "desktop_chat")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(out["persistent_chat_memory_appended"])

    def test_skips_when_earlier_route_already_appended(self):
        receipt = {"persistent_chat_memory_appended": True}
        svc._ensure_final_chat_memory(receipt, "hi", "hello", "desktop_chat")
        self.assertEqual(len(self.calls), 0, "must not double-write when a route already saved")

    def test_records_error_from_append(self):
        def _fail(prompt, reply, receipt, source):
            return False, "disk full"

        svc._append_final_chat_memory = _fail
        receipt = {}
        out = svc._ensure_final_chat_memory(receipt, "hi", "hello", "desktop_chat")
        self.assertFalse(out["persistent_chat_memory_appended"])
        self.assertEqual(out["persistent_chat_memory_error"], "disk full")


if __name__ == "__main__":
    unittest.main(verbosity=2)
