"""find_similar's checks: the LSH candidates and exact Jaccard matches, recomputed from the file with hashlib."""

from .checks import (
    MAX_PERM,
    MIN_PERM,
    bands_of,
    jaccard,
    minhashes,
    path_problem,
    read_records,
    result,
    shingles,
    words,
)

# A match LSH misses with at most this probability must be found.
MISS_LIMIT = 1e-6


def settings_problem(threshold, num_perm, bands):
    if not 0 <= threshold <= 1:
        return "threshold must be between 0 and 1"
    if not MIN_PERM <= num_perm <= MAX_PERM:
        return f"num_perm must be between {MIN_PERM} and {MAX_PERM}"
    if bands < 1 or num_perm % bands:
        return "bands must be a positive divisor of num_perm"
    return None


def verify_input(value):
    problem = (
        path_problem(value.file, ".jsonl")
        or settings_problem(value.threshold, value.num_perm, value.bands)
        or (None if words(value.text) else "text must hold at least one word of letters or digits")
    )
    if problem:
        return result(False, problem)
    return result(True, "input is valid")


def expected(input_value, records):
    """The candidate count and the (id, rounded jaccard) matches in order, and every exact Jaccard by id."""
    query = shingles(input_value.text)
    corpus = [shingles(record["summary"]) for record in records]
    rows = input_value.num_perm // input_value.bands
    query_signature, *signatures = minhashes([query, *corpus], input_value.num_perm)
    wanted = bands_of(query_signature, rows)
    candidates, matches, exact = 0, [], {}
    for record, grams, signature in zip(records, corpus, signatures):
        similarity = jaccard(query, grams)
        exact[record["id"]] = similarity
        if any(left == right for left, right in zip(bands_of(signature, rows), wanted)):
            candidates += 1
            if similarity >= input_value.threshold:
                matches.append((record["id"], round(similarity, 4)))
    matches.sort(key=lambda match: (-match[1], match[0]))
    return candidates, matches, exact


def verify_output(input_value, output_value, workspace):
    records = read_records(workspace, input_value.file)
    if isinstance(records, str):
        return result(False, records)
    if not words(input_value.text):
        return result(False, "text holds no words")
    rows = input_value.num_perm // input_value.bands
    candidates, matches, exact = expected(input_value, records)
    problems = []
    asked = (input_value.file, input_value.threshold, input_value.num_perm, input_value.bands, rows)
    echoed = (output_value.file, output_value.threshold, output_value.num_perm, output_value.bands, output_value.rows)
    if echoed != asked:
        problems.append("file, threshold, num_perm, bands or rows is not the one asked for")
    if output_value.candidates_checked != candidates:
        problems.append(f"candidates_checked is {output_value.candidates_checked}, but {candidates} share a band")
    given = [(match.id, match.jaccard) for match in output_value.matches]
    ids = [incident for incident, _ in given]
    if len(set(ids)) != len(ids):
        problems.append("an incident is listed twice")
    if sorted(given, key=lambda match: (-match[1], match[0])) != given:
        problems.append("matches are not ordered by jaccard, then id")
    if sorted(given) != sorted(matches):
        problems.append("matches are not the candidates with exact jaccard at least the threshold")
    surely_found = sorted(
        incident
        for incident, similarity in exact.items()
        if similarity >= input_value.threshold
        and (1 - similarity**rows) ** input_value.bands < MISS_LIMIT
        and incident not in ids
    )
    if surely_found:
        problems.append(f"near-duplicates LSH finds with certainty are missing: {', '.join(surely_found)}")
    if problems:
        return result(False, problems[0], problems=problems)
    return result(True, f"{len(matches)} matches among {candidates} LSH candidates", candidates=candidates)
