"""generate_incidents and read_incident: a seeded incident history with planted near-duplicates."""

import hashlib
import json
import random
import re
from pathlib import Path

from contract import GenerateInput, GenerateOutput, ReadInput, ReadOutput

MIN_COUNT, MAX_COUNT = 50, 2000
NEW_INCIDENTS = 5
KEYS = ["id", "service", "summary", "resolution"]
MIN_WORDS, MAX_WORDS = 30, 60

SERVICES = [
    "checkout-api",
    "payments-gateway",
    "auth-service",
    "search-indexer",
    "inventory-db",
    "notification-worker",
    "user-profile",
    "order-queue",
    "cdn-edge",
    "billing-batch",
    "recommendation-engine",
    "shipping-tracker",
]
COMPONENTS = [
    "redis cache",
    "postgres primary",
    "kafka consumer",
    "nginx ingress",
    "grpc gateway",
    "object store",
    "dns resolver",
    "jvm heap",
    "connection pool",
    "load balancer",
    "elasticsearch cluster",
    "rabbitmq broker",
    "memcached tier",
    "etcd quorum",
    "service mesh sidecar",
    "cron scheduler",
    "tls terminator",
    "feature flag service",
    "rate limiter",
    "read replica",
    "session store",
    "image resizer",
    "webhook dispatcher",
    "batch exporter",
]
SYMPTOMS = [
    "latency spiked",
    "error rate climbed",
    "requests timed out",
    "pods crash looped",
    "disk filled up",
    "memory kept growing",
    "the queue backed up",
    "health checks failed",
    "throughput dropped",
    "cpu saturated",
    "connections were refused",
    "replication lagged",
    "writes stalled",
    "gateway errors surged",
    "logins started failing",
    "jobs stopped draining",
    "cache hit ratio collapsed",
    "file descriptors ran out",
    "garbage collection paused",
    "responses came back empty",
]
CAUSES = [
    "a bad config push",
    "an expired certificate",
    "a schema migration",
    "a noisy neighbor",
    "a retry storm",
    "a stale cache key",
    "an unindexed query",
    "a dependency upgrade",
    "a network partition",
    "a runaway cron job",
    "a thundering herd",
    "a leaked file handle",
    "a misrouted canary",
    "a full inode table",
    "clock skew",
    "a hot partition",
    "a missing timeout",
    "an oversized payload",
    "a deadlock",
    "a quota limit",
]
METRICS = ["p99 latency", "error budget burn", "queue depth", "heap usage", "open connections", "retry count"]
UNITS = ["ms", "percent", "messages", "megabytes", "sockets", "calls"]
AUDIENCES = ["shoppers", "mobile users", "partners", "internal tools", "admins", "api clients", "new signups"]
EFFECTS = [
    "failed checkouts",
    "slow page loads",
    "duplicate emails",
    "missing orders",
    "login loops",
    "stale prices",
    "blank dashboards",
    "dropped webhooks",
]
REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-south-1", "ap-northeast-1", "sa-east-1"]
HOST_PREFIXES = ["web", "api", "db", "worker", "cache", "edge", "batch", "mq"]
ERRCODES = ["econnreset", "etimedout", "oom killed", "deadline exceeded", "too many open files", "broken pipe"]
TEAMS = ["platform", "payments", "storage", "edge", "identity", "data", "sre"]
TABLES = ["orders", "sessions", "carts", "invoices", "events", "users"]
# Words a new incident's report swaps in at its start and end.
FILLER = [
    "update",
    "again",
    "reopened",
    "customer",
    "flagged",
    "today",
    "still",
    "seeing",
    "similar",
    "noted",
    "followup",
    "pager",
    "escalated",
    "overnight",
    "weekend",
    "shift",
    "reported",
    "ongoing",
    "repeat",
    "maybe",
]


def safe_folder(destination: str) -> Path:
    path = Path(destination)
    if not destination.strip() or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"destination {destination!r} must be a folder inside the plugin workspace")
    return path


def incidents_name(seed: int, count: int) -> str:
    return f"incidents-{seed}-{count}.jsonl"


