"""Splitting extracted text into overlapping chunks."""

import re

PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
SENTENCE_END = re.compile(r"(?<=[.!?;:])[ \t]")
OVERLAP_ALLOWANCE = 1.5


class Unit:
    """One sentence of the source text, and where it sits in it.

    The offsets are kept rather than the words, so that a chunk can be cut
    from the original text with its line breaks intact. Rebuilding a chunk by
    joining words back together flattens lists, headings and tables into a
    single line, which is exactly the structure that tells a model a price
    belongs to a plan.
    """

    def __init__(self, text, start, end, ends_paragraph):
        """Store the slice this unit covers and whether it closes a paragraph."""
        self.start = start
        self.end = end
        self.ends_paragraph = ends_paragraph
        self.words = len(text[start:end].split())
        self.tokens = 0


def split_text(text, chunk_words, overlap_words, max_tokens=None, count_tokens=None):
    """Split text into chunks that overlap at their edges.

    Takes the text, the target number of words per chunk, how many words each
    chunk repeats from the previous one and, when the model's own tokeniser is
    at hand, the number of tokens it will read and a way to count them.
    Returns a list of chunk strings, empty when the text holds no words.

    The token budget is what actually matters and the word count is only a
    stand-in for it: a model reads so many tokens and silently ignores the
    rest, and Spanish costs more tokens per word than the English most of
    these models were measured on. Whichever limit is reached first closes the
    chunk, so a chunk never carries text the model will not look at.

    Chunks are closed at a paragraph or a sentence boundary near the target
    rather than at an exact count, because a chunk that begins mid-sentence
    embeds as a fragment and scores below a worse passage that reads whole.
    """
    if overlap_words >= chunk_words:
        raise ValueError("The overlap must be smaller than the chunk size")
    units = list(split_units(text, chunk_words, overlap_words))
    if not units:
        return []
    if count_tokens and max_tokens:
        measure(units, text, count_tokens)
        units = fit(units, text, max_tokens, count_tokens)
    chunks = []
    start = 0
    while start < len(units):
        end = close_chunk(units, start, chunk_words, max_tokens)
        chunks.append(text[units[start].start : units[end - 1].end].strip())
        if end >= len(units):
            break
        start = step_back(units, start, end, overlap_words)
    return [chunk for chunk in chunks if chunk]


def measure(units, text, count_tokens):
    """Count how many tokens each unit costs the model.

    Takes the units, the text they point into and the model's counter. Counted
    once per sentence and added up, rather than counting every candidate chunk
    over and over, which would tokenise the same document dozens of times.
    """
    for unit in units:
        unit.tokens = count_tokens(text[unit.start : unit.end])


def fit(units, text, max_tokens, count_tokens):
    """Cut apart any unit that on its own costs more than the model reads.

    Takes the measured units, the text, the budget and the counter. Returns
    units none of which exceeds the budget, so that a chunk can always be
    closed before passing it.

    How many words fit in a token budget is not a constant: it depends on the
    model's vocabulary and on the language the document is written in, and a
    model trained on English spends far more tokens per word on Spanish. So
    the ratio is taken from the unit itself rather than assumed, and a margin
    is left because cutting changes it slightly.
    """
    fitted = []
    for unit in units:
        if unit.tokens <= max_tokens or unit.words <= 1:
            fitted.append(unit)
            continue
        words = text[unit.start : unit.end].split()
        each = max(1, int(unit.words * max_tokens / unit.tokens * 0.9))
        for piece in cut(text, unit.start, unit.end, words, each, unit.ends_paragraph):
            piece.tokens = count_tokens(text[piece.start : piece.end])
            fitted.append(piece)
    return fitted


