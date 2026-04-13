import json

from transcript.entries import Paragraph, Word
from transcript.refinements import (
    ParagraphInsert,
    ParagraphMerge,
    WordDelete,
    WordInsert,
    WordUpdate,
    apply_paragraph_insert,
    apply_paragraph_merge,
    apply_word_delete,
    apply_word_insert,
    apply_word_update,
)

ParseResult = Word | WordUpdate | WordDelete | WordInsert | ParagraphInsert | ParagraphMerge | None


def parse(line: str) -> ParseResult:
    record = json.loads(line)

    # Refinement instruction
    if "i" in record:
        s = record["s"]
        if record["i"] == "word-update":
            return WordUpdate(s, record["rt"])
        elif record["i"] == "word-delete":
            return WordDelete(s)
        elif record["i"] == "word-insert":
            return WordInsert(s, record["e"], record["rt"])
        elif record["i"] == "paragraph-insert":
            return ParagraphInsert(s)
        elif record["i"] == "paragraph-merge":
            return ParagraphMerge(s, record["e"])

    # Control record
    if "type" in record:
        return None

    # Entry (Word)
    return Word(record["s"], record["e"], record["t"], record["p"], record.get("S"))


def handle(line: str, paragraphs: list[Paragraph]) -> bool:
    """Process a line and update paragraphs. Returns True if stream has ended."""
    record = json.loads(line)

    # Check for end before parsing — we need to stop polling
    if record.get("type") == "end":
        return True

    result = parse(line)

    if result is None:
        return False

    if isinstance(result, Word):
        # SPEC-COMPLIANT: Group words by JSON p-field (paragraph_id) as per README spec.
        # "Paragraph id — words with the same p belong together."
        # Speaker changes within a paragraph are handled via majority vote.
        for paragraph in paragraphs:
            if paragraph.paragraph_id == result.paragraph_id:
                paragraph.words.append(result)
                return False

        # Paragraph doesn't exist yet, create it
        new_paragraph = Paragraph(paragraph_id=result.paragraph_id)
        new_paragraph.words.append(result)
        paragraphs.append(new_paragraph)
        return False

    elif isinstance(result, WordUpdate):
        apply_word_update(result, paragraphs)

    elif isinstance(result, WordDelete):
        apply_word_delete(result, paragraphs)

    elif isinstance(result, WordInsert):
        apply_word_insert(result, paragraphs)

    elif isinstance(result, ParagraphInsert):
        apply_paragraph_insert(result, paragraphs)

    elif isinstance(result, ParagraphMerge):
        apply_paragraph_merge(result, paragraphs)

    return False
