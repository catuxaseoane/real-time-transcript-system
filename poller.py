import asyncio

import httpx

from transcript.handler import handle
from transcript.state import StreamState


async def poll(
    state: StreamState,
    speed: float = 10.0,
    base_url: str = "http://localhost:8000",
) -> None:
    """Poll the server incrementally using byte-range requests."""
    state.status = "live"

    async with httpx.AsyncClient() as client:
        while state.status != "ended":
            headers = {}
            if state.byte_offset > 0:
                headers["Range"] = f"bytes={state.byte_offset}-"

            try:
                response = await client.get(
                    f"{base_url}/transcript",
                    headers=headers,
                    params={"speed": speed},
                )

                if response.status_code in (200, 206):
                    content = response.content
                    if content:
                        state.byte_offset += len(content)
                        for line in content.decode().splitlines():
                            if line.strip():
                                ended = handle(line, state.paragraphs)
                                if ended:
                                    state.status = "ended"
                                    return

                # 416 = no new bytes yet, just wait
            except httpx.RequestError:
                pass

            await asyncio.sleep(0.5)