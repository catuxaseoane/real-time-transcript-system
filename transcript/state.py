from dataclasses import dataclass, field

from transcript.entries import Paragraph


@dataclass
class StreamState:
    paragraphs: list[Paragraph] = field(default_factory=list)
    status: str = "not_started"  # not_started, live, ended
    byte_offset: int = 0
