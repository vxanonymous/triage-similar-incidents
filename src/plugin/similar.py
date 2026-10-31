"""find_similar: MinHash signatures and LSH banding over word 3-gram shingles, then exact Jaccard on candidates."""

import hashlib
import operator
import re
from pathlib import Path

from contract import Match, SimilarInput, SimilarOutput
from plugin.incidents import read_records

MIN_PERM, MAX_PERM = 16, 256
SHINGLE = 3


def shingles(text: str) -> set[str]:
    """Consecutive word 3-grams of the lowercased text; a text of 1 or 2 words is one shingle of all its words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        raise ValueError("text must hold at least one word of letters or digits")
    if len(words) < SHINGLE:
        return {" ".join(words)}
    return {" ".join(words[index : index + SHINGLE]) for index in range(len(words) - SHINGLE + 1)}


def signatures(sets: list[set[str]], num_perm: int) -> list[list[int]]:
    """Each set's MinHash signature. Value i of a set is the least 64-bit blake2b digest of its shingles,
    salted with i as 8 big-endian bytes. Each distinct shingle is hashed once per salt."""
    distinct = sorted(set().union(*sets))
    position = {gram: index for index, gram in enumerate(distinct)}
    encoded = [gram.encode("utf-8") for gram in distinct]
    # Each picker returns a tuple of the set's digests plus one extra (index 0), dropped below, so a
    # one-shingle set still gets a tuple.
    pickers = [operator.itemgetter(*sorted(position[gram] for gram in grams), 0) for grams in sets]
    result: list[list[int]] = [[] for _ in sets]
    for index in range(num_perm):
        salted = hashlib.blake2b(digest_size=8, salt=index.to_bytes(8, "big"))
        digests = []
        for gram in encoded:
            hasher = salted.copy()
            hasher.update(gram)
            digests.append(hasher.digest())
        for values, picker in zip(result, pickers):
            # Equal-length big-endian digests order as their integers do.
            values.append(int.from_bytes(min(picker(digests)[:-1]), "big"))
    return result


def band_keys(values: list[int], rows: int) -> list[tuple[int, ...]]:
    return [tuple(values[start : start + rows]) for start in range(0, len(values), rows)]


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right)


def check_settings(threshold: float, num_perm: int, bands: int) -> None:
    if not 0 <= threshold <= 1:
        raise ValueError(f"threshold must be between 0 and 1, got {threshold}")
    if not MIN_PERM <= num_perm <= MAX_PERM:
        raise ValueError(f"num_perm must be between {MIN_PERM} and {MAX_PERM}, got {num_perm}")
    if bands < 1 or num_perm % bands:
        raise ValueError(f"bands must be a positive divisor of num_perm {num_perm}, got {bands}")


def find_similar(given: SimilarInput, workspace: Path) -> SimilarOutput:
    check_settings(given.threshold, given.num_perm, given.bands)
    query = shingles(given.text)
    corpus = [(record["id"], shingles(record["summary"])) for record in read_records(workspace, given.file)]
    rows = given.num_perm // given.bands
    query_signature, *corpus_signatures = signatures([query] + [grams for _, grams in corpus], given.num_perm)
    wanted = band_keys(query_signature, rows)
    candidates, matches = 0, []
    for (incident, grams), values in zip(corpus, corpus_signatures):
        if not any(key == want for key, want in zip(band_keys(values, rows), wanted)):
            continue
        candidates += 1
        exact = jaccard(query, grams)
        if exact >= given.threshold:
            matches.append(Match(id=incident, jaccard=round(exact, 4)))
    matches.sort(key=lambda match: (-match.jaccard, match.id))
    return SimilarOutput(
        file=given.file,
        threshold=given.threshold,
        num_perm=given.num_perm,
        bands=given.bands,
        rows=rows,
        candidates_checked=candidates,
        matches=matches,
    )
