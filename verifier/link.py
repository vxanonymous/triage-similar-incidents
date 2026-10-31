"""link-new-incident's check: the submitted match against exact Jaccard over the whole seed's history."""

from .checks import jaccard, read_records, result, shingles
from .generate import expected_files


def verify_task(arguments, output, reference, workspace):
    """``output``: a contract LinkOutput for the history generated from ``arguments``' seed and count."""
    incidents, new = expected_files("incidents", arguments.seed, arguments.count)
    if output.incidents_file != incidents:
        return result(False, f"incidents_file is {output.incidents_file!r}, not the seed's history {incidents}")
    past = read_records(workspace, incidents)
    if isinstance(past, str):
        return result(False, past)
    fresh = read_records(workspace, new)
    if isinstance(fresh, str):
        return result(False, fresh)
    wanted = arguments.new_id.value
    reports = [record for record in fresh if record["id"] == wanted]
    if not reports:
        return result(False, f"{new} has no incident {wanted}")
    if not past:
        return result(False, f"{incidents} holds no incidents")
    query = shingles(reports[0]["summary"])
    similarity = {record["id"]: jaccard(query, shingles(record["summary"])) for record in past}
    resolution = {record["id"]: record["resolution"] for record in past}
    best = max(similarity.values())
    top = sorted(incident for incident, value in similarity.items() if value == best)
    runner_up = max((value for value in similarity.values() if value < best), default=0.0)
    allowed = [resolution[output.match_id]] if output.match_id in top else [resolution[i] for i in top]
    checks = {
        "new_id": output.new_id.value == wanted,
        "match_id": output.match_id in top,
        "jaccard": output.jaccard == round(best, 4),
        "resolution": output.resolution in allowed,
    }
    failed = [name for name, passed in checks.items() if not passed]
    details = {
        "best_matches": top,
        "best_jaccard": round(best, 4),
        "runner_up_jaccard": round(runner_up, 4),
        "failed": failed,
    }
    score = (len(checks) - len(failed)) / len(checks)
    if failed:
        return result(False, f"wrong {', '.join(failed)}", score=score, **details)
    return result(True, f"{wanted} matches {output.match_id} at jaccard {round(best, 4)}", **details)
