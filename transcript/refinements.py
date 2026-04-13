from dataclasses import dataclass

from transcript.entries import Paragraph, Word


@dataclass
class WordUpdate:
    start: float
    replacement_text: str


@dataclass
class WordDelete:
    start: float


@dataclass
class WordInsert:
    start: float
    end: float
    replacement_text: str


@dataclass
class ParagraphInsert:
    start: float


@dataclass
class ParagraphMerge:
    start: float
    end: float


# --- Apply functions ---

def apply_word_update(instruction: WordUpdate, paragraphs: list[Paragraph]) -> None:
    for paragraph in paragraphs:
        for word in paragraph.words:
            if word.start == instruction.start:
                word.text = instruction.replacement_text
                return


def apply_word_delete(instruction: WordDelete, paragraphs: list[Paragraph]) -> None:
    for paragraph in paragraphs:
        paragraph.words = [w for w in paragraph.words if w.start != instruction.start]


def apply_word_insert(instruction: WordInsert, paragraphs: list[Paragraph]) -> None:
    # Find the paragraph whose time range contains the insert timestamp
    target = _find_paragraph_for_timestamp(instruction.start, paragraphs)
    if target is None:
        return
    new_word = Word(
        start=instruction.start,
        end=instruction.end,
        text=instruction.replacement_text,
        paragraph_id=target.paragraph_id,
        speaker=None,
    )
    # Insert in order by start time
    for i, word in enumerate(target.words):
        if word.start > instruction.start:
            target.words.insert(i, new_word)
            return
    target.words.append(new_word)


def apply_paragraph_insert(instruction: ParagraphInsert, paragraphs: list[Paragraph]) -> None:
    # Split paragraph: words with s < timestamp stay, words with s >= timestamp move to new paragraph
    for i, paragraph in enumerate(paragraphs):
        words_before = [w for w in paragraph.words if w.start < instruction.start]
        words_after = [w for w in paragraph.words if w.start >= instruction.start]
        if words_after:
            paragraph.words = words_before
            # New paragraph id based on the split timestamp
            new_id = f"{paragraph.paragraph_id}_split_{instruction.start}"
            new_paragraph = Paragraph(paragraph_id=new_id)
            new_paragraph.words = words_after
            for word in words_after:
                word.paragraph_id = new_id
            paragraphs.insert(i + 1, new_paragraph)
            return


def apply_paragraph_merge(instruction: ParagraphMerge, paragraphs: list[Paragraph]) -> None:
    # Currently unused per README
    pass


def _find_paragraph_for_timestamp(timestamp: float, paragraphs: list[Paragraph]) -> Paragraph | None:
    """Find the paragraph whose time range contains the given timestamp."""
    for paragraph in paragraphs:
        if not paragraph.words:
            continue
        min_t = min(w.start for w in paragraph.words)
        max_t = max(w.start for w in paragraph.words)
        if min_t <= timestamp <= max_t:
            return paragraph
    # Fallback: last paragraph
    return paragraphs[-1] if paragraphs else None