# Live Transcript Assignment

![Demo](demo.gif)

## Scenario

A FastAPI server simulates a live earnings call transcript. It serves a growing [JSON Lines](https://jsonlines.org/) stream — one JSON object per line — just as it would from S3 during a real event.

The stream contains **word-level entries** that build up the text, and **refinement instructions** that correct previously delivered words and paragraphs.

## Task

Build a Python **TUI** that:

1. Polls the server to incrementally consume new lines as they appear
2. Groups words into paragraphs with speaker labels
3. Applies refinement instructions to update already-displayed text
4. Shows the transcript updating live in the terminal

Use any libraries you like. `httpx`, `rich`, and `textual` are included as suggestions.

## Bonus

- Use HTTP byte-range requests (`Range: bytes=N-`) for efficient incremental polling
- Handle `[indiscernible]` markers
- Visual indication when refinements update existing text
- Paragraph-level speaker via majority vote (see below)
- Tests for the refinement logic

## Getting started

```bash
pip install -e .
uvicorn server:app
curl http://localhost:8000/transcript
```

| Endpoint | Description |
|---|---|
| `GET /transcript?speed=1` | Lines available up to current simulated time. `speed` (default 1) is a playback multiplier. |
| `GET /transcript/status?speed=1` | `not_started`, `live`, or `ended`. |
| `POST /reset` | Resets the simulation clock. |

The server supports `Range: bytes=N-` headers (returns 206). The clock starts on first request to `/transcript`.

---

## Format specification

Each line is a JSON object. The `type` field indicates the record type. If `type` is missing, the record is an **entry**.

### Entries

A single word in the transcript. The most common record type.

| Field | Type | Description |
|---|---|---|
| `t` | string | The word. `[indiscernible]` means low confidence. |
| `s` | number | Start time (seconds). |
| `e` | number | End time (seconds). |
| `p` | string | Paragraph id — words with the same `p` belong together. |
| `S` | string | Speaker index (uppercase, 0-indexed). May be missing. |
| `ot` | string | Original text when `t` is `[indiscernible]`. |
| `c` | number | Confidence score. |

```json
{"s": 585.32, "e": 585.6, "p": "10", "t": "you.", "S": "20"}
```

Ignore unknown keys — the format may be extended.

### Control records

- **`start`** — first record, metadata only.
- **`keep-alive`** — stream is active, no content. Ignore.
- **`end`** — final record. Stop polling. Has optional `code` (0 = success) and `user_reason`.
- **`interruption`** — transcription error. Has `time` (seconds) and `restarting` (bool).
- **`section`** — marks start/end of a section (e.g. `predicted-qna`, `predicted-speech`). Has `name` and either `s` or `e`.
- **Unknown types** — ignore them.

### Refinement instructions

Records with an `i` field correct previously delivered content. Apply in order.

| Instruction | Fields | Effect |
|---|---|---|
| `word-update` | `s`, `rt` | Replace the word at timestamp `s` with `rt`. |
| `word-delete` | `s` | Remove the word at timestamp `s`. |
| `word-insert` | `s`, `e`, `rt` | Insert a new word at timestamp `s`. |
| `paragraph-insert` | `s` | Split paragraph: words with `s` < timestamp stay, words with `s` >= timestamp move to a new paragraph. |
| `paragraph-merge` | `s`, `e` | Merge paragraphs in time range (currently unused). |

Instructions arrive in chunks. For example, splitting "TomHanks" into two words is a `word-delete` + two `word-insert`s.

### Example

```json
{"s":1493.2,"e":1493.44,"p":"17","t":"close","S":"2"}
{"s":1493.44,"e":1493.72,"p":"17","t":"with","S":"2"}
{"s":1495.2,"e":1495.44,"p":"17","t":"good","S":"2"}
{"s":1495.44,"e":1495.96,"p":"17","t":"news","S":"2"}
{"s":1496.4,"e":1496.4,"p":"17","t":"?","S":"2"}
{"s":1495.44,"e":null,"rt":null,"i":"word-delete"}
{"s":1496.4,"e":null,"rt":null,"i":"word-delete"}
{"s":1495.44,"e":1496.4,"rt":"news?","i":"word-insert"}
```

The refinements delete "news" and "?" then insert "news?" — merging them into one token.

### Paragraph-level speakers

Speaker indexes (`S`) can fluctuate within a paragraph. Use **majority vote** for a stable label: the most common `S` in a paragraph is its speaker. UIs may display 1-indexed (Speaker 1, Speaker 2, ...).
