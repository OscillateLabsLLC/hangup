import json
import time
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from ovos_skill_hangup import HangupSkill

SKILL_ID = "ovos-skill-hangup.oscillatelabsllc"
DECLINE_TOPIC = f"{SKILL_ID}:{HangupSkill.DECLINE_INTENT}"


@pytest.fixture
def skill(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    s = HangupSkill(skill_id=SKILL_ID, bus=FakeBus())
    yield s
    s.shutdown()


def collect(bus, *topics):
    seen = {t: [] for t in topics}
    for t in topics:
        bus.on(t, lambda m, t=t: seen[t].append(m))
    return seen


def decline(skill, **data):
    msg = Message(DECLINE_TOPIC, {"lang": "en-us", **data}, {"session": {"session_id": "default"}, "skill_id": SKILL_ID})
    skill.bus.emit(msg)


def wait_for(seen, topic, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline and not seen[topic]:
        time.sleep(0.05)


def test_decline_is_silent_logged_announced_and_completes(skill):
    seen = collect(skill.bus, "speak", HangupSkill.DECLINED_EVENT, "mycroft.skill.handler.complete")
    decline(skill, utterance="dinner was great", reason="decline_class", stage="classifier", p_addressed=0.12)
    wait_for(seen, "mycroft.skill.handler.complete")
    assert not seen["speak"], "Hangup must never speak"
    assert seen["mycroft.skill.handler.complete"], "ovos-core's dispatcher waits for this done-signal"
    announced = seen[HangupSkill.DECLINED_EVENT][0].data
    assert announced["utterance"] == "dinner was great"
    assert announced["detail"] == {"p_addressed": 0.12}
    record = json.loads((Path(skill.file_system.path) / "declines.jsonl").read_text().splitlines()[-1])
    assert record["reason"] == "decline_class"
    assert record["session_id"] == "default"


def test_file_logging_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    s = HangupSkill(skill_id=SKILL_ID, bus=FakeBus(), settings={"log_declines": False})
    try:
        seen = collect(s.bus, HangupSkill.DECLINED_EVENT)
        decline(s, utterances=["yeah"], reason="ignore", stage="llm")
        wait_for(seen, HangupSkill.DECLINED_EVENT)
        assert seen[HangupSkill.DECLINED_EVENT][0].data["utterance"] == "yeah"
        assert not (Path(s.file_system.path) / "declines.jsonl").exists()
    finally:
        s.shutdown()


def test_registers_no_intents(skill):
    assert not skill.intent_service.registered_intents


def test_log_moves_to_backup_past_size(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    s = HangupSkill(skill_id=SKILL_ID, bus=FakeBus(), settings={"max_log_bytes": 1})
    try:
        seen = collect(s.bus, "mycroft.skill.handler.complete")
        for text in ("first", "second"):
            decline(s, utterance=text, reason="ignore", stage="llm")
        deadline = time.time() + 5
        while time.time() < deadline and len(seen["mycroft.skill.handler.complete"]) < 2:
            time.sleep(0.05)
        log = Path(s.file_system.path) / "declines.jsonl"
        assert json.loads(log.read_text())["utterance"] == "second"
        assert json.loads(Path(f"{log}.1").read_text())["utterance"] == "first"
    finally:
        s.shutdown()
