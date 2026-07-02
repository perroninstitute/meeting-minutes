"""Turn a speaker-labelled transcript into RSST meeting minutes.

Runs entirely against a local Ollama server — the transcript never leaves the
machine. Short transcripts are summarised in one pass; long ones (e.g. a
full-hour meeting that won't fit a 7B model's context) are split into parts,
each summarised, then merged into one clean set of minutes.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request


SYSTEM_PROMPT = """You are a precise meeting-minutes assistant for a \
neurological institute. You turn raw, speaker-labelled transcripts into clear, \
factual minutes.

- Only state what the transcript supports. Never invent names, numbers, dates, \
dosages, or decisions.
- Keep clinical terms, drug names, and abbreviations spelled exactly as given.
- Attribute actions and decisions to the person who made them when it is clear.
- Write "[unclear]" for anything inaudible rather than guessing.
- Keep patient-identifying detail to the minimum needed for the minutes to be \
useful."""


# Single-pass: short transcript -> full minutes document.
MINUTES_TEMPLATE = """Summarise the meeting transcript below as a clean, \
numbered list of minutes with actions.

Format rules:
- Write a numbered list (1., 2., 3., …) of the points discussed, in full \
sentences, grouped by topic.
- Where a point has extra detail, add lettered sub-points (a., b., c.) \
underneath it.
- When a task or follow-up was agreed, write it on its own line right after the \
related point, starting with "**ACTION:**" and naming who is responsible (or \
"[owner unclear]" if the transcript does not say).
- Start the document with this single line: # RSST Meeting Minutes — {date}
- Do not add any other sections — no Summary, Attendees, Decisions, or Open \
Questions headings.

Here is an example of the SHAPE only (ignore its content — do not copy it):

# RSST Meeting Minutes — 30/06/2026

1. Website engagement needs to be improved.
2. A partnership agreement with the other institute is still outstanding.
   a. The legal team needs to review the IP terms first.

**ACTION:** [owner unclear] to circulate the draft agreement.

Domain terms — use these spellings if they appear, and do not list them in your
answer:
{glossary}

Transcript:
{transcript}

Now write the minutes for the real transcript above. Output only the minutes,
starting with the "# RSST Meeting Minutes" line. Do not repeat these
instructions or the transcript."""


# Map step: one part of a long transcript -> a partial list of points (no title).
CHUNK_TEMPLATE = """This is part {part} of {total} of a longer meeting \
transcript. Summarise ONLY this part.

- Write a numbered list (1., 2., 3., …) of the distinct points discussed in \
this part, in full sentences.
- Add lettered sub-points (a., b., c.) for supporting detail.
- Put any agreed task on its own line right after the related point, starting \
with "**ACTION:**" and naming who is responsible (or "[owner unclear]").
- Do NOT write a title or any section headings. Just the numbered points and \
ACTION lines.
- Base everything only on the transcript. Never invent names, numbers, dates, \
or decisions.

Domain terms — use these spellings if they appear, and do not list them in your
answer:
{glossary}

Transcript (part {part} of {total}):
{transcript}

Now list the points and actions for this part only. Do not repeat these
instructions or the transcript."""


# Reduce step: combine the partial lists into one clean minutes document.
MERGE_TEMPLATE = """Below are minutes taken from consecutive parts of ONE \
meeting. Combine them into a single, clean set of minutes.

- Merge points that are duplicated or continued across parts into one point — \
do not repeat the same thing twice.
- Keep the logical order and renumber the points from 1.
- Keep every distinct action as an "**ACTION:**" line right after the point it \
relates to.
- Start with this single line: # RSST Meeting Minutes — {date}
- No other sections — no Summary, Attendees, Decisions, or Open Questions.
- Do not add anything that is not in the parts below.

Minutes from each part:
{partials}

Now output the single combined set of minutes, starting with the "# RSST
Meeting Minutes" line."""


SAFE_CTX = 8192          # comfortable context for a 7B on a laptop (per pass)
CTX_CAP = 16384          # never allocate more than this (RAM guard)
MAX_CHUNK_CHARS = int(os.getenv("MM_MAX_CHUNK_CHARS", "22000"))  # ~6k tokens


def _est_tokens(*parts: str) -> int:
    return sum(len(p) for p in parts) // 4


def _strip_echoed_reference(minutes: str) -> str:
    """Cut anything the model appends after the minutes (echoed prompt sections).
    The minutes proper never contain these markers, so the first occurrence marks
    where the model started parroting the prompt."""
    markers = ("\nDomain terms —", "\nTranscript (part", "\nTranscript:",
               "\nMinutes from each part:", "\nNow list the points",
               "\nNow output the single", "\nNow write the minutes",
               "\nHere is an example")
    positions = [minutes.find(m) for m in markers if m in minutes]
    if not positions:
        return minutes
    cut = min(positions)
    # Don't over-strip: a marker right at the very top means the model parroted
    # the prompt instead of writing minutes. Keep the raw text so the caller can
    # see what happened rather than silently returning almost nothing.
    return minutes if cut < 20 else minutes[:cut].rstrip()


