"""Retrieve the project's own documentation so architecture answers are real.

The repository ships the documentation that describes this system:
``README.md``, ``tech.md``, ``docs/*.md`` and the pipeline reports. Rather than
parroting a hand-written summary that will drift out of date, this module reads
those files, splits them into chunks, and retrieves only the chunks relevant to
the question.

Two things keep it cheap and safe:

* **Cached and lazy.** The index is built on first use and reused.
* **Bounded.** At most ``MAX_CHUNKS`` chunks of at most ``MAX_CHARS`` each are
  ever put in a prompt, so a long architecture question cannot dump the whole
  repository into the model.

Files are read from the repository, never from the request, so nothing the user
types can steer a path lookup.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: Documentation the assistant is allowed to read, in retrieval-priority order.
#: Explicit allow-list: a stray markdown file in the repo cannot be indexed.
DOC_FILES: tuple[tuple[str, str], ...] = (
    ("README.md", "Project overview and features"),
    ("docs/architecture.md", "System architecture, layers, data flow"),
    ("docs/api.md", "API endpoints and their contracts"),
    ("docs/navigation.md", "Route generation, risk scoring, voyage simulation"),
    ("docs/datasets.md", "Datasets, sources, licensing and preprocessing"),
    ("docs/model_training.md", "Models, features, training and evaluation"),
    ("docs/limitations.md", "Known limitations and honest caveats"),
    ("docs/demo.md", "Demo mode and synthetic data"),
    ("docs/PRODUCTION_READINESS.md", "Deployment and production status"),
    ("tech.md", "Technology stack"),
    ("Real data/README.md", "Real data acquisition and layout"),
    ("reports/dataset_inventory.md", "Dataset inventory and classification"),
    ("reports/real_model_accuracy_report.md", "Measured model accuracy"),
    ("reports/pipeline_report.md", "Data pipeline stages"),
    ("reports/quality_control_report.md", "Data quality control"),
)

#: Prompt budget. Architecture answers stay readable and cheap.
MAX_CHUNKS = 5
MAX_CHARS = 2200
MIN_SCORE = 2

#: Stop words that must not create keyword matches on their own. Includes the
#: question-framing verbs people use when talking to an assistant, which carry
#: no topical signal but would otherwise match half the documentation.
_STOP = frozenset("""
a an and app application are as at be by can could did do does for from get
give go has have help how i in into is it its just know let like make me my
need of on or our please project really say show some than that the their
them then there these they thing things this to up us use used using want was
were what when where which who why will with would you your
explain describe current actually stuff right going happen happens
system systems work works working
""".split())


def _repo_root() -> Path:
    # .../<repo>/backend/assistant/docs_index.py -> <repo>
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Chunk:
    """One retrievable slice of a documentation file."""

    source: str
    title: str
    text: str
    terms: frozenset[str]


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) sections."""
    sections: list[tuple[str, str]] = []
    heading = "Overview"
    buffer: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,4})\s+(.*)$", line)
        if match:
            if buffer and "".join(buffer).strip():
                sections.append((heading, "\n".join(buffer).strip()))
            heading = match.group(2).strip()
            buffer = []
        else:
            buffer.append(line)
    if buffer and "".join(buffer).strip():
        sections.append((heading, "\n".join(buffer).strip()))
    return sections


def _terms(text: str) -> frozenset[str]:
    return frozenset(
        word for word in re.findall(r"[a-z0-9_]{3,}", text.lower())
        if word not in _STOP
    )


@lru_cache(maxsize=1)
def _index() -> tuple[Chunk, ...]:
    root = _repo_root()
    chunks: list[Chunk] = []
    for relative, description in DOC_FILES:
        path = root / relative
        try:
            # "utf-8-sig" strips the byte-order mark some of these files carry;
            # leaving it in would put an invisible character in the answer.
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        # Skip fenced code: endpoint tables and prose matter, code blocks
        # mostly waste the prompt budget.
        text = re.sub(r"```.*?```", " ", text, flags=re.S)
        for heading, body in _split_sections(text):
            body = body.strip()
            if len(body) < 40:
                continue
            if len(body) > MAX_CHARS * 3:
                body = body[: MAX_CHARS * 3] + "\n[...truncated...]"
            chunks.append(
                Chunk(
                    source=relative,
                    title=heading or description,
                    text=body,
                    terms=_terms(f"{heading} {body} {description} {Path(relative).stem}"),
                )
            )
    return tuple(chunks)


