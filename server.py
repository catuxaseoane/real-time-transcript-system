"""Simulated live transcript server.

Serves lines from a JSONL transcript file incrementally,
gated by simulated elapsed time. Supports byte-range requests.
"""

import json
import time
from pathlib import Path

from fastapi import FastAPI, Query, Request, Response

app = FastAPI(title="Live Transcript Server")

TRANSCRIPT_PATH = Path(__file__).parent / "live_transcript_refined.jsonl"


### Precomputed line data ###


def _load_transcript() -> tuple[list[bytes], list[float]]:
    """Load transcript lines and compute effective timestamps.

    Returns
    -------
    raw_lines
        Each line as raw bytes (including trailing newline).
    effective_timestamps
        Per-line timestamp used for time-gating. Entries use their ``s``
        field; non-entry lines (control records, refinements) inherit
        the ``s`` of the most recent entry before them.
    """
    raw_lines: list[bytes] = []
    effective_timestamps: list[float] = []
    last_entry_ts: float | None = None

    with open(TRANSCRIPT_PATH, "rb") as fh:
        for raw in fh:
            raw_lines.append(raw)
            record = json.loads(raw)

            # An entry has "t" (transcript text) and "s" (start time).
            has_own_ts = "t" in record and "s" in record
            if has_own_ts:
                last_entry_ts = float(record["s"])

            effective_timestamps.append(
                last_entry_ts if last_entry_ts is not None else 0.0
            )

    return raw_lines, effective_timestamps


RAW_LINES, EFFECTIVE_TIMESTAMPS = _load_transcript()

# The first real entry timestamp — we skip ahead to this so there's
# no dead air at the start of the simulation.
ORIGIN_TS: float = next(
    (ts for ts in EFFECTIVE_TIMESTAMPS if ts > 0.0),
    0.0,
)


### Simulation clock ###

_start_wall: float | None = None


def _get_start_wall() -> float:
    """Return (and lazily initialise) the wall-clock start time."""
    global _start_wall
    if _start_wall is None:
        _start_wall = time.monotonic()
    return _start_wall


def _visible_line_count(speed: float) -> int:
    """How many lines should be visible at the current moment."""
    start = _get_start_wall()
    elapsed = (time.monotonic() - start) * speed
    cutoff_ts = ORIGIN_TS + elapsed

    # Binary search: find how many lines have effective_ts <= cutoff_ts.
    # Because effective timestamps are monotonically non-decreasing
    # (entries arrive in order, non-entries inherit the previous entry's ts),
    # we can bisect.
    lo, hi = 0, len(EFFECTIVE_TIMESTAMPS)
    while lo < hi:
        mid = (lo + hi) // 2
        if EFFECTIVE_TIMESTAMPS[mid] <= cutoff_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


### Endpoints ###


@app.get("/transcript")
async def get_transcript(
    request: Request,
    speed: float = Query(default=1, gt=0, description="Playback speed multiplier"),
) -> Response:
    """Serve transcript lines available up to the current simulated time.

    Supports ``Range: bytes=N-`` for incremental polling.
    """
    n_visible = _visible_line_count(speed)
    visible_bytes = b"".join(RAW_LINES[:n_visible])

    # Handle byte-range requests.
    range_header = request.headers.get("range")
    if range_header is not None:
        start_byte = _parse_range(range_header)
        if start_byte is None or start_byte >= len(visible_bytes):
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{len(visible_bytes)}"},
            )
        sliced = visible_bytes[start_byte:]
        return Response(
            content=sliced,
            status_code=206,
            media_type="application/x-ndjson",
            headers={
                "Content-Range": f"bytes {start_byte}-{len(visible_bytes) - 1}/{len(visible_bytes)}",
                "Accept-Ranges": "bytes",
            },
        )

    return Response(
        content=visible_bytes,
        status_code=200,
        media_type="application/x-ndjson",
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/transcript/status")
async def get_status(
    speed: float = Query(default=1, gt=0, description="Playback speed multiplier"),
) -> dict[str, str]:
    """Return the current stream status."""
    if _start_wall is None:
        return {"status": "not_started"}
    n_visible = _visible_line_count(speed)
    if n_visible >= len(RAW_LINES):
        return {"status": "ended"}
    return {"status": "live"}


### Helpers ###


def _parse_range(header: str) -> int | None:
    """Parse a ``Range: bytes=N-`` header, returning the start byte."""
    header = header.strip()
    if not header.startswith("bytes="):
        return None
    range_spec = header[len("bytes=") :]
    if "-" not in range_spec:
        return None
    start_str, _ = range_spec.split("-", 1)
    try:
        return int(start_str)
    except ValueError:
        return None


@app.post("/reset")
async def reset_clock() -> dict[str, str]:
    """Reset the simulation clock. Useful during development."""
    global _start_wall
    _start_wall = None
    return {"status": "reset"}
