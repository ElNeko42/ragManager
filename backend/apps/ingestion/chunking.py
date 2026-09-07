"""Splitting extracted text into overlapping chunks."""

DEFAULT_CHUNK_WORDS = 400
DEFAULT_OVERLAP_WORDS = 60


def split_text(text, chunk_words=DEFAULT_CHUNK_WORDS, overlap_words=DEFAULT_OVERLAP_WORDS):
    """Split text into chunks that overlap at their edges.

    Takes the text, the target number of words per chunk and how many words
    each chunk repeats from the previous one, so that an idea cut in half by a
    boundary still appears whole in one of the two neighbours. Returns a list
    of chunk strings, empty when the text holds no words.
    """
    if overlap_words >= chunk_words:
        raise ValueError("The overlap must be smaller than the chunk size")
    words = text.split()
    if not words:
        return []
    step = chunk_words - overlap_words
    chunks = []
    for start in range(0, len(words), step):
        chunk = words[start : start + chunk_words]
        chunks.append(" ".join(chunk))
        if start + chunk_words >= len(words):
            break
    return chunks
