"""Hangup: silently absorb utterances that Switchboard declines.

When Switchboard decides speech wasn't meant for the assistant (overheard conversation, TV, the assistant hearing
itself) it routes the utterance here instead of letting it fall through to fallback skills, which would SPEAK
("I don't understand", an LLM answer). Hangup speaks nothing. It records each decline (JSONL in the skill's data
directory) and announces it on the bus as ``hangup.declined`` for anything that wants to observe.

Hangup registers no intents, so no matcher can ever route to it by accident: the only way in is a dispatch to
``<skill_id>:decline``, which Switchboard emits. The handler goes through ovos-workshop's event machinery so
ovos-core's dispatcher receives the usual completion signal and the round ends cleanly.
"""

import inspect
import json
import os
import time

from ovos_bus_client.message import Message
from ovos_utils.log import LOG
from ovos_workshop.skills.ovos import OVOSSkill

DECLINE_INTENT = "decline"
DECLINED_EVENT = "hangup.declined"
LOG_FILE = "declines.jsonl"
DEFAULT_MAX_LOG_BYTES = 5_000_000


def build_record(data: dict, context: dict) -> dict:
    """What was declined and why, from the dispatch message. Pure, for testing."""
    utterances = data.get("utterances") or ([data["utterance"]] if data.get("utterance") else [])
    session = context.get("session") if isinstance(context.get("session"), dict) else {}
    return {
        "ts": round(time.time(), 3),
        "utterance": utterances[0] if utterances else None,
        "lang": data.get("lang"),
        "reason": data.get("reason"),  # e.g. "ignore", "decline_class", "gate"
        "stage": data.get("stage"),
        "detail": {k: v for k, v in data.items() if k not in {"utterance", "utterances", "lang", "reason", "stage"}},
        "session_id": session.get("session_id"),
    }


def append_record(path: str, record: dict, max_bytes: int = DEFAULT_MAX_LOG_BYTES) -> None:
    """Append one JSON line, rotating to <path>.1 when the file exceeds max_bytes."""
    if os.path.exists(path) and os.path.getsize(path) > max_bytes:
        os.replace(path, path + ".1")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _supports_intent_name() -> bool:
    """ovos-workshop >= 8 reports intent_name in the done-signal; Neon Hub's 0.1.7 has no such parameter."""
    return "intent_name" in inspect.signature(OVOSSkill.add_event).parameters


class HangupSkill(OVOSSkill):
    def initialize(self):
        kwargs = {"intent_name": DECLINE_INTENT} if _supports_intent_name() else {}
        self.add_event(f"{self.skill_id}:{DECLINE_INTENT}", self.handle_decline,
                       handler_info="mycroft.skill.handler", activation=False, speak_errors=False, **kwargs)

    @property
    def log_path(self) -> str:
        return os.path.join(self.file_system.path, LOG_FILE)

    def handle_decline(self, message: Message):
        """Never speaks. Logs the decline and tells the bus."""
        record = build_record(message.data, message.context)
        try:
            append_record(self.log_path, record, int(self.settings.get("max_log_bytes", DEFAULT_MAX_LOG_BYTES)))
        except OSError:
            LOG.exception("Hangup could not write the decline log; continuing silently")
        LOG.info(f"declined to participate: {record['utterance']!r} ({record['reason']}, {record['stage']})")
        self.bus.emit(message.forward(DECLINED_EVENT, record))
