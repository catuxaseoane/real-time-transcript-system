from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Word:
    start: float
    end: float | None
    text: str
    paragraph_id: str
    speaker: str | None


@dataclass
class Paragraph:
    paragraph_id: str
    words: list[Word] = field(default_factory=list)

    def speaker(self) -> str | None:
        """Majority vote robust (ignores None / empty)."""
        speakers = [
            w.speaker
            for w in self.words
            if w.speaker is not None and str(w.speaker).strip() != ""
        ]
        if not speakers:
            return None

        return Counter(speakers).most_common(1)[0][0]

    def text(self) -> str:
        """Return clean, ordered text."""
        words = sorted(self.words, key=lambda w: w.start)

        clean = []
        for w in words:
            if not w.text:
                continue
            clean.append(w.text)

        return " ".join(clean)