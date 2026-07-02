"""Turn a speaker-labelled transcript into RSST meeting minutes.

Runs entirely against a local Ollama server — the transcript never leaves the
machine. The model is given the domain glossary so it keeps clinical terms
correct, and a strict structure so the output is consistent every time.
"""

from __future__ import annotations

import json
import urllib.request


SYSTEM_PROMPT = """You are a precise clinical meeting-minutes assistant for a \
neurological institute. You turn raw, speaker-labelled meeting transcripts into \
a clean, logically organised list of minutes and actions.

Rules:
- Be factual. Only state what is supported by the transcript. Never invent \
names, numbers, dates, dosages, or decisions.
- Preserve clinical terminology exactly. Do not simplify or paraphrase medical \
terms, drug names, or abbreviations.
- Attribute decisions and actions to the person who made them when the \
transcript makes it clear.
- If something is unclear or inaudible, write "[unclear]" rather than guessing.
- Keep patient-identifying detail to the minimum needed for the minutes to be \
useful.
- Write in full, readable sentences. Organise by topic, not by the chronology \
of the conversation — merge scattered mentions of the same topic into one \
point."""


MINUTES_TEMPLATE = """Produce the minutes as a clean numbered list of discussion \
points, with any agreed tasks called out as ACTION lines. Use this exact \
Markdown structure:

# RSST Meeting Minutes — {date}

1. First discussion point, in full sentences — what was discussed, noted, or decided.
   a. A supporting detail, consideration, or who-said-what, if there is one.
   b. Another supporting detail, if there is one.
2. The next discussion point.

**ACTION:** <responsible person> to <do what>.

Rules for the structure:
- Number the main discussion points (1., 2., 3. …), ordered logically by topic.
- Use lettered sub-items (a., b., c.) ONLY where a point has supporting detail \
worth separating out. If a point has no sub-detail, do not force any.
- Whenever a task or follow-up is agreed, put it on its OWN line immediately \
after the point it relates to, formatted exactly as: **ACTION:** <who> to \
<task>. One action per line. If the owner is not clear from the transcript, \
write "**ACTION:** [owner unclear] — <task>".
- Do NOT add Summary, Attendees, Decisions, or Open Questions sections. Only the \
numbered points and their ACTION lines.

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
