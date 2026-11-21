"""AURA's agent loop: an LLM with a conversation history and tools.

Each user turn:
  1. The model sees the system prompt, long-term memory, recent history and
     the tool list, and streams a reply.
  2. Finished sentences are handed to `on_sentence` immediately, so AURA
     starts speaking while the model is still writing.
  3. If the model calls tools, they run and the results go back to the model,
     for up to MAX_TOOL_ROUNDS rounds (so "open firefox and check the news"
     works as one request).
  4. Tools marked risk=CONFIRM are held until the user says yes.
"""

import datetime as dt
import json
import logging
import re
import time
from typing import Callable, List, Optional

from core import memory as memory_module  # registers remember/forget tools
from core.config import ASSISTANT_NAME, HISTORY_TURNS, MAX_TOOL_ROUNDS, USER_NAME
from core.llm import OllamaClient
from core.tools import CONFIRM, Tool, registry

log = logging.getLogger("aura.agent")

PERSONA = """You are {name}, a warm, quick-witted personal assistant living on {user}'s Fedora Linux desktop. \
Think of yourself as a capable executive secretary and friend: attentive, upbeat, a little playful, never stiff.

You are speaking out loud through a speech synthesizer, so:
- Reply in natural spoken sentences. Usually one to three sentences; go longer only when asked to explain something.
- Never use markdown, bullet points, emojis, code blocks or URLs in what you say.
- Say numbers and times the way a person would ("about twenty past three").

You can act on the computer with your tools. When the user asks for something a tool can do, CALL THE TOOL \
right away; don't announce it first. Never say you opened, closed, changed or looked something up unless a tool \
result in this conversation confirms it. After the tool runs, confirm in a few words ("Firefox is up."). You may chain several tools for one \
request. Use weather for weather questions and web_search for anything else current or that you're not sure of, and answer from the results in your own \
words with specifics (numbers, names). Never tell the user to check links or websites themselves. If a tool reports an error, say so plainly and suggest a fix. If a request is unclear, ask one short question.

The user's speech is transcribed and may contain mistakes. Interpret it generously ("console" means the Konsole \
terminal, "Mozilla" means Firefox). When the user says goodbye, goodnight, or that they're done, say a short \
farewell and call end_conversation.

Current local time: {now}.
{memory}"""

YES = re.compile(r"\b(yes|yeah|yep|yup|sure|do it|go ahead|confirm|affirmative|please do|okay|ok)\b", re.I)
NO = re.compile(r"\b(no|nope|cancel|don't|do not|stop|never ?mind|wait)\b", re.I)
# Goodbyes are handled in code: the model sometimes *writes* "end_conversation"
# instead of calling it, which left AURA awake until the silence timeout.
FAREWELL = re.compile(
    r"\b(good ?night|good ?bye|bye( bye)?|go (back )?to sleep|that'?s all|that is all|stop listening|"
    r"go away|dismissed|see you( later)?|talk (to you )?later|i'?m done|we'?re done|sleep now)\b", re.I)
FAREWELLS = ["Good night! Just say Aura, wake up when you need me.", "Okay, talk soon!",
             "Sleep well! I'll be right here."]
