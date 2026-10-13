"""Hangup: silently absorb utterances that Switchboard declines.

When Switchboard decides speech wasn't meant for the assistant (overheard conversation, TV, the assistant hearing
itself) it dispatches the utterance here instead of letting it fall through to fallback skills, which would SPEAK.
Hangup speaks nothing: it records the decline and announces it on the bus as ``hangup.declined``.

Hangup registers no intents, so no matcher can route to it by accident; the only way in is a dispatch to
``<skill_id>:decline``. The handler is registered through ``add_event`` so ovos-core's dispatcher receives the usual
completion signal and the round ends cleanly.
"""

import inspect
import json
import logging
import time
from logging.handlers import RotatingFileHandler

from ovos_bus_client.message import Message
from ovos_workshop.skills.ovos import OVOSSkill


class HangupSkill(OVOSSkill):
    # Interface contract with Switchboard, not user settings: changing either on one side alone breaks routing.
    DECLINE_INTENT = "decline"
    DECLINED_EVENT = "hangup.declined"

    def initialize(self):
        self.decline_log = self._make_decline_log()
        # ovos-workshop >= 8 reports intent_name in the done-signal; Neon Hub's 0.1.7 has no such parameter.
        extra = {"intent_name": self.DECLINE_INTENT} \
            if "intent_name" in inspect.signature(self.add_event).parameters else {}
        self.add_event(f"{self.skill_id}:{self.DECLINE_INTENT}", self.handle_decline,
                       handler_info="mycroft.skill.handler", activation=False, speak_errors=False, **extra)

    def _make_decline_log(self):
        """A JSON-lines decline log in the skill's data directory, rotated by the standard library."""
        logger = logging.getLogger(f"{self.skill_id}.declines")
        logger.propagate = False
        logger.handlers.clear()
        if self.settings.get("log_declines", True):
            path = f"{self.file_system.path}/{self.settings.get('log_file', 'declines.jsonl')}"
            handler = RotatingFileHandler(path, maxBytes=int(self.settings.get("max_log_bytes", 5_000_000)),
                                          backupCount=int(self.settings.get("log_backups", 1)), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def describe(self, message: Message) -> dict:
        """What was declined and why, from Switchboard's dispatch."""
        data = message.data
        utterances = data.get("utterances") or ([data["utterance"]] if data.get("utterance") else [])
        session = message.context.get("session") if isinstance(message.context.get("session"), dict) else {}
        return {
            "ts": round(time.time(), 3),
            "utterance": utterances[0] if utterances else None,
            "lang": data.get("lang"),
            "reason": data.get("reason"),  # e.g. "ignore", "decline_class", "gate"
            "stage": data.get("stage"),
            "detail": {k: v for k, v in data.items() if k not in {"utterance", "utterances", "lang", "reason", "stage"}},
            "session_id": session.get("session_id"),
        }

    def handle_decline(self, message: Message):
        """Never speaks. Records the decline and tells the bus."""
        record = self.describe(message)
        self.decline_log.info(json.dumps(record, default=str))
        self.log.info(f"declined to participate: {record['utterance']!r} ({record['reason']}, {record['stage']})")
        self.bus.emit(message.forward(self.DECLINED_EVENT, record))
