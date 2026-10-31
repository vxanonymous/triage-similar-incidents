from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import TASKS, TOOLS, GenerateInput, ReadInput, SimilarInput, Task, Tool
from plugin import find_similar, generate_incidents, read_incident


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def verify_input(tool: str, value: dict) -> dict:
    return verifier.verify_input(tool, build_output(value, TOOLS[Tool(tool)][0]))


def verify_output(tool: str, given: dict, made: dict, workspace: Path) -> dict:
    classes = TOOLS[Tool(tool)]
    return verifier.verify_output(tool, build_output(given, classes[0]), build_output(made, classes[1]), str(workspace))


def verify_task(task: str, arguments: dict, output: dict, workspace: Path) -> dict:
    given, made = TASKS[Task(task)]
    return verifier.verify_task(task, build_output(arguments, given), build_output(output, made), None, str(workspace))


def generated(workspace: Path, seed: int = 3, count: int = 200) -> tuple[dict, dict]:
    given = {"seed": seed, "count": count, "destination": "incidents"}
    return given, plain_output(generate_incidents(GenerateInput(**given), workspace))


def read(workspace: Path, file: str, id: str) -> tuple[dict, dict]:
    given = {"file": file, "id": id}
    return given, plain_output(read_incident(build_output(given, ReadInput), workspace))


def similar(workspace: Path, file: str, text: str, threshold=0.2, num_perm=128, bands=32) -> tuple[dict, dict]:
    given = {"file": file, "text": text, "threshold": threshold, "num_perm": num_perm, "bands": bands}
    return given, plain_output(find_similar(build_output(given, SimilarInput), workspace))


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


def incident(id: str, summary: str, resolution: str = "fixed") -> dict:
    return {"id": id, "service": "checkout-api", "summary": summary, "resolution": resolution}


# generate_incidents


@pytest.mark.parametrize("count", [50, 200])
def test_approves_generated_incidents(tmp_path: Path, count: int) -> None:
    given, made = generated(tmp_path, count=count)
    assert verify_output("generate_incidents", given, made, tmp_path)["valid"] is True
    assert verify_task("generate-incidents", given, made, tmp_path)["valid"] is True


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"incidents_file": "incidents/incidents-4-200.jsonl"}, "not saved as"),
        ({"new_file": "incidents/new.jsonl"}, "not saved as"),
        ({"sha256": "0" * 64}, "sha256"),
        ({"new_sha256": "0" * 64}, "sha256"),
        ({"count": 199}, "count"),
    ],
)
def test_refuses_a_wrong_generate_output(tmp_path: Path, changes: dict, message: str) -> None:
    given, made = generated(tmp_path)
    verdict = verify_output("generate_incidents", given, made | changes, tmp_path)
    assert verdict["valid"] is False and message in verdict["message"]


def test_refuses_missing_tampered_or_malformed_incident_files(tmp_path: Path) -> None:
    given, made = generated(tmp_path)
    target = tmp_path / made["incidents_file"]
    original = target.read_text()
    target.write_text(original.replace("INC-00001", "INC-00000", 1))
    assert "sha256" in verify_output("generate_incidents", given, made, tmp_path)["message"]
    target.write_text(original + "{not json\n")
    assert "not JSON" in verify_output("generate_incidents", given, made, tmp_path)["message"]
    target.write_text(original + '{"id": "INC-00201"}\n')
    assert "keys" in verify_output("generate_incidents", given, made, tmp_path)["message"]
    target.unlink()
    assert "not in the workspace" in verify_output("generate_incidents", given, made, tmp_path)["message"]


