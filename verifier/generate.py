"""generate_incidents' checks: both files are where the seed names them, whole, and hash to the declared values."""

from pathlib import Path

from .checks import MAX_COUNT, MIN_COUNT, NEW_IDS, path_problem, read_records, result, sha256_of, words

MIN_WORDS, MAX_WORDS = 30, 60


def expected_files(destination, seed, count):
    folder = Path(destination)
    return (folder / f"incidents-{seed}-{count}.jsonl").as_posix(), (folder / f"new-{seed}-{count}.jsonl").as_posix()


def verify_input(value):
    if not MIN_COUNT <= value.count <= MAX_COUNT:
        return result(False, f"count must be between {MIN_COUNT} and {MAX_COUNT}")
    problem = path_problem(value.destination)
    if problem:
        return result(False, problem)
    return result(True, "input is valid")


def records_problem(records, ids, resolved):
    """Why ``records`` are not the expected incidents in order, or None."""
    if [record["id"] for record in records] != ids:
        return f"the ids are not {ids[0]} to {ids[-1]} in order"
    for record in records:
        length = len(words(record["summary"]))
        if not MIN_WORDS <= length <= MAX_WORDS:
            return f"{record['id']}'s summary has {length} words, not {MIN_WORDS} to {MAX_WORDS}"
        if bool(record["resolution"]) != resolved:
            return f"{record['id']}'s resolution should be {'set' if resolved else 'empty'}"
    return None


def verify_output(input_value, output_value, workspace):
    incidents, new = expected_files(input_value.destination, input_value.seed, input_value.count)
    if (output_value.incidents_file, output_value.new_file) != (incidents, new):
        return result(False, f"the files are not saved as {incidents} and {new}")
    if output_value.count != input_value.count:
        return result(False, f"count is {output_value.count}, not {input_value.count}")
    declared = {incidents: output_value.sha256, new: output_value.new_sha256}
    expected_ids = {
        incidents: [f"INC-{index:05d}" for index in range(1, input_value.count + 1)],
        new: NEW_IDS,
    }
    for file, digest in declared.items():
        records = read_records(workspace, file)
        if isinstance(records, str):
            return result(False, records)
        actual = sha256_of(workspace, file)
        if digest != actual:
            return result(False, f"sha256 of {file} does not match its bytes", declared=digest, actual=actual)
        problem = records_problem(records, expected_ids[file], file == incidents)
        if problem:
            return result(False, f"{file}: {problem}")
    return result(True, f"{incidents} holds {input_value.count} incidents and {new} holds {len(NEW_IDS)}")
