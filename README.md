# Hangup

An OVOS skill that says nothing. [Switchboard](https://github.com/OscillateLabsLLC/switchboard) sends it the speech
that wasn't meant for the assistant.

A voice assistant hears a lot that isn't for it: people talking in the room, the TV, its own voice. In stock OVOS,
anything no skill claims falls through to fallback skills, and those *answer*: "I don't understand", or an LLM's
reply to a sentence nobody asked. That's the false trigger households find most annoying.

When Switchboard decides speech wasn't for the assistant, it sends it to Hangup instead. Hangup:

- **says nothing**,
- adds a line to `declines.jsonl` in its data folder (what was heard, why it was declined, and by which step),
- announces `hangup.declined` on the bus, for anything that wants to watch.

Hangup registers no intents, so nothing can reach it by accident; only Switchboard sends to it. Switchboard needs
Hangup installed.

## Install

```sh
pip install ovos-skill-hangup
```

Python 3.11-3.14. Works with ovos-workshop 0.x (Neon) and current OVOS.

## Settings

| key | default | meaning |
|---|---|---|
| `log_declines` | `true` | write each declined utterance to the log |
| `log_file` | `declines.jsonl` | the log's file name, in the skill's data folder |
| `max_log_bytes` | 5000000 | above this size the log moves to `<log_file>.1` (one backup is kept) |

## License

Apache-2.0
