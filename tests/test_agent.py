"""Offline tests for the agent loop, tools and memory (no Ollama, mic or TTS)."""

import tempfile
import unittest
from pathlib import Path

from core.agent import Agent, speakable
from core.events import EventPublisher
from core.memory import LongTermMemory, SessionLog
from core.state import AURAState
from core.tools import CONFIRM, Tool, ToolRegistry, find_app


class FakeClient:
    """Replays scripted model turns. Each turn: (text, [tool_calls])."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen = []

    def chat_stream(self, messages, tools=None):
        self.seen.append([dict(m) for m in messages])
        text, calls = self.turns.pop(0)
        for word in text.split(" "):
            yield {"content": word + " ", "tool_calls": [], "done": False}
        yield {"content": "", "tool_calls": calls, "done": True}


def call(tool_name, **args):
    return {"function": {"name": tool_name, "arguments": args}}


def make_agent(turns, tools=None):
    tools = tools or ToolRegistry()
    mem = LongTermMemory(Path(tempfile.mkdtemp()) / "m.json")
    return Agent(client=FakeClient(turns), tools=tools, memory=mem)


class AgentTests(unittest.TestCase):
    def test_plain_reply_streams_sentences(self):
        agent = make_agent([("Hello there. How are you?", [])])
        spoken = []
        reply = agent.respond("hi", on_sentence=spoken.append)
        self.assertEqual(spoken, ["Hello there.", "How are you?"])
        self.assertEqual(reply, "Hello there. How are you?")

    def test_tool_call_runs_and_result_goes_back(self):
        tools = ToolRegistry()
        ran = []
        tools.register(Tool("open_app", "open", lambda name: ran.append(name) or f"Launched {name}.",
                            {"name": {"type": "string"}}))
        agent = make_agent([("", [call("open_app", name="firefox")]), ("Firefox is up.", [])], tools)
        reply = agent.respond("open mozilla")
        self.assertEqual(ran, ["firefox"])
        self.assertEqual(reply, "Firefox is up.")
        tool_msgs = [m for m in agent.history if m["role"] == "tool"]
        self.assertEqual(tool_msgs[0]["content"], "Launched firefox.")

    def test_dangerous_tool_waits_for_yes(self):
        tools = ToolRegistry()
        ran = []
        tools.register(Tool("power", "power", lambda action: ran.append(action) or "Shutdown started.",
                            {"action": {"type": "string"}}, risk=CONFIRM))
        agent = make_agent([("Sure, shutting down!", [call("power", action="shutdown")])], tools)
        reply = agent.respond("shut it down")
        self.assertEqual(ran, [])
        self.assertIn("Just to be sure", reply)
        agent.respond("yes please")
        self.assertEqual(ran, ["shutdown"])

    def test_dangerous_tool_cancelled_by_no(self):
        tools = ToolRegistry()
        ran = []
        tools.register(Tool("power", "power", lambda action: ran.append(action) or "started",
                            {"action": {"type": "string"}}, risk=CONFIRM))
        agent = make_agent([("", [call("power", action="reboot")])], tools)
        agent.respond("reboot")
        self.assertEqual(agent.respond("no, wait"), "Okay, I won't.")
        self.assertEqual(ran, [])

    def test_unknown_tool_and_crashing_tool_do_not_raise(self):
        tools = ToolRegistry()
        tools.register(Tool("boom", "x", lambda: 1 / 0))
        agent = make_agent([("", [call("boom"), call("nope")]), ("That failed.", [])], tools)
        self.assertEqual(agent.respond("go"), "That failed.")
        results = [m["content"] for m in agent.history if m["role"] == "tool"]
        self.assertTrue(results[0].startswith("Error running boom"))
        self.assertIn("no tool named nope", results[1])

    def test_end_conversation_sets_flag(self):
        agent = make_agent([("Good night!", [call("end_conversation")]), ("", [])])
        agent.respond("good night aura")
        self.assertTrue(agent.end_requested)

    def test_tool_rounds_are_capped(self):
        tools = ToolRegistry()
        tools.register(Tool("loop", "x", lambda: "again"))
        agent = make_agent([("", [call("loop")])] * 10, tools)
        agent.respond("go")
        self.assertLessEqual(len([m for m in agent.history if m["role"] == "tool"]), 6)

    def test_memory_appears_in_system_prompt(self):
        agent = make_agent([("Ada.", [])])
        agent.memory.add("The user's sister is Ada")
        agent.respond("who is my sister")
        system = agent.client.seen[0][0]["content"]
        self.assertIn("sister is Ada", system)

    def test_speakable_strips_markdown(self):
        self.assertEqual(speakable("**Hi** there 😀 see https://x.com"), "Hi there see")


class ToolAndMemoryTests(unittest.TestCase):
    def test_aliases_resolve_to_installed_apps(self):
        app = find_app("console")
        if app is None:
            self.skipTest("Konsole not installed")
        self.assertEqual(app.process_name, "konsole")

    def test_memory_add_dedupe_forget(self):
        mem = LongTermMemory(Path(tempfile.mkdtemp()) / "m.json")
        mem.add("Likes jazz")
        self.assertEqual(mem.add("likes jazz"), "I already knew that.")
        self.assertEqual(LongTermMemory(mem.path).facts[0]["fact"], "Likes jazz")
        mem.forget("jazz")
        self.assertEqual(mem.facts, [])

    def test_session_saved_once(self):
        log = SessionLog(Path(tempfile.mkdtemp()))
        log.add("user", "hi")
        log.save()
        log.path.unlink()
        log.save()
        self.assertFalse(log.path.exists())


class EventTests(unittest.TestCase):
    def test_states_are_observable(self):
        from main import AuraAssistant
        events = EventPublisher()
        seen = []
        events.subscribe(lambda e: seen.append(e.state))
        assistant = AuraAssistant(events)
        for state in (AURAState.LISTENING, AURAState.THINKING, AURAState.SPEAKING):
            assistant.set_state(state)
        self.assertEqual(seen, [AURAState.LISTENING, AURAState.THINKING, AURAState.SPEAKING])


if __name__ == "__main__":
    unittest.main()


class ConfirmationSafetyTests(unittest.TestCase):
    def _agent(self, ran):
        tools = ToolRegistry()
        tools.register(Tool("power", "power", lambda action: ran.append(action) or "Shutdown started.",
                            {"action": {"type": "string"}}, risk=CONFIRM))
        return make_agent([("Sure, shutting down!", [call("power", action="shutdown")]),
                           ("It's noon.", [])], tools)

    def test_yes_buried_in_a_question_does_not_confirm(self):
        ran = []
        agent = self._agent(ran)
        agent.respond("shut down")
        agent.respond("ok what time is it first and then tell me the weather")
        self.assertEqual(ran, [])

    def test_stale_yes_does_not_confirm(self):
        import core.agent as agent_module
        ran = []
        agent = self._agent(ran)
        agent.respond("shut down")
        agent.pending = agent.pending[:2] + (agent.pending[2] - agent_module.CONFIRM_TIMEOUT - 1,)
        agent.respond("yes")
        self.assertEqual(ran, [])

    def test_model_text_in_confirm_round_is_not_spoken(self):
        ran = []
        agent = self._agent(ran)
        spoken = []
        agent.respond("shut down", on_sentence=spoken.append)
        self.assertEqual(len(spoken), 1)
        self.assertTrue(spoken[0].startswith("Just to be sure"))

    def test_generic_exec_names_are_never_killable(self):
        from core.tools import DesktopApp
        self.assertEqual(DesktopApp("x", "X", "env FOO=1 sh -c thing").process_name, "")
        self.assertEqual(DesktopApp("x", "X", "env GDK=1 /usr/bin/gimp %U").process_name, "gimp")
        self.assertEqual(DesktopApp("x", "X", "python3 -m foo").process_name, "")


class FarewellTests(unittest.TestCase):
    def test_goodnight_ends_without_the_model(self):
        agent = make_agent([])          # any model call would raise IndexError
        for phrase in ("Good night Aura", "thanks, that's all", "goodbye", "go to sleep"):
            agent.respond(phrase)
            self.assertTrue(agent.end_requested, phrase)

    def test_long_sentence_with_bye_is_not_a_farewell(self):
        agent = make_agent([("Sure.", [])])
        agent.respond("can you tell me how to say bye in french and spanish and also german please")
        self.assertFalse(agent.end_requested)

    def test_leaked_tool_name_not_spoken(self):
        self.assertEqual(speakable("Good night to you too! endconversation"), "Good night to you too!")
