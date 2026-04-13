"""
Simple live transcript viewer — full-screen redraw style.

Matches the demo.gif behaviour:
  - First line shows byte counter ("Live transcript • N bytes received")
  - Below it, all paragraphs with speaker labels, rebuilt in-place each poll
  - No external TUI library needed — just ANSI escape codes

Run with:
    uvicorn server:app &
    python tui_basic.py
"""
import asyncio
import shutil
import sys

from poller import poll
from transcript.state import StreamState

# ANSI escape sequences
_HOME        = "\033[H"        # move cursor to top-left
_CLEAR_SCR   = "\033[2J"       # clear entire screen
_CLEAR_LINE  = "\033[2K"       # erase current line
_CLEAR_DOWN  = "\033[J"        # clear from cursor to end of screen
_HIDE_CURSOR = "\033[?25l"
_SHOW_CURSOR = "\033[?25h"


def _label(raw_id: str | None) -> str:
    """Display the raw S value as-is: S='21' → 'Speaker 21'."""
    return f"Speaker {raw_id}" if raw_id is not None else "Unknown"


def _para_start(p) -> float:
    """Earliest word start time — used to sort paragraphs chronologically."""
    return min(w.start for w in p.words) if p.words else 0.0


def _redraw(state: StreamState) -> None:
    """Clear screen and redraw the full transcript from the top.

    We use \033[2J (clear visible screen) + \033[H (go home) on every frame.
    Just \033[H alone fails when content exceeds terminal height: the terminal
    scrolls down, and on the next call \033[H only reaches the top of the
    *current* viewport — so old content above keeps accumulating and the whole
    transcript duplicates.  Clearing the screen first avoids that.
    The full output is built as a single string before writing to minimise flicker.
    """
    lines: list[str] = []

    # ── Header line ───────────────────────────────────────────────────────
    lines.append(f"Live transcript • {state.byte_offset:,} bytes received")
    lines.append("")

    # ── All paragraphs — sorted chronologically by first word timestamp ──
    sorted_paras = sorted(
        (p for p in state.paragraphs if p.text().strip()),
        key=_para_start,
    )
    last_speaker: str | None = None
    for p in sorted_paras:
        text = p.text().strip()
        speaker = _label(p.speaker())
        if speaker != last_speaker:
            lines.append(f"{speaker}: {text}")
            last_speaker = speaker
        else:
            lines.append(f"  {text}")  # same speaker — indent, no label

    # Build once, write once → minimises the visible flicker window
    sys.stdout.write(_CLEAR_SCR + _HOME + "\n".join(lines))
    sys.stdout.flush()


async def main() -> None:
    state = StreamState()
    asyncio.create_task(poll(state))

    # Initial setup
    sys.stdout.write(_CLEAR_SCR + _HOME + _HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            _redraw(state)

            if state.status == "ended":
                # Print final message below the transcript
                sys.stdout.write(f"\n─── Transcript ended ───\n")
                sys.stdout.flush()
                break

            await asyncio.sleep(0.3)

    finally:
        # Always restore cursor even if Ctrl-C'd
        sys.stdout.write(_SHOW_CURSOR)
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
