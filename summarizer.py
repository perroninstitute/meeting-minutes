"""Turn a speaker-labelled transcript into clinical meeting minutes.

Runs entirely against a local Ollama server — the transcript never leaves the
machine. The model is given the domain glossary so it keeps clinical terms
correct, and a strict structure so the output is consistent every time.
"""

from __future__ import annotations

import json
import urllib.request


SYSTEM_PROMPT = """You are a precise clinical meeting-minutes assistant for a \
neurological institute. You transform raw, speaker-labelled meeting transcripts \
into structured minutes.

Rules:
- Be factual. Only state what is supported by the transcript. Never invent \
names, numbers, dates, dosages, or decisions.
- Preserve clinical terminology exactly. Do not simplify or paraphrase medical \
terms, drug names, or abbreviations.
- Attribute decisions and action items to the speaker who made them when the \
transcript makes it clear.
- If something is unclear or inaudible, write "[unclear]" rather than guessing.
- Keep patient-identifying detail to the minimum needed for the minutes to be \
useful."""


MINUTES_TEMPLATE = """Produce the minutes in this exact Markdown structure:

# Meeting Minutes

**Date:** {date}
**Attendees (speakers detected):** {speakers}

## Summary
A short paragraph (3-5 sentences) capturing the purpose and overall outcome.

## Key Discussion Points
- Bullet points of the main topics discussed, grouped logically.

## Decisions
- Each decision made, with the responsible person if known.

## Action Items
- [ ] Action — Owner — Due/Timeframe (use "[unclear]" where not stated)

## Open Questions / Follow-ups
- Anything left unresolved.

---
Use this domain terminology with the spellings below wherever it appears. Do
NOT list, repeat, or output these terms anywhere in your answer — they are
reference only:
{glossary}
---

Transcript to summarise:
{transcript}

Now output ONLY the meeting minutes in the exact structure above. Do not echo
the terminology list or the transcript."""


def _speakers_in(transcript: str) -> str:
    seen = []
    for line in transcript.splitlines():
        # lines look like "[mm:ss] SPEAKER_00: text"
        if "] " in line and ": " in line:
            spk = line.split("] ", 1)[1].split(": ", 1)[0]
            if spk and spk not in seen:
                seen.append(spk)
    return ", ".join(seen) if seen else "not separated"


def _strip_echoed_reference(minutes: str) -> str:
    """Cut anything the model appends after the minutes (echoed glossary or
    transcript). The minutes proper never contain these markers, so the first
    occurrence of one marks where the model started parroting the prompt."""
    markers = ("\nUse this domain terminology", "\nTranscript to summarise",
               "\nRelevant domain terminology", "\nTranscript:")
    cut = min((minutes.find(m) for m in markers if m in minutes), default=-1)
    return minutes[:cut].rstrip() if cut != -1 else minutes


def summarize(transcript: str, cfg, date: str = "") -> str:
    # Cleaned terms only (no "#" comment lines from glossary.txt) — keeps the
    # prompt tight and avoids the model echoing comment scaffolding.
    glossary = ", ".join(cfg.glossary_terms()) or "(none provided)"
    user_prompt = MINUTES_TEMPLATE.format(
        date=date or "[not stated]",
        speakers=_speakers_in(transcript),
        glossary=glossary,
        transcript=transcript,
    )

    payload = {
        "model": cfg.summary_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        # Low temperature: minutes should be faithful, not creative.
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }

    url = cfg.ollama_host.rstrip("/") + "/api/chat"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Could not reach Ollama at {cfg.ollama_host} ({e}).\n"
            "Is it running?  Start it with:  ollama serve\n"
            f"And is the model pulled?  ollama pull {cfg.summary_model}"
        )

    content = (data.get("message") or {}).get("content", "").strip()
    return _strip_echoed_reference(content)
