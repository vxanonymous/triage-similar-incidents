"""Checks shared by the tool verifiers. Pure functions of their arguments and the files on disk."""

import hashlib
import json
import operator
import re
from pathlib import Path

KEYS = ["id", "service", "summary", "resolution"]
MIN_COUNT, MAX_COUNT = 50, 2000
MIN_PERM, MAX_PERM = 16, 256
NEW_IDS = ["NEW-1", "NEW-2", "NEW-3", "NEW-4", "NEW-5"]
SHINGLE = 3


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def path_problem(relative, suffix=None):
    path = Path(relative)
    if not relative.strip() or path.is_absolute() or ".." in path.parts:
        return f"{relative!r} must stay inside the plugin workspace"
    if suffix and path.suffix != suffix:
        return f"{relative!r} must be a {suffix} file"
    return None


def words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def shingles(text):
    """The set of consecutive word 3-grams joined by spaces; fewer than 3 words make one shingle of them all."""
    found = words(text)
    if len(found) < SHINGLE:
        return {" ".join(found)}
    return {" ".join(found[index : index + SHINGLE]) for index in range(len(found) - SHINGLE + 1)}


def jaccard(left, right):
    return len(left & right) / len(left | right)


def minhashes(sets, num_perm):
    """Each set's signature. Value i of a set is the least
    int.from_bytes(blake2b(shingle, digest_size=8, salt=i as 8 big-endian bytes).digest(), "big") over its shingles.
    Each distinct shingle is hashed once per i."""
    distinct = set()
    for grams in sets:
        distinct |= grams
    encoded = {gram: gram.encode("utf-8") for gram in distinct}
    lookups = [operator.itemgetter(*grams) for grams in sets]
    signatures = [[] for _ in sets]
    for index in range(num_perm):
        salted = hashlib.blake2b(digest_size=8, salt=index.to_bytes(8, "big"))
        digest = {}
        for gram, data in encoded.items():
            hasher = salted.copy()
            hasher.update(data)
            digest[gram] = hasher.digest()
        for grams, lookup, signature in zip(sets, lookups, signatures):
            # Equal-length big-endian digests order as the integers they encode.
            found = lookup(digest)
            signature.append(int.from_bytes(min(found) if len(grams) > 1 else found, "big"))
    return signatures


def bands_of(values, rows):
    return [tuple(values[start : start + rows]) for start in range(0, len(values), rows)]


def read_records(workspace, relative):
    """The file's records as dicts in order, or a string saying why it is not an incident file."""
    target = Path(workspace) / relative
    if not target.is_file():
        return f"{relative} is not in the workspace"
    records, seen = [], set()
    for number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
        except ValueError:
            return f"{relative} line {number} is not JSON"
        if not isinstance(record, dict) or list(record) != KEYS:
            return f"{relative} line {number} does not hold the keys {', '.join(KEYS)}"
        if not all(isinstance(value, str) for value in record.values()):
            return f"{relative} line {number} has a value that is not a string"
        if not words(record["summary"]):
            return f"{relative} line {number} has a summary with no words"
        if record["id"] in seen:
            return f"{relative} lists {record['id']} twice"
        seen.add(record["id"])
        records.append(record)
    return records


def sha256_of(workspace, relative):
    return hashlib.sha256((Path(workspace) / relative).read_bytes()).hexdigest()
