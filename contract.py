"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GENERATE_INCIDENTS = "generate_incidents"
    READ_INCIDENT = "read_incident"
    FIND_SIMILAR = "find_similar"


class Task(Enum):
    GENERATE_INCIDENTS = "generate-incidents"
    FIND_SIMILAR_INCIDENTS = "find-similar-incidents"
    LINK_NEW_INCIDENT = "link-new-incident"


class NewIncident(Enum):
    NEW_1 = "NEW-1"
    NEW_2 = "NEW-2"
    NEW_3 = "NEW-3"
    NEW_4 = "NEW-4"
    NEW_5 = "NEW-5"


SEED = "The scenario's seed: the same seed and count always give the same files, byte for byte"
COUNT = "How many past incidents the history holds, 50 to 2000"
DESTINATION = "The folder relative to the plugin workspace the files are saved in, e.g. incidents"
INCIDENTS_FILE = "The past incidents, relative to the plugin workspace: <destination>/incidents-<seed>-<count>.jsonl"
INCIDENT_FILE = "An incident JSONL file relative to the plugin workspace, e.g. incidents/incidents-7-2000.jsonl"
SHA256 = "The SHA-256 of the file's bytes, lowercase hex"


@dataclass
class GenerateInput(Output):
    seed: Annotated[int, SEED]
    count: Annotated[int, COUNT]
    destination: Annotated[str, DESTINATION]


@dataclass
class GenerateOutput(Output):
    incidents_file: Annotated[str, INCIDENTS_FILE]
    new_file: Annotated[
        str, "The 5 new incidents NEW-1 to NEW-5, with empty resolutions: <destination>/new-<seed>-<count>.jsonl"
    ]
    count: Annotated[int, "How many past incidents the incidents file holds"]
    sha256: Annotated[str, "The SHA-256 of the incidents file's bytes, lowercase hex"]
    new_sha256: Annotated[str, "The SHA-256 of the new incidents file's bytes, lowercase hex"]


@dataclass
class ReadInput(Output):
    file: Annotated[str, INCIDENT_FILE]
    id: Annotated[str, "The incident's id, such as INC-00042 or NEW-3"]


@dataclass
class ReadOutput(Output):
    file: Annotated[str, "The file, as given"]
    id: Annotated[str, "The id, as given"]
    service: Annotated[str, "The service the incident hit"]
    summary: Annotated[str, "What happened, in 30 to 60 words"]
    resolution: Annotated[str, "How it was fixed; empty for a new incident"]


@dataclass
class SimilarInput(Output):
    file: Annotated[str, "The past incidents to search, relative to the plugin workspace"]
    text: Annotated[str, "The text to match, such as a new incident's summary; it must hold at least one word"]
    threshold: Annotated[float, "The least exact Jaccard similarity of word 3-gram sets a match may have, 0 to 1"]
    num_perm: Annotated[int, "How many MinHash values each signature holds, 16 to 256"]
    bands: Annotated[int, "How many LSH bands the signature is cut into; it must divide num_perm"]


@dataclass
class Match(Output):
    id: Annotated[str, "The past incident's id"]
    jaccard: Annotated[float, "The exact Jaccard similarity of its word 3-gram set to the text's, rounded to 4 places"]


@dataclass
class SimilarOutput(Output):
    file: Annotated[str, "The file, as given"]
    threshold: Annotated[float, "The threshold, as given"]
    num_perm: Annotated[int, "The signature length, as given"]
    bands: Annotated[int, "The band count, as given"]
    rows: Annotated[int, "How many MinHash values each band holds, num_perm / bands"]
    candidates_checked: Annotated[int, "How many past incidents share at least one LSH band with the text"]
    matches: Annotated[
        list[Match],
        "Every candidate whose exact Jaccard is at least the threshold, highest Jaccard first, ties by id",
    ]


@dataclass
class LinkInput(Output):
    seed: Annotated[int, SEED]
    count: Annotated[int, COUNT]
    new_id: Annotated[NewIncident, "The new incident to link to its past near-duplicate"]


@dataclass
class LinkOutput(Output):
    incidents_file: Annotated[
        str, "The past incidents generated for the seed and count, incidents/incidents-<seed>-<count>.jsonl"
    ]
    new_id: Annotated[NewIncident, "The new incident, as given"]
    match_id: Annotated[str, "The past incident most similar to the new one"]
    jaccard: Annotated[float, "Their exact Jaccard similarity, rounded to 4 places"]
    resolution: Annotated[str, "How the matched past incident was resolved, exactly as its record says"]


TOOLS = {
    Tool.GENERATE_INCIDENTS: (GenerateInput, GenerateOutput),
    Tool.READ_INCIDENT: (ReadInput, ReadOutput),
    Tool.FIND_SIMILAR: (SimilarInput, SimilarOutput),
}
TASKS = {
    Task.GENERATE_INCIDENTS: (GenerateInput, GenerateOutput),
    Task.FIND_SIMILAR_INCIDENTS: (SimilarInput, SimilarOutput),
    Task.LINK_NEW_INCIDENT: (LinkInput, LinkOutput),
}
