# Triage Similar Incidents

A `nanoagent.plugin/v0001` plugin for incident triage. It writes a seeded
history of past incidents and a few new ones, then finds the past incidents
whose summaries nearly repeat a new one, with MinHash signatures and
locality-sensitive hashing (LSH) banding. A responder who gets paged can see
which past incident looks the same and read how it was fixed.

## Tools

| Tool | Does | Code |
|---|---|---|
| `generate_incidents` | Writes the past incidents for a seed and count to `<destination>/incidents-<seed>-<count>.jsonl` and 5 new incidents to `<destination>/new-<seed>-<count>.jsonl`, and returns both paths, the count and both SHA-256 hashes | `src/plugin/incidents.py` |
| `read_incident` | Returns one incident's service, summary and resolution from an incident file, by id | `src/plugin/incidents.py` |
| `find_similar` | MinHash and LSH over word 3-grams: every past incident that shares a band with the text and whose exact Jaccard is at least the threshold | `src/plugin/similar.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `generate-incidents` | Generates a seeded incident history | `tool`, with `generate_incidents` |
| `find-similar-incidents` | Finds the past incidents similar to a text | `tool`, with `find_similar` |
| `link-new-incident` | Links a new incident to its closest past incident and returns how that one was resolved | `agent`, with `generate_incidents`, `read_incident` and `find_similar` |

Each line of an incident file is a JSON object with the string keys `id`,
`service`, `summary` and `resolution`. Past incidents are `INC-00001`
onward; new ones are `NEW-1` to `NEW-5` and have an empty resolution.
Summaries hold 30 to 60 words drawn from a bank of symptoms, causes and
components, so unrelated incidents share many words but few 3-word runs.
Each new incident is one seed-chosen past incident with about 12% of its
words replaced at its start and end. Each also has one or two decoys: past
incidents that keep the start and end of its source but have a different
middle. Over seeds 1 to 10 with 200 and 2000 incidents, every new incident's
source has a Jaccard similarity between 0.74 and 0.82, every runner-up is at
least 0.39 below it, and `find_similar` with threshold 0.2, num_perm 128 and
bands 32 returns the source first. The same seed and count always give the
same bytes.

### How find_similar works

- **Shingles.** The words of a text are `re.findall(r"[a-z0-9]+", text.lower())`.
  Its shingles are the set of each 3 consecutive words joined by a space. A
  text of 1 or 2 words is one shingle of all its words; a text with no words
  is refused.
- **MinHash.** Value `i` of a signature, for `i` in `0 .. num_perm - 1`, is the
  least `int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8, salt=i.to_bytes(8, "big")).digest(), "big")`
  over the set's shingles.
- **LSH.** The signature is cut into `bands` bands of `rows = num_perm / bands`
  consecutive values. A past incident is a candidate when any of its band
  tuples equals the text's band tuple at the same position.
- **Matches.** `candidates_checked` counts the candidates. A candidate is a
  match when its exact Jaccard similarity with the text's shingles is at
  least `threshold`; it is reported rounded to 4 places, highest first, ties
  by id.

An incident with Jaccard `J` shares a given band with probability `J^rows`,
so LSH misses it with probability `(1 - J^rows)^bands`. With 128 values in 32
bands of 4, a near-duplicate at 0.74 is missed with probability about
`1.2e-5`, and an unrelated incident at 0.1 becomes a candidate with
probability about 0.3%.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # needed environment variable names (none here)
├── src/plugin/      # the MCP server (__main__.py, its IMPLEMENTATIONS table) and the tools
├── tests/
├── ui/              # outputs are drawn from their JSON Schema
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier, one module per tool, and link.py for link-new-incident
```

`verifier/` imports only the standard library and `contract`. It reads the
files back from the workspace and recomputes every shingle set, signature
and similarity itself with `hashlib`, then checks:

- `generate_incidents`: both files are at the paths the seed and count name,
  their SHA-256 hashes are the declared ones, the past incidents are
  `INC-00001` to the count in order with resolutions, the new ones are
  `NEW-1` to `NEW-5` with empty resolutions, and every summary has 30 to 60
  words.
- `read_incident`: the id is in the file, and the service, summary and
  resolution are the record's own.
- `find_similar`: the settings and `rows` are echoed; `candidates_checked` is
  the exact number of incidents that share a band; the matches are exactly
  the candidates at or above the threshold, with their Jaccard rounded to 4
  places, listed once each, highest first, ties by id. As a recall check,
  every incident at or above the threshold that LSH would miss with
  probability below `1e-6` must be listed.
- `link-new-incident`: the file is the seed's history, then four named
  checks. `new_id` echoes the input and exists in the new file; `match_id`
  has the highest exact Jaccard over the whole history (any of them on a
  tie); `jaccard` equals that best value rounded to 4 places; and
  `resolution` is the matched incident's resolution in the file. The score is
  the share of these four checks that pass, and `details.failed` names the
  ones that did not.

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

NanoAgent passes the folder the plugin may write to as `NANOAGENT_WORKSPACE`.
Incident files are written there; `read_incident` and `find_similar` read a
file by its path inside it.
