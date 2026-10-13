import json
import time
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from ovos_skill_hangup import DECLINE_INTENT, DECLINED_EVENT, HangupSkill, append_record, build_record

SKILL_ID = "ovos-skill-hangup.oscillatelabsllc"


def test_build_record_keeps_reason_and_detail():
    data = {"utterance": "honey where are my keys", "lang": "en-us", "reason": "ignore", "stage": "llm",
            "p_addressed": 0.12}
    record = build_record(data, {"session": {"session_id": "abc"}})
    assert record["utterance"] == "honey where are my keys"
    assert record["reason"] == "ignore"
    assert record["stage"] == "llm"
    assert record["detail"] == {"p_addressed": 0.12}
    assert record["session_id"] == "abc"


def test_build_record_tolerates_missing_fields():
    record = build_record({"utterances": ["yeah"]}, {})
    assert record["utterance"] == "yeah"
    assert record["session_id"] is None


def test_append_record_rotates(tmp_path):
    path = str(tmp_path / "declines.jsonl")
    append_record(path, {"n": 1}, max_bytes=1)
    append_record(path, {"n": 2}, max_bytes=1)  # previous file is over the cap -> rotated
    assert json.loads(Path(path).read_text()) == {"n": 2}
    assert json.loads(Path(path + ".1").read_text()) == {"n": 1}


@pytest.fixture
def skill(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    bus = FakeBus()
    s = HangupSkill(skill_id=SKILL_ID, bus=bus)
    yield s
    s.shutdown()


def _collect(bus, *topics):
    seen = {t: [] for t in topics}
    for t in topics:
        bus.on(t, lambda m, t=t: seen[t].append(m))
    return seen


def test_decline_dispatch_is_silent_logged_announced_and_completes(skill):
    seen = _collect(skill.bus, "speak", DECLINED_EVENT, "mycroft.skill.handler.complete")
    msg = Message(f"{SKILL_ID}:{DECLINE_INTENT}",
                  {"utterance": "dinner was great", "lang": "en-us", "reason": "decline_class", "stage": "classifier"},
                  {"session": {"session_id": "default"}, "skill_id": SKILL_ID})
    skill.bus.emit(msg)
    deadline = time.time() + 5
    while time.time() < deadline and not seen["mycroft.skill.handler.complete"]:
        time.sleep(0.05)
    assert not seen["speak"], "Hangup must never speak"
    assert seen[DECLINED_EVENT] and seen[DECLINED_EVENT][0].data["utterance"] == "dinner was great"
    assert seen["mycroft.skill.handler.complete"], "ovos-core's dispatcher waits for this done-signal"
    record = json.loads(Path(skill.log_path).read_text().splitlines()[-1])
    assert record["reason"] == "decline_class"


def test_registers_no_intents(skill):
    assert not skill.intent_service.registered_intents