def new_name(seed: int, count: int) -> str:
    return f"new-{seed}-{count}.jsonl"


def word_count(text: str) -> int:
    """Words as find_similar splits them: runs of lowercase letters and digits."""
    return len(re.findall(r"[a-z0-9]+", text.lower()))


def _host(rng: random.Random) -> str:
    return f"{rng.choice(HOST_PREFIXES)}-{rng.randrange(1, 64)}"


def _clauses(rng: random.Random, service: str) -> list[str]:
    """One incident's sentences: an opening, then details in a seeded order."""
    pick = rng.choice
    openings = [
        f"{service} paged at {rng.randrange(24):02d}:{rng.randrange(60):02d} utc when {pick(SYMPTOMS)} on {_host(rng)}",
        f"on call saw {pick(SYMPTOMS)} in {pick(REGIONS)} for {service}",
        f"alert fired for {service} because {pick(SYMPTOMS)} across {rng.randrange(2, 40)} hosts",
    ]
    details = [
        f"the {pick(COMPONENTS)} reported {pick(METRICS)} of {rng.randrange(50, 9000)} {pick(UNITS)}",
        f"dashboards showed {pick(METRICS)} near {rng.randrange(50, 9000)} {pick(UNITS)} on {pick(COMPONENTS)}",
        f"{pick(COMPONENTS)} logs listed {rng.randrange(10, 5000)} errors like {pick(ERRCODES)} from {_host(rng)}",
        f"root cause looked like {pick(CAUSES)} touching the {pick(COMPONENTS)}",
        f"investigation pointed to {pick(CAUSES)} after deploy {rng.randrange(1000, 9999)}",
        f"we traced it to {pick(CAUSES)} in {pick(COMPONENTS)}",
        f"about {rng.randrange(2, 90)} percent of {pick(AUDIENCES)} saw {pick(EFFECTS)}",
        f"{pick(AUDIENCES)} in {pick(REGIONS)} hit {pick(EFFECTS)} for {rng.randrange(3, 240)} minutes",
        f"a second wave where {pick(SYMPTOMS)} followed on {_host(rng)}",
        f"retries made {pick(COMPONENTS)} worse until traffic shifted to {pick(REGIONS)}",
        f"{pick(TEAMS)} team joined while {pick(SYMPTOMS)} near {pick(COMPONENTS)}",
    ]
    rng.shuffle(details)
    return [pick(openings), *details]


def _summary(rng: random.Random, service: str) -> str:
    clauses = _clauses(rng, service)
    target = rng.randint(MIN_WORDS + 4, MAX_WORDS - 6)
    words: list[str] = []
    for clause in clauses:
        if len(words) >= target:
            break
        words += clause.split()
    while word_count(" ".join(words)) > MAX_WORDS:
        words.pop()
    return " ".join(words)


def _resolution(rng: random.Random, service: str) -> str:
    pick = rng.choice
    actions = [
        f"rolled back deploy {rng.randrange(1000, 9999)}",
        f"raised the {pick(COMPONENTS)} limit to {rng.randrange(64, 4096)}",
        f"added an index on {pick(TABLES)}.{pick(['created_at', 'user_id', 'status', 'region'])}",
        f"drained {_host(rng)} and replaced it",
        f"flushed the {pick(COMPONENTS)}",
        f"disabled flag {pick(['fast-path', 'new-pricing', 'async-write', 'v2-router', 'bulk-sync'])}",
        f"scaled {service} to {rng.randrange(4, 80)} replicas",
        f"restarted the {pick(COMPONENTS)}",
        f"renewed the certificate for {pick(REGIONS)}",
        f"capped retries at {rng.randrange(2, 9)} with jitter",
    ]
    first, second = rng.sample(actions, 2)
    return (
        f"{first[0].upper()}{first[1:]}, then {second}. Closed by {pick(TEAMS)} after {rng.randrange(8, 300)} minutes."
    )


