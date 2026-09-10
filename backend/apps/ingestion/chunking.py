"""Splitting extracted text into overlapping chunks."""

import re

MIN_CHUNK_WORDS = 20
MIN_OVERLAP_WORDS = 0

PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
SENTENCE_END = re.compile(r"(?<=[.!?;:])\s")


def split_text(text, chunk_words, overlap_words):
    """Split text into chunks that overlap at their edges.

    Takes the text, the target number of words per chunk and how many words
    each chunk repeats from the previous one, so that an idea cut in half by a
    boundary still appears whole in one of the two neighbours. Returns a list
    of chunk strings, empty when the text holds no words.

    Chunks are closed at a paragraph or a sentence boundary whenever one falls
    near the target rather than at the exact word count: a chunk that begins
    mid-sentence embeds as a fragment, and a search then scores it below a
    worse passage that happens to read as a whole. The target is a size, not a
    rule, so a chunk ends up a little shorter or a little longer than asked.
    """
    if overlap_words >= chunk_words:
        raise ValueError("The overlap must be smaller than the chunk size")
    units = list(split_units(text, chunk_words, overlap_words))
    if not units:
        return []
    chunks = []
    start = 0
    while start < len(units):
        end = close_chunk(units, start, chunk_words)
        chunks.append(" ".join(word for unit in units[start:end] for word in unit))
        if end >= len(units):
            break
        start = step_back(units, start, end, overlap_words)
    return chunks


def split_units(text, chunk_words, overlap_words):
    """Break text into the smallest pieces a chunk boundary may fall between.

    Takes the text, the target chunk size and the overlap. Yields lists of
    words, one per sentence, carrying a marker of whether the piece ends a
    paragraph so that the stronger boundary can be preferred. Returns nothing
    at all for text that holds no words.

    A sentence longer than a whole chunk is cut into pieces the size of the
    overlap: recognised text often carries no punctuation at all, and one
    unbroken run of it would otherwise become a single chunk far longer than
    the model reads, with no boundary left anywhere for the next chunk to
    step back to.
    """
    granularity = overlap_words or chunk_words
    for paragraph in PARAGRAPH_BREAK.split(text):
        sentences = [part for part in SENTENCE_END.split(paragraph) if part.strip()]
        for position, sentence in enumerate(sentences):
            words = sentence.split()
            if not words:
                continue
            closes = position == len(sentences) - 1
            if len(words) <= chunk_words:
                unit = Unit(words)
                unit.ends_paragraph = closes
                yield unit
                continue
            for start in range(0, len(words), granularity):
                unit = Unit(words[start : start + granularity])
                unit.ends_paragraph = closes and start + granularity >= len(words)
                yield unit


class Unit(list):
    """One sentence of the source text, and whether it closes a paragraph."""

    ends_paragraph = False


def close_chunk(units, start, chunk_words):
    """Find where the chunk beginning at one unit should end.

    Takes the units, the index to start at and the target size. Returns the
    index one past the last unit of the chunk: the first boundary that reaches
    the target, preferring the end of a paragraph when one falls inside the
    last quarter of the chunk. A single sentence longer than the target
    becomes a chunk on its own rather than being cut mid-thought.
    """
    counted = 0
    paragraph_end = None
    for index in range(start, len(units)):
        counted += len(units[index])
        if units[index].ends_paragraph and counted >= chunk_words * 3 // 4:
            paragraph_end = index + 1
        if counted >= chunk_words:
            return paragraph_end or index + 1
    return len(units)


def step_back(units, start, end, overlap_words):
    """Find where the next chunk starts so that it repeats the overlap.

    Takes the units, the index the chunk just closed began at, the index it
    ended at and how many words to repeat. Walks back from the end until the
    repeated words reach the overlap, stopping one unit past where the last
    chunk began: a sentence longer than the whole overlap would otherwise make
    the split stand still and emit the same chunk forever. Returns the index
    the next chunk starts at.
    """
    counted = 0
    index = end
    while index > start + 1 and counted < overlap_words:
        counted += len(units[index - 1])
        index -= 1
    return index
