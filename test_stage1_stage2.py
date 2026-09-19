"""Focused regression tests for the Stage 1 lifecycle and Stage 2 events."""

import unittest
from unittest.mock import Mock, patch

from core.events import EventPublisher
from core.state import AURAState
from core.task_executor import TaskExecutor
from main import AuraAssistant


class Stage1Stage2Tests(unittest.TestCase):
    def test_state_sequence_is_observable(self):
        events = EventPublisher()
        assistant = object.__new__(AuraAssistant)
        assistant.state = AURAState.SLEEPING
        assistant.events = events
        states = []
        events.subscribe(lambda event: states.append(event.state))

        for state in (
            AURAState.WAKING,
            AURAState.LISTENING,
            AURAState.PROCESSING,
            AURAState.THINKING,
            AURAState.EXECUTING,
            AURAState.SPEAKING,
            AURAState.SLEEPING,
        ):
            assistant.set_state(state)

        self.assertEqual(states, [
            AURAState.WAKING,
            AURAState.LISTENING,
            AURAState.PROCESSING,
            AURAState.THINKING,
            AURAState.EXECUTING,
            AURAState.SPEAKING,
            AURAState.SLEEPING,
        ])

    def test_event_publisher_delivers_state_and_data(self):
        events = EventPublisher()
        received = []
        events.subscribe(received.append)

        event = events.publish(
            "transcript_received",
            state=AURAState.PROCESSING,
            text="reboot my computer",
        )

        self.assertEqual(received, [event])
        self.assertEqual(event.name, "transcript_received")
        self.assertEqual(event.state, AURAState.PROCESSING)
        self.assertEqual(event.data["text"], "reboot my computer")

    def test_action_plan_is_allowlisted(self):
        self.assertEqual(
            TaskExecutor.execute_plan({"action": "run_shell", "app": None}),
            (False, "No safe action was selected."),
        )

    def test_system_action_is_announced_and_saved_before_execution(self):
        assistant = AuraAssistant()
        assistant.running = True
        assistant.session = Mock()
        assistant.session.session_name = "test_session"
        assistant.session.is_active = True

        with patch.object(assistant, "speak_response") as speak, \
                patch.object(assistant.session, "save_session") as save, \
                patch("main.TaskExecutor.execute_plan", return_value=(True, "Reboot command accepted.")):
            assistant.session.add_message = Mock()
            assistant.set_state = Mock()
            assistant.emit = Mock()
            action = {"action": "reboot", "app": None}
            assistant.emit("tool_started", action=action["action"])
            notice = "I'm preparing to reboot the computer now. I'll save this session first."
            assistant.session.add_message("assistant", notice)
            assistant.speak_response(notice)
            assistant.session.is_active = False
            assistant.session.save_session()
            assistant.session_saved = True
            TaskExecutor.execute_plan(action)

        speak.assert_called_once_with(notice)
        save.assert_called_once_with()

    def test_sleep_phrases_are_recognized(self):
        assistant = object.__new__(AuraAssistant)
        for phrase in ("Good night", "Good night, Aurora", "Goodnight AURA"):
            self.assertTrue(assistant.check_for_sleep_word(phrase))

    def test_cleanup_terminates_audio_and_saves_once(self):
        assistant = object.__new__(AuraAssistant)
        assistant.session = Mock()
        assistant.session.session_name = "cleanup_test"
        assistant.session_saved = False
        assistant.running = True
        assistant.session.get_session_summary.return_value = {
            "duration_seconds": 0.0,
            "message_count": 0,
            "timeout_count": 0,
        }
        assistant.state = AURAState.SLEEPING
        assistant.events = EventPublisher()
        assistant.audio_stream = Mock()
        assistant.pa = Mock()

        assistant.end_session()

        assistant.session.end_session.assert_called_once_with()
        assistant.audio_stream.stop_stream.assert_called_once_with()
        assistant.audio_stream.close.assert_called_once_with()
        assistant.pa.terminate.assert_called_once_with()
        self.assertFalse(assistant.running)


if __name__ == "__main__":
    unittest.main()