@lru_cache(maxsize=1)
def _idf() -> dict[str, float]:
    """Inverse document frequency, so 'route' matters less than 'dataset'."""
    chunks = _index()
    if not chunks:
        return {}
    total = len(chunks)
    document_frequency: dict[str, int] = {}
    for chunk in chunks:
        for term in chunk.terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1
    return {
        term: 1.0 + (total - count) / count
        for term, count in document_frequency.items()
    }


#: Pure social turns. These should never drag documentation into a prompt.
_GREETING = re.compile(
    r"^\s*(hi|hey|hello|yo|thanks|thank you|thx|ok|okay|cool|nice|great|good|"
    r"bye|goodbye|yes|no|yep|nope|sure|alright|how are you|whats up|what's up)\b[\s!.?]*$",
    re.IGNORECASE,
)


def available_sources() -> list[str]:
    """Which documentation files were actually indexed."""
    return sorted({chunk.source for chunk in _index()})


def _overview_chunks() -> list[Chunk]:
    """Generic project sections, used when a question has no topical words.

    "What is this project?" is almost all function words; returning nothing
    would leave the assistant unable to introduce its own system.
    """
    preferred = (
        ("README.md", "Overview"),
        ("docs/architecture.md", "Architecture"),
        ("tech.md", "Technology"),
    )
    fallback: list[Chunk] = []
    for source, title_prefix in preferred:
        for chunk in _index():
            if chunk.source == source and chunk.title.lower().startswith(title_prefix.lower()):
                fallback.append(chunk)
                break
    return fallback[:2]


def search(question: str, limit: int = MAX_CHUNKS) -> list[Chunk]:
    """Return the best-matching documentation chunks for a question.

    Scored by summed IDF, so a query word that only appears in one document
    ("kelp", "difficulty", "band") counts for much more than one that appears
    in all of them ("route", "data"). A question with no topical words at all
    falls back to the project overview.
    """
    query_terms = _terms(question)
    if _GREETING.match(question):
        return []
    if not query_terms:
        return _overview_chunks()[:limit]
    idf = _idf()
    # A question that names a document ("what datasets...") should land in that
    # document, even if the word is common inside it.
    source_boost = {
        Path(source).stem.lower() for source in {c.source for c in _index()}
    } & query_terms
    scored: list[tuple[float, Chunk]] = []
    for chunk in _index():
        overlap = query_terms & chunk.terms
        if not overlap:
            continue
        score = sum(idf.get(term, 1.0) for term in overlap)
        # Nudge sections whose own heading uses the user's words.
        title_terms = _terms(chunk.title)
        score += 1.5 * sum(idf.get(term, 1.0) for term in (overlap & title_terms))
        if Path(chunk.source).stem.lower() in source_boost:
            score += 6.0
        if score >= MIN_SCORE:
            scored.append((score, chunk))
    scored.sort(key=lambda item: -item[0])
    hits = [chunk for _, chunk in scored[:limit]]
    # A question with real words but no document coverage (alerts, for example,
    # are generated in the frontend and are deliberately undocumented) still
    # deserves an introduction to the system rather than silence.
    return hits or _overview_chunks()[:limit]


def render(question: str, limit: int = MAX_CHUNKS) -> tuple[str, list[str]]:
    """Documentation block for the prompt, plus the sources it came from."""
    hits = search(question, limit)
    if not hits:
        return "", []
    blocks: list[str] = []
    used: list[str] = []
    for chunk in hits:
        text = chunk.text
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n[...truncated...]"
        blocks.append(
            f"[docs: {chunk.source} - {chunk.title}]\n{text}"
        )
        used.append(f"{chunk.source}#{chunk.title}")
    return "\n\n".join(blocks), used


def render_block(question: str, limit: int = MAX_CHUNKS) -> str:
    """Documentation block only, for the offline composer."""
    body, _ = render(question, limit)
    if not body:
        return ""
    return (
        "From the project's own documentation:\n\n"
        f"{body}\n\n"
        "Quote these specifics rather than describing the system generically."
    )
