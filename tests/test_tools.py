import hashlib
import json
from pathlib import Path

import pytest

from contract import GenerateInput, ReadInput, SimilarInput
from plugin import find_similar, generate_incidents, read_incident
from plugin.incidents import build, word_count
from plugin.similar import jaccard, shingles, signatures


def generated(workspace: Path, seed: int = 3, count: int = 200):
    return generate_incidents(GenerateInput(seed=seed, count=count, destination="incidents"), workspace)


def similar(workspace: Path, file: str, text: str, threshold=0.2, num_perm=128, bands=32):
    given = SimilarInput(file=file, text=text, threshold=threshold, num_perm=num_perm, bands=bands)
    return find_similar(given, workspace)


def test_the_same_seed_gives_the_same_bytes(tmp_path: Path) -> None:
    first = generated(tmp_path)
    data = (tmp_path / first.incidents_file).read_bytes()
    second = generated(tmp_path)
    assert first == second and (tmp_path / second.incidents_file).read_bytes() == data
    assert first.incidents_file == "incidents/incidents-3-200.jsonl"
    assert first.new_file == "incidents/new-3-200.jsonl"
    assert first.sha256 == hashlib.sha256(data).hexdigest()
    assert generated(tmp_path, seed=4).sha256 != first.sha256


def test_records_have_the_documented_shape(tmp_path: Path) -> None:
    out = generated(tmp_path, count=50)
    past = [json.loads(line) for line in (tmp_path / out.incidents_file).read_text().splitlines()]
    new = [json.loads(line) for line in (tmp_path / out.new_file).read_text().splitlines()]
    assert [r["id"] for r in past] == [f"INC-{i:05d}" for i in range(1, 51)]
    assert [r["id"] for r in new] == ["NEW-1", "NEW-2", "NEW-3", "NEW-4", "NEW-5"]
    assert all(list(r) == ["id", "service", "summary", "resolution"] for r in past + new)
    assert all(r["resolution"] for r in past) and not any(r["resolution"] for r in new)
    assert all(30 <= word_count(r["summary"]) <= 60 for r in past + new)


@pytest.mark.parametrize(
    ("count", "destination"),
    [(49, "incidents"), (2001, "incidents"), (200, "../out"), (200, "/tmp/x"), (200, " ")],
)
def test_refuses_bad_generate_inputs(tmp_path: Path, count: int, destination: str) -> None:
    with pytest.raises(ValueError):
        generate_incidents(GenerateInput(seed=1, count=count, destination=destination), tmp_path)


def test_each_new_incident_has_one_clear_best_match() -> None:
    past, new = build(5, 200)
    for incident in new:
        query = shingles(incident["summary"])
        ranked = sorted((jaccard(query, shingles(r["summary"])) for r in past), reverse=True)
        assert ranked[0] > 0.7 and ranked[0] - ranked[1] > 0.3


def test_shingles_follow_the_spec() -> None:
    assert shingles("Disk FULL on db-1") == {"disk full on", "full on db", "on db 1"}
    assert shingles("Disk, full") == {"disk full"}
    assert shingles("disk") == {"disk"}
    with pytest.raises(ValueError):
        shingles("!!! ---")


def test_signatures_follow_the_spec() -> None:
    def spec(grams, num_perm):
        return [
            min(
                int.from_bytes(
                    hashlib.blake2b(g.encode(), digest_size=8, salt=i.to_bytes(8, "big")).digest(),
                    "big",
                )
                for g in grams
            )
            for i in range(num_perm)
        ]

    sets = [shingles("a b"), shingles("the quick brown fox jumps"), shingles("x y z w")]
    assert signatures(sets, 40) == [spec(grams, 40) for grams in sets]


def test_finds_the_planted_source_first(tmp_path: Path) -> None:
    out = generated(tmp_path)
    new = read_incident(ReadInput(file=out.new_file, id="NEW-2"), tmp_path)
    found = similar(tmp_path, out.incidents_file, new.summary)
    past, _ = build(3, 200)
    query = shingles(new.summary)
    best = max(past, key=lambda r: jaccard(query, shingles(r["summary"])))
    assert found.rows == 4 and found.matches[0].id == best["id"]
    assert [m.jaccard for m in found.matches] == sorted((m.jaccard for m in found.matches), reverse=True)


def test_an_identical_text_matches_at_one(tmp_path: Path) -> None:
    out = generated(tmp_path, count=50)
    record = read_incident(ReadInput(file=out.incidents_file, id="INC-00007"), tmp_path)
    found = similar(tmp_path, out.incidents_file, record.summary, threshold=1.0)
    assert [(m.id, m.jaccard) for m in found.matches] == [("INC-00007", 1.0)]


@pytest.mark.parametrize(
    ("threshold", "num_perm", "bands"),
    [(-0.1, 128, 32), (1.1, 128, 32), (0.2, 15, 15), (0.2, 257, 1), (0.2, 128, 3), (0.2, 128, 0)],
)
def test_refuses_bad_settings(tmp_path: Path, threshold, num_perm, bands) -> None:
    out = generated(tmp_path, count=50)
    with pytest.raises(ValueError):
        similar(tmp_path, out.incidents_file, "disk full", threshold, num_perm, bands)


def test_refuses_an_empty_text(tmp_path: Path) -> None:
    out = generated(tmp_path, count=50)
    with pytest.raises(ValueError):
        similar(tmp_path, out.incidents_file, "  ...  ")


def test_read_incident_refuses_an_absent_id_or_bad_file(tmp_path: Path) -> None:
    out = generated(tmp_path, count=50)
    assert read_incident(ReadInput(file=out.new_file, id="NEW-5"), tmp_path).resolution == ""
    with pytest.raises(ValueError):
        read_incident(ReadInput(file=out.incidents_file, id="INC-00051"), tmp_path)
    with pytest.raises(FileNotFoundError):
        read_incident(ReadInput(file="incidents/none.jsonl", id="INC-00001"), tmp_path)
    with pytest.raises(ValueError):
        read_incident(ReadInput(file="../outside.jsonl", id="INC-00001"), tmp_path)
    (tmp_path / "bad.jsonl").write_text('{"id": "INC-00001"}\n')
    with pytest.raises(ValueError):
        read_incident(ReadInput(file="bad.jsonl", id="INC-00001"), tmp_path)
    (tmp_path / "bad.jsonl").write_text("not json\n")
    with pytest.raises(ValueError):
        similar(tmp_path, "bad.jsonl", "disk full")