def split_units(text, chunk_words, overlap_words):
    """Break text into the smallest pieces a chunk boundary may fall between.

    Takes the text, the target chunk size and the overlap. Yields units in the
    order they appear, each carrying a marker of whether it closes a paragraph
    so that the stronger boundary can be preferred.

    A sentence longer than a whole chunk is cut into pieces the size of the
    overlap: recognised text often carries no punctuation at all, and one
    unbroken run of it would otherwise become a single chunk far longer than
    the model reads, with no boundary anywhere for the next chunk to step back
    to.
    """
    granularity = overlap_words or chunk_words
    for paragraph_start, paragraph_end in spans(text, PARAGRAPH_BREAK):
        sentences = list(spans(text, SENTENCE_END, paragraph_start, paragraph_end))
        for position, (start, end) in enumerate(sentences):
            closes = position == len(sentences) - 1
            words = text[start:end].split()
            if not words:
                continue
            if len(words) <= chunk_words:
                yield Unit(text, start, end, closes)
                continue
            yield from cut(text, start, end, words, granularity, closes)


def cut(text, start, end, words, granularity, closes):
    """Cut one oversized sentence into pieces a chunk can be built from."""
    offset = start
    taken = 0
    while taken < len(words):
        piece = words[taken : taken + granularity]
        stop = end if taken + granularity >= len(words) else find_after(text, offset, piece)
        yield Unit(text, offset, stop, closes and stop == end)
        offset = stop
        taken += granularity


def find_after(text, offset, piece):
    """Return where a run of words ends inside the text it came from."""
    position = offset
    for word in piece:
        found = text.find(word, position)
        position = (found + len(word)) if found != -1 else position
    return position


def spans(text, pattern, start=0, end=None):
    """Yield the pieces a pattern cuts a slice of text into, as offsets.

    Takes the text, the separator, and the slice to work within. Returning
    offsets rather than substrings is what lets a chunk be cut from the
    original text later, with everything between its units still in place.
    """
    end = len(text) if end is None else end
    position = start
    for match in pattern.finditer(text, start, end):
        if match.start() > position:
            yield position, match.start()
        position = match.end()
    if position < end:
        yield position, end


def close_chunk(units, start, chunk_words, max_tokens):
    """Find where the chunk beginning at one unit should end.

    Takes the units, the index to start at, the target size and the token
    budget. Returns the index one past the last unit of the chunk.

    The word count is a target and the chunk closes at the first boundary that
    reaches it. The token budget is a ceiling and the chunk closes before
    passing it, because everything past it is text the model will not read: a
    target may be overshot, a ceiling may not. A paragraph boundary is
    preferred when one falls inside the last quarter of the chunk.
    """
    words = 0
    tokens = 0
    paragraph_end = None
    for index in range(start, len(units)):
        unit = units[index]
        if max_tokens and tokens and tokens + unit.tokens > max_tokens:
            return paragraph_end if paragraph_end and paragraph_end > start else index
        words += unit.words
        tokens += unit.tokens
        if unit.ends_paragraph and words >= chunk_words * 3 // 4:
            paragraph_end = index + 1
        if words >= chunk_words:
            return paragraph_end or index + 1
    return len(units)


def step_back(units, start, end, overlap_words):
    """Find where the next chunk starts so that it repeats the overlap.

    Takes the units, the index the chunk just closed began at, the index it
    ended at and how many words to repeat. Returns the index the next chunk
    starts at.

    A unit is only taken back when it fits the budget with room to spare, so
    that one long sentence cannot turn a fifth of a chunk into half of it:
    every word repeated is a word the reader pays for twice. The walk stops
    one unit past where the last chunk began either way, since a sentence
    longer than the whole overlap would otherwise make the split stand still
    and emit the same chunk forever.
    """
    if overlap_words <= 0:
        return end
    budget = overlap_words * OVERLAP_ALLOWANCE
    counted = 0
    index = end
    while index > start + 1:
        taking = units[index - 1].words
        if counted and counted + taking > budget:
            break
        counted += taking
        index -= 1
        if counted >= overlap_words:
            break
    return index