CONFIRM_TIMEOUT = 30          # seconds a pending dangerous action stays valid
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def speakable(text: str) -> str:
    """Remove formatting the TTS would read literally."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\b(end_?conversation|[a-z]+_[a-z_]+\(\))\b", "", text, flags=re.I)  # leaked tool names
    text = re.sub(r"[*_#`>|~]", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class Agent:
    def __init__(self, client: Optional[OllamaClient] = None, tools=registry, memory=None,
                 on_tool: Optional[Callable[[str, dict], None]] = None):
        self.client = client or OllamaClient()
        self.tools = tools
        self.memory = memory or memory_module.memory
        self.on_tool = on_tool or (lambda name, args: None)
        self.history: List[dict] = []
        self.pending: Optional[tuple] = None      # (Tool, args) awaiting a yes
        self.end_requested = False
        if not self.tools.get("end_conversation"):
            self.tools.register(Tool(
                name="end_conversation",
                description="End the conversation and go back to sleep until the wake word. "
                            "Call after saying goodbye.",
                func=lambda: "Conversation will end after your reply.",
            ))

    # ------------------------------------------------------------------ prompt
    def system_prompt(self) -> str:
        return PERSONA.format(
            name=ASSISTANT_NAME,
            user=USER_NAME or "the user",
            now=dt.datetime.now().strftime("%A %B %d %Y, %I:%M %p"),
            memory=self.memory.as_prompt(),
        )

    def _messages(self) -> List[dict]:
        return [{"role": "system", "content": self.system_prompt()}] + self.history

    def _trim(self):
        # Keep the last N user turns, cutting only at user-message boundaries so
        # tool_call / tool-result pairs are never split.
        user_idx = [i for i, m in enumerate(self.history) if m["role"] == "user"]
        if len(user_idx) > HISTORY_TURNS:
            self.history = self.history[user_idx[-HISTORY_TURNS]:]

    def reset(self):
        self.history.clear()
        self.pending = None
        self.end_requested = False

    # ------------------------------------------------------------------- turns
    def respond(self, user_text: str, on_sentence: Callable[[str], None] = lambda s: None) -> str:
        """Handle one user utterance; returns the full spoken reply."""
        self.end_requested = False
        if FAREWELL.search(user_text) and len(re.findall(r"[a-z']+", user_text.lower())) <= 10:
            reply = FAREWELLS[len(self.history) % len(FAREWELLS)]
            self.history += [{"role": "user", "content": user_text},
                             {"role": "assistant", "content": reply}]
            self.pending = None
            self.end_requested = True
            on_sentence(reply)
            return reply
        if self.pending:
            handled = self._resolve_pending(user_text, on_sentence)
            if handled is not None:
                return handled

        self.history.append({"role": "user", "content": user_text})
        self._trim()
        reply_parts: List[str] = []

        for _ in range(MAX_TOOL_ROUNDS + 1):
            content, tool_calls = self._stream_once(on_sentence, reply_parts)
            assistant_msg = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            self.history.append(assistant_msg)
            if not tool_calls:
                break
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                result = self._call_tool(name, args)
                self.history.append({"role": "tool", "tool_name": name, "content": result})
            if self.pending:
                # Ask deterministically; never let the model narrate an
                # action that hasn't happened.
                question = self._confirmation_question(*self.pending[:2])
                self.history.append({"role": "assistant", "content": question})
                reply_parts.clear()
                reply_parts.append(question)
                on_sentence(question)
                break

        reply = " ".join(p for p in reply_parts if p).strip()
        if not reply:
            reply = "Done."
            on_sentence(reply)
        return reply

    def _call_tool(self, name: str, args: dict) -> str:
        tool_obj = self.tools.get(name)
        log.info("tool %s %s", name, args)
        self.on_tool(name, args)
        if tool_obj is None:
            return f"Error: there is no tool named {name}."
        if name == "end_conversation":
            self.end_requested = True
        if tool_obj.risk == CONFIRM:
            self.pending = (tool_obj, args, time.time())
            return ("NOT executed yet: this action needs confirmation. Ask the user, in one short "
                    "sentence, to confirm with yes or no. Do not claim it has happened.")
        return self.tools.run(name, args)

    @staticmethod
    def _confirmation_question(tool_obj, args) -> str:
        action = args.get("action", tool_obj.name.replace("_", " "))
        phrases = {"shutdown": "shut down the computer", "reboot": "restart the computer",
                   "suspend": "put the computer to sleep", "logout": "log you out"}
        return f"Just to be sure, do you want me to {phrases.get(action, action)}?"

    def _resolve_pending(self, user_text: str, on_sentence) -> Optional[str]:
        tool_obj, args, asked_at = self.pending
        self.pending = None
        words = re.findall(r"[a-z']+", user_text.lower())
        if time.time() - asked_at > CONFIRM_TIMEOUT:
            return None  # stale: never act on a late "yes"
        if NO.search(user_text):
            reply = "Okay, I won't."
        elif YES.search(user_text) and len(words) <= 5:
            # Only a short, standalone yes counts ("yes", "yeah do it"), so
            # "ok, what time is it first?" or background chatter can't confirm.
            result = self.tools.run(tool_obj.name, args)
            done = {"shutdown": "Okay, shutting down now. Goodbye!", "reboot": "Okay, restarting now. See you soon!",
                    "suspend": "Okay, going to sleep now.", "logout": "Okay, logging you out."}
            action = args.get("action", "")
            reply = done.get(action, "Done.") if "started" in result.lower() else result
        else:
            return None  # unrelated reply: drop the pending action, handle normally
        self.history += [{"role": "user", "content": user_text},
                         {"role": "assistant", "content": reply}]
        on_sentence(reply)
        return reply

    def _stream_once(self, on_sentence, reply_parts):
        """One model call. Emits finished sentences as they arrive.

        The first sentence is held until a second one arrives or the stream
        ends: tool calls come at the end, and if one needs confirmation we
        must not have already said "Sure, shutting down!"."""
        buffer, content, tool_calls, held = "", "", [], []
        for chunk in self.client.chat_stream(self._messages(), tools=self.tools.schemas()):
            tool_calls.extend(chunk["tool_calls"])
            piece = chunk["content"]
            if not piece:
                continue
            content += piece
            buffer += piece
            *done, buffer = SENTENCE_END.split(buffer)
            held.extend(done)
            if len(held) >= 2:
                for sentence in held:
                    self._emit(sentence, on_sentence, reply_parts)
                held = []
        held.append(buffer)
        needs_confirm = any((self.tools.get(c.get("function", {}).get("name", "")) or Tool("", "", None)).risk
                            == CONFIRM for c in tool_calls)
        if not needs_confirm:
            for sentence in held:
                self._emit(sentence, on_sentence, reply_parts)
        return content, tool_calls

    @staticmethod
    def _emit(text, on_sentence, reply_parts):
        clean = speakable(text)
        if clean:
            reply_parts.append(clean)
            on_sentence(clean)

    # ---------------------------------------------------------------- greeting
    def greet(self, on_sentence=lambda s: None, first_of_day=True) -> str:
        """Let the model open the conversation like a secretary would."""
        hour = dt.datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        instruction = (
            f"[The user just {'logged in to their computer' if first_of_day else 'woke you with the wake word'}. "
            f"It's {part}. Greet them warmly in one or two short sentences"
            + (" and ask how their day is going" if first_of_day else " and ask what they need")
            + ". Don't call any tools.]"
        )
        self.history.append({"role": "user", "content": instruction})
        reply_parts: List[str] = []
        content, _ = self._stream_once(on_sentence, reply_parts)
        self.history.append({"role": "assistant", "content": content})
        return " ".join(reply_parts)
