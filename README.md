# Hangup

An OVOS skill that silently absorbs utterances [Switchboard](https://github.com/OscillateLabsLLC/switchboard) declines.

A voice assistant hears a lot that isn't meant for it: conversation in the room, the TV, its own voice. In stock
OVOS, anything the intent pipeline can't place falls through to fallback skills, and those *speak* ("I don't
understand", or an LLM answer to a sentence nobody asked). That's the false trigger households find most irritating.

When Switchboard decides speech wasn't meant for the assistant, it dispatches it to Hangup instead. Hangup:

- **speaks nothing**,
- appends a JSON line to `declines.jsonl` in its data directory (utterance, reason, pipeline stage, details),
- emits `hangup.declined` on the bus for anything that wants to observe.

Hangup registers no intents, so no matcher can route to it by accident. The only way in is a dispatch to
`ovos-skill-hangup.oscillatelabsllc:decline`. The handler runs through ovos-workshop's event machinery, so
ovos-core's dispatcher gets its normal completion signal and the round ends cleanly.

## Install

```sh
pip install git+https://github.com/OscillateLabsLLC/hangup
```

Works with ovos-workshop 0.x (Neon Hub) and current OVOS (9.x).

## Settings

| key | default | meaning |
|---|---|---|
| `max_log_bytes` | 5000000 | rotate `declines.jsonl` to `declines.jsonl.1` past this size |