def test_refuses_a_rehashed_file_with_wrong_records(tmp_path: Path) -> None:
    given, made = generated(tmp_path, count=50)
    path = tmp_path / made["new_file"]
    records = [json.loads(line) for line in path.read_text().splitlines()]
    write_jsonl(path, [records[0] | {"resolution": "rolled back"}, *records[1:]])
    rehashed = made | {"new_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    verdict = verify_output("generate_incidents", given, rehashed, tmp_path)
    assert verdict["valid"] is False and "resolution" in verdict["message"]


# read_incident


def test_approves_and_refuses_read_incident(tmp_path: Path) -> None:
    _, made = generated(tmp_path, count=50)
    given, record = read(tmp_path, made["incidents_file"], "INC-00010")
    assert verify_output("read_incident", given, record, tmp_path)["valid"] is True
    for field in ("service", "summary", "resolution"):
        verdict = verify_output("read_incident", given, record | {field: "other"}, tmp_path)
        assert verdict["valid"] is False and field in verdict["message"]
    assert verify_output("read_incident", given, record | {"id": "INC-00011"}, tmp_path)["valid"] is False
    absent = given | {"id": "INC-09999"}
    assert "no incident" in verify_output("read_incident", absent, record | {"id": "INC-09999"}, tmp_path)["message"]


# find_similar


def new_summary(workspace: Path, made: dict, new_id: str = "NEW-1") -> str:
    return read(workspace, made["new_file"], new_id)[1]["summary"]


@pytest.mark.parametrize(
    ("threshold", "num_perm", "bands"),
    [(0.2, 128, 32), (0.0, 16, 16), (1.0, 16, 1), (0.5, 256, 64), (0.3, 64, 8)],
)
def test_approves_a_correct_similarity_search(tmp_path: Path, threshold, num_perm, bands) -> None:
    _, made = generated(tmp_path)
    given, found = similar(tmp_path, made["incidents_file"], new_summary(tmp_path, made), threshold, num_perm, bands)
    assert verify_output("find_similar", given, found, tmp_path)["valid"] is True
    assert verify_task("find-similar-incidents", given, found, tmp_path)["valid"] is True


def test_an_empty_result_is_valid_and_an_invented_match_is_not(tmp_path: Path) -> None:
    _, made = generated(tmp_path, count=50)
    given, found = similar(tmp_path, made["incidents_file"], "zebra quantum lattice harmonica", 0.2, 16, 1)
    assert found["candidates_checked"] == 0 and found["matches"] == []
    assert verify_output("find_similar", given, found, tmp_path)["valid"] is True
    invented = found | {"matches": [{"id": "INC-00001", "jaccard": 0.5}]}
    assert verify_output("find_similar", given, invented, tmp_path)["valid"] is False


def test_refuses_a_wrong_similarity_search(tmp_path: Path) -> None:
    _, made = generated(tmp_path)
    given, found = similar(tmp_path, made["incidents_file"], new_summary(tmp_path, made), 0.2, 16, 16)
    assert len(found["matches"]) >= 2
    first, second = found["matches"][0], found["matches"][1]
    cases = {
        "missing": (found | {"matches": found["matches"][1:]}, "matches are not"),
        "rounded wrong": (
            found | {"matches": [first | {"jaccard": first["jaccard"] + 0.0001}, *found["matches"][1:]]},
            "matches are not",
        ),
        "unrounded": (
            found | {"matches": [first | {"jaccard": first["jaccard"] + 0.00001}, *found["matches"][1:]]},
            "matches are not",
        ),
        "extra": (found | {"matches": [*found["matches"], {"id": "INC-00200", "jaccard": 0.01}]}, "matches are not"),
        "duplicated": (found | {"matches": [first, *found["matches"]]}, "twice"),
        "order": (found | {"matches": [second, first, *found["matches"][2:]]}, "ordered"),
        "candidates": (found | {"candidates_checked": found["candidates_checked"] + 1}, "candidates_checked"),
        "rows": (found | {"rows": 8}, "not the one asked for"),
        "echo": (found | {"threshold": 0.3}, "not the one asked for"),
    }
    for name, (output, message) in cases.items():
        verdict = verify_output("find_similar", given, output, tmp_path)
        assert verdict["valid"] is False and message in verdict["message"], name


def test_threshold_edges_and_ties_are_exact(tmp_path: Path) -> None:
    base = "alpha beta gamma delta epsilon zeta eta theta"
    # Shingle sets of size 6: a copy (J = 1), one with the last word changed (J = 5/7), and two identical ones.
    records = [
        incident("INC-00001", base),
        incident("INC-00002", base.replace("theta", "iota")),
        incident("INC-00003", "one two three four five six seven eight"),
        incident("INC-00004", "one two three four five six seven eight"),
    ]
    write_jsonl(tmp_path / "corpus.jsonl", records)
    given, found = similar(tmp_path, "corpus.jsonl", base, threshold=5 / 7, num_perm=16, bands=16)
    assert [(m["id"], m["jaccard"]) for m in found["matches"]] == [("INC-00001", 1.0), ("INC-00002", 0.7143)]
    assert verify_output("find_similar", given, found, tmp_path)["valid"] is True
    given, found = similar(tmp_path, "corpus.jsonl", "one two three four five six seven eight", 1.0, 16, 4)
    assert [m["id"] for m in found["matches"]] == ["INC-00003", "INC-00004"]
    assert verify_output("find_similar", given, found, tmp_path)["valid"] is True
    swapped = found | {"matches": found["matches"][::-1]}
    assert "ordered" in verify_output("find_similar", given, swapped, tmp_path)["message"]


def test_recall_check_flags_a_near_duplicate_missing_with_its_candidacy(tmp_path: Path) -> None:
    _, made = generated(tmp_path)
    text = read(tmp_path, made["incidents_file"], "INC-00005")[1]["summary"]
    given, found = similar(tmp_path, made["incidents_file"], text, 0.2)
    dropped = found | {
        "candidates_checked": found["candidates_checked"] - 1,
        "matches": [m for m in found["matches"] if m["id"] != "INC-00005"],
    }
    problems = verify_output("find_similar", given, dropped, tmp_path)["details"]["problems"]
    assert any("certainty" in problem and "INC-00005" in problem for problem in problems)


def test_refuses_a_malformed_or_missing_corpus(tmp_path: Path) -> None:
    given = {"file": "bad.jsonl", "text": "disk full", "threshold": 0.2, "num_perm": 16, "bands": 4}
    made = {k: given[k] for k in ("file", "threshold", "num_perm", "bands")} | {
        "rows": 4,
        "candidates_checked": 0,
        "matches": [],
    }
    (tmp_path / "bad.jsonl").write_text("not json\n")
    assert "not JSON" in verify_output("find_similar", given, made, tmp_path)["message"]
    write_jsonl(tmp_path / "bad.jsonl", [incident("INC-00001", "a b c"), incident("INC-00001", "d e f")])
    assert "twice" in verify_output("find_similar", given, made, tmp_path)["message"]
    write_jsonl(tmp_path / "bad.jsonl", [incident("INC-00001", "a b c") | {"resolution": 3}])
    assert "not a string" in verify_output("find_similar", given, made, tmp_path)["message"]
    (tmp_path / "bad.jsonl").unlink()
    assert "not in the workspace" in verify_output("find_similar", given, made, tmp_path)["message"]


def test_checks_what_the_types_cannot_say() -> None:
    good = {"file": "incidents/i.jsonl", "text": "disk full", "threshold": 0.2, "num_perm": 128, "bands": 32}
    assert verify_input("find_similar", good)["valid"] is True
    for edge in ({"threshold": 0.0}, {"threshold": 1.0}, {"num_perm": 16, "bands": 16}, {"num_perm": 256, "bands": 1}):
        assert verify_input("find_similar", good | edge)["valid"] is True, edge
    for bad in (
        {"threshold": -0.01},
        {"threshold": 1.01},
        {"num_perm": 15, "bands": 5},
        {"num_perm": 257, "bands": 1},
        {"bands": 3},
        {"bands": 0},
        {"text": " -- "},
        {"file": "../i.jsonl"},
        {"file": "i.csv"},
    ):
        assert verify_input("find_similar", good | bad)["valid"] is False, bad
    generate = {"seed": 1, "count": 50, "destination": "incidents"}
    assert verify_input("generate_incidents", generate)["valid"] is True
    assert verify_input("generate_incidents", generate | {"count": 2000})["valid"] is True
    for bad in ({"count": 49}, {"count": 2001}, {"destination": "/abs"}, {"destination": "../x"}):
        assert verify_input("generate_incidents", generate | bad)["valid"] is False, bad
    assert verify_input("read_incident", {"file": "incidents/i.jsonl", "id": "NEW-1"})["valid"] is True
    assert verify_input("read_incident", {"file": "incidents/i.jsonl", "id": " "})["valid"] is False
    assert verify_input("read_incident", {"file": "/i.jsonl", "id": "NEW-1"})["valid"] is False


# link-new-incident


def link(workspace: Path, seed: int = 3, count: int = 200, new_id: str = "NEW-1") -> tuple[dict, dict]:
    """What a correct agent submits: generate, read the new incident, search, read the top match."""
    _, made = generated(workspace, seed, count)
    _, new = read(workspace, made["new_file"], new_id)
    _, found = similar(workspace, made["incidents_file"], new["summary"], 0.2, 128, 32)
    top = found["matches"][0]
    _, past = read(workspace, made["incidents_file"], top["id"])
    output = {
        "incidents_file": made["incidents_file"],
        "new_id": new_id,
        "match_id": top["id"],
        "jaccard": top["jaccard"],
        "resolution": past["resolution"],
    }
    return {"seed": seed, "count": count, "new_id": new_id}, output


@pytest.mark.parametrize(("seed", "count", "new_id"), [(3, 200, "NEW-1"), (1, 50, "NEW-5"), (9, 200, "NEW-3")])
def test_approves_the_right_link(tmp_path: Path, seed: int, count: int, new_id: str) -> None:
    arguments, output = link(tmp_path, seed, count, new_id)
    verdict = verify_task("link-new-incident", arguments, output, tmp_path)
    assert verdict["valid"] is True and verdict["score"] == 1.0
    assert verdict["details"]["best_matches"] == [output["match_id"]]
    assert verdict["details"]["best_jaccard"] - verdict["details"]["runner_up_jaccard"] > 0.3


@pytest.mark.parametrize(
    ("changes", "failed"),
    [
        ({"new_id": "NEW-2"}, ["new_id"]),
        # Another incident is not the best match, so its id, similarity and fix are all wrong.
        (
            {"match_id": "INC-00001", "jaccard": 0.1, "resolution": "Restarted it."},
            ["match_id", "jaccard", "resolution"],
        ),
        ({"jaccard": 0.5}, ["jaccard"]),
        ({"resolution": "Restarted it."}, ["resolution"]),
    ],
)
def test_refuses_a_wrong_link_and_scores_what_is_right(tmp_path: Path, changes: dict, failed: list) -> None:
    arguments, output = link(tmp_path)
    verdict = verify_task("link-new-incident", arguments, output | changes, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["failed"] == failed
    assert verdict["score"] == (4 - len(failed)) / 4


def test_a_wrong_match_with_its_own_fix_still_fails_resolution(tmp_path: Path) -> None:
    arguments, output = link(tmp_path)
    other = "INC-00002" if output["match_id"] != "INC-00002" else "INC-00003"
    _, record = read(tmp_path, output["incidents_file"], other)
    wrong = output | {"match_id": other, "resolution": record["resolution"]}
    verdict = verify_task("link-new-incident", arguments, wrong, tmp_path)
    assert verdict["details"]["failed"] == ["match_id", "resolution"] and verdict["score"] == 0.5


def test_refuses_a_link_from_another_history_or_none(tmp_path: Path) -> None:
    arguments, output = link(tmp_path)
    verdict = verify_task("link-new-incident", arguments | {"seed": 4}, output, tmp_path)
    assert "not the seed's history" in verdict["message"]
    (tmp_path / "incidents" / "new-3-200.jsonl").write_text("")
    assert "no incident NEW-1" in verify_task("link-new-incident", arguments, output, tmp_path)["message"]
    (tmp_path / output["incidents_file"]).unlink()
    assert "not in the workspace" in verify_task("link-new-incident", arguments, output, tmp_path)["message"]


def test_a_tie_accepts_either_match(tmp_path: Path) -> None:
    summary = "disk filled up on the postgres primary after a schema migration"
    write_jsonl(
        tmp_path / "incidents" / "incidents-0-50.jsonl",
        [incident("INC-00001", summary, "Grew the volume."), incident("INC-00002", summary, "Pruned the logs.")]
        + [incident(f"INC-{i:05d}", f"unrelated note number {i} about cats") for i in range(3, 51)],
    )
    write_jsonl(tmp_path / "incidents" / "new-0-50.jsonl", [incident("NEW-1", summary + " again", "")])
    arguments = {"seed": 0, "count": 50, "new_id": "NEW-1"}
    jaccard = round(9 / 10, 4)
    for match_id, resolution in (("INC-00001", "Grew the volume."), ("INC-00002", "Pruned the logs.")):
        output = {
            "incidents_file": "incidents/incidents-0-50.jsonl",
            "new_id": "NEW-1",
            "match_id": match_id,
            "jaccard": jaccard,
            "resolution": resolution,
        }
        assert verify_task("link-new-incident", arguments, output, tmp_path)["valid"] is True
    crossed = output | {"resolution": "Grew the volume."}
    assert verify_task("link-new-incident", arguments, crossed, tmp_path)["details"]["failed"] == ["resolution"]