def _dump_debug(cfg, tag: str, user_prompt: str, raw: str, num_ctx: int) -> str | None:
    """Save a failed exchange for diagnosis. A debug aid must never mask the error."""
    try:
        import config
        path = config.OUTPUT_DIR / "last_failure_debug.txt"
        path.write_text(
            f"stage: {tag}\nmodel: {cfg.summary_model}\nnum_ctx: {num_ctx}\n\n"
            f"===== SYSTEM PROMPT =====\n{SYSTEM_PROMPT}\n\n"
            f"===== USER PROMPT =====\n{user_prompt}\n\n"
            f"===== RAW MODEL RESPONSE =====\n{raw!r}\n",
            encoding="utf-8",
        )
        return str(path)
    except Exception:
        return None


def _call_ollama(user_prompt: str, cfg, num_ctx: int) -> str:
    payload = {
        "model": cfg.summary_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": num_ctx},
    }
    req = urllib.request.Request(
        cfg.ollama_host.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Could not reach Ollama at {cfg.ollama_host} ({e}).\n"
            "Is it running?  Start it with:  ollama serve\n"
            f"And is the model pulled?  ollama pull {cfg.summary_model}"
        )
    return (data.get("message") or {}).get("content", "").strip()


def _split_transcript(transcript: str, max_chars: int) -> list[str]:
    """Split into chunks of <= max_chars, only ever breaking at line boundaries
    (each transcript line is one speaker turn) so a sentence is never cut."""
    chunks, cur, size = [], [], 0
    for line in transcript.splitlines(keepends=True):
        if size + len(line) > max_chars and cur:
            chunks.append("".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line)
    if cur:
        chunks.append("".join(cur))
    return chunks or [transcript]


def _mechanical_merge(partials: list[str], date: str) -> str:
    """Fallback if the LLM merge pass fails: stitch the parts together and
    renumber the top-level points sequentially. Keeps sub-points and actions."""
    out, n = [f"# RSST Meeting Minutes — {date}", ""], 0
    for part in partials:
        for line in part.splitlines():
            m = re.match(r"^\s*\d+\.\s+(.*)", line)
            if m:
                n += 1
                out.append(f"{n}. {m.group(1)}")
            else:
                out.append(line)
    return "\n".join(out).strip()


def _fail(cfg, tag, user_prompt, raw, num_ctx, est):
    debug_path = _dump_debug(cfg, tag, user_prompt, raw, num_ctx)
    preview = (raw[:500] + "…") if len(raw) > 500 else (raw or "(empty)")
    where = f"\n  Full prompt + response saved to: {debug_path}" if debug_path else ""
    raise RuntimeError(
        f"The summary model returned almost nothing usable ({tag}).\n"
        f"  Model actually returned: {preview!r}\n"
        f"  Prompt size: ~{est} tokens (context set to {num_ctx}).{where}\n\n"
        "The model and Ollama are working, so this is the model choking on this "
        "specific prompt. Send me last_failure_debug.txt and I'll pin it down."
    )


def summarize(transcript: str, cfg, date: str = "") -> str:
    date = date or "[not stated]"
    glossary = ", ".join(cfg.glossary_terms()) or "(none provided)"

    # --- Short transcript: one pass, full document. --------------------------
    single_prompt = MINUTES_TEMPLATE.format(date=date, glossary=glossary,
                                            transcript=transcript)
    if _est_tokens(SYSTEM_PROMPT, single_prompt) + 1024 <= SAFE_CTX:
        est = _est_tokens(SYSTEM_PROMPT, single_prompt)
        num_ctx = min(max(SAFE_CTX, est + 1024), CTX_CAP)
        raw = _call_ollama(single_prompt, cfg, num_ctx)
        minutes = _strip_echoed_reference(raw)
        if len(minutes.strip()) < 15:
            _fail(cfg, "single pass", single_prompt, raw, num_ctx, est)
        return minutes

    # --- Long transcript: map (per part) then reduce (merge). ----------------
    chunks = _split_transcript(transcript, MAX_CHUNK_CHARS)
    print(f"  … transcript is long — summarising in {len(chunks)} parts")
    partials = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  … part {i}/{len(chunks)}")
        prompt = CHUNK_TEMPLATE.format(part=i, total=len(chunks),
                                       glossary=glossary, transcript=chunk)
        est = _est_tokens(SYSTEM_PROMPT, prompt)
        num_ctx = min(max(SAFE_CTX, est + 1024), CTX_CAP)
        raw = _call_ollama(prompt, cfg, num_ctx)
        part = _strip_echoed_reference(raw)
        if len(part.strip()) < 15:
            _fail(cfg, f"part {i}/{len(chunks)}", prompt, raw, num_ctx, est)
        partials.append(part)

    print("  … merging parts into final minutes")
    combined = "\n\n".join(f"--- Part {i} ---\n{p}" for i, p in enumerate(partials, 1))
    merge_prompt = MERGE_TEMPLATE.format(date=date, partials=combined)
    est = _est_tokens(SYSTEM_PROMPT, merge_prompt)

    # If even the combined partials are too big to merge in one pass, stitch them
    # mechanically rather than risk a truncated merge.
    if est + 1024 > CTX_CAP:
        return _mechanical_merge(partials, date)

    num_ctx = min(max(SAFE_CTX, est + 1024), CTX_CAP)
    raw = _call_ollama(merge_prompt, cfg, num_ctx)
    merged = _strip_echoed_reference(raw)
    if len(merged.strip()) < 15:
        # Merge choked — fall back to a clean mechanical stitch so the user still
        # gets usable minutes instead of an error.
        print("  … merge pass came back empty; stitching parts directly")
        return _mechanical_merge(partials, date)
    return merged