def _replace_middle(rng: random.Random, words: list[str], filler: list[str]) -> list[str]:
    """A decoy: the opening 35% and closing 25% kept, the middle swapped for another incident's words."""
    head, tail = round(0.35 * len(words)), round(0.25 * len(words))
    middle = len(words) - head - tail
    start = rng.randrange(0, max(1, len(filler) - middle))
    swapped = filler[start : start + middle]
    while swapped and word_count(" ".join(words[:head] + swapped + words[len(words) - tail :])) > MAX_WORDS:
        swapped.pop()
    return words[:head] + swapped + words[len(words) - tail :]


def _perturb(rng: random.Random, words: list[str]) -> list[str]:
    """A new report of a past incident: about 12% of its words, split between its start and end, replaced."""
    changed = max(4, round(0.12 * len(words)))
    front, back = (changed + 1) // 2, changed // 2
    fresh = rng.sample(FILLER, changed)
    return fresh[:front] + words[front : len(words) - back] + fresh[front:]


def build(seed: int, count: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rng = random.Random(seed)
    past = []
    for index in range(count):
        service = rng.choice(SERVICES)
        past.append(
            {
                "id": f"INC-{index + 1:05d}",
                "service": service,
                "summary": _summary(rng, service),
                "resolution": _resolution(rng, service),
            }
        )
    order = rng.sample(range(count), count)
    targets, spare = order[:NEW_INCIDENTS], order[NEW_INCIDENTS:]
    new = []
    for number, target in enumerate(targets, start=1):
        source = past[target]
        words = source["summary"].split()
        for _ in range(rng.choice([1, 2])):
            decoy = past[spare.pop()]
            filler = (_summary(rng, source["service"]) + " " + _summary(rng, source["service"])).split()
            decoy["service"] = source["service"]
            decoy["summary"] = " ".join(_replace_middle(rng, words, filler))
        new.append(
            {
                "id": f"NEW-{number}",
                "service": source["service"],
                "summary": " ".join(_perturb(rng, words)),
                "resolution": "",
            }
        )
    return past, new


def _jsonl(records: list[dict[str, str]]) -> bytes:
    return "".join(json.dumps(record) + "\n" for record in records).encode("utf-8")


def generate_incidents(given: GenerateInput, workspace: Path) -> GenerateOutput:
    if not MIN_COUNT <= given.count <= MAX_COUNT:
        raise ValueError(f"count must be between {MIN_COUNT} and {MAX_COUNT}, got {given.count}")
    folder = safe_folder(given.destination)
    past, new = build(given.seed, given.count)
    files = {}
    for name, records in ((incidents_name(given.seed, given.count), past), (new_name(given.seed, given.count), new)):
        data = _jsonl(records)
        target = workspace / folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[name] = ((folder / name).as_posix(), hashlib.sha256(data).hexdigest())
    (incidents_file, sha256), (new_file, new_sha256) = files.values()
    return GenerateOutput(
        incidents_file=incidents_file,
        new_file=new_file,
        count=given.count,
        sha256=sha256,
        new_sha256=new_sha256,
    )


def read_records(workspace: Path, file: str) -> list[dict[str, str]]:
    """Every record of an incident file, or an error saying why it is not one."""
    path = Path(file)
    if not file.strip() or path.is_absolute() or ".." in path.parts or path.suffix != ".jsonl":
        raise ValueError(f"file {file!r} must be a .jsonl inside the plugin workspace")
    target = workspace / path
    if not target.is_file():
        raise FileNotFoundError(f"{file} is not in the workspace: generate it with generate_incidents first")
    records, seen = [], set()
    for number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{file} line {number} is not JSON") from error
        if not isinstance(record, dict) or list(record) != KEYS or not all(isinstance(v, str) for v in record.values()):
            raise ValueError(f"{file} line {number} does not hold the string keys {', '.join(KEYS)}")
        if record["id"] in seen:
            raise ValueError(f"{file} lists {record['id']} twice")
        seen.add(record["id"])
        records.append(record)
    return records


def read_incident(given: ReadInput, workspace: Path) -> ReadOutput:
    for record in read_records(workspace, given.file):
        if record["id"] == given.id:
            return ReadOutput(
                file=given.file,
                id=given.id,
                service=record["service"],
                summary=record["summary"],
                resolution=record["resolution"],
            )
    raise ValueError(f"{given.file} has no incident {given.id!r}")
