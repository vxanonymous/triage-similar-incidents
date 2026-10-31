"""read_incident's checks: the fields are the record's own, as the file holds them."""

from .checks import path_problem, read_records, result


def verify_input(value):
    problem = path_problem(value.file, ".jsonl")
    if problem:
        return result(False, problem)
    if not value.id.strip():
        return result(False, "id must not be blank")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    records = read_records(workspace, input_value.file)
    if isinstance(records, str):
        return result(False, records)
    found = [record for record in records if record["id"] == input_value.id]
    if not found:
        return result(False, f"{input_value.file} has no incident {input_value.id}")
    record = found[0]
    if (output_value.file, output_value.id) != (input_value.file, input_value.id):
        return result(False, "file or id is not the one asked for")
    returned = {"service": output_value.service, "summary": output_value.summary, "resolution": output_value.resolution}
    wrong = [key for key, value in returned.items() if value != record[key]]
    if wrong:
        return result(False, f"{', '.join(wrong)} differ from the record", wrong=wrong)
    return result(True, f"{input_value.id} is read as the file holds it")
