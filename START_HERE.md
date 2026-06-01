# Start Here — a friendly setup guide

This guide walks you through setting up the meeting-minutes tool on a normal
Windows laptop, step by step, explaining **what** each thing is and **why** you
need it. No prior coding experience assumed. Take it one box at a time — you
only do this setup **once**.

> If you ever want the short, technical version, see `README.md`. This guide is
> the gentle version.

---

## What does this tool actually do?

You sit in a meeting (e.g. a Teams call) like normal. This tool:

1. **Records** the audio — both the other people (what comes out of your
   speakers/headset) and you (your microphone).
2. **Writes down** everything that was said, and figures out **who said what**
   ("Speaker 1", "Speaker 2", …).
3. **Summarises** it into tidy meeting minutes — a summary, key points,
   decisions, and action items.

```
   your meeting  →  recording  →  transcript (who said what)  →  minutes.md
```

**The most important part:** *everything happens on your own laptop.* Your
audio, the transcript, and the minutes are **never** uploaded anywhere. There's
no cloud account, no per-use cost, no company servers. (More on this in
[Is this private?](#is-this-private) below — it matters for sensitive meetings.)

---

## The pieces you'll install (and why)

| You install… | What it is | Why it's needed |
|---|---|---|
| **Python** | The programming language the tool is written in | Runs the tool |
| **The tool's packages** | A bundle of code libraries (Whisper, etc.) | Does the listening + writing-down |
| **Ollama** | A small app that runs an AI model on your laptop | Writes the summary, locally |
| **FFmpeg** | A free audio utility | Lets the tool read the recorded sound |
| **A Hugging Face account** | A free account that hosts the "who spoke" AI model | One-time, free download of that model |

You'll set these up in order below. It takes maybe **30–45 minutes** the first
time, mostly waiting for downloads.

---

## One-time setup

### Step 0 — Open "PowerShell"

PowerShell is the text-command window we'll type into. Click **Start**, type
`PowerShell`, and click **Windows PowerShell**.

You'll paste commands into it and press **Enter** to run them. (To paste, right-
click in the window, or press Ctrl+V.)

> **One-time:** so Windows will let you run the helper scripts in this project,
> paste this and press Enter:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```
> Type `Y` and Enter if it asks. This only allows scripts *you* have on your
> own machine to run — it's safe.

### Step 1 — Install Python

1. Go to <https://www.python.org/downloads/> and click the big "Download" button.
2. Run the installer. **Important:** on the first screen, tick the box that says
   **"Add Python to PATH"** (this lets you run Python by name). Then click
   "Install Now".

*Why:* Python is the engine the whole tool runs on.

### Step 2 — Get the code

You'll have been given access to the project on GitHub. Easiest way:

- On the GitHub page, click the green **Code** button → **Download ZIP**.
- Unzip it somewhere easy to find, like your Desktop. You'll get a folder called
  `meeting-minutes`.

Then in PowerShell, move into that folder (adjust the path if you put it
elsewhere):
```powershell
cd $HOME\Desktop\meeting-minutes
```

*Why:* this folder has all the tool's code and the helper scripts.

### Step 3 — Set up the tool's packages

Paste these **one line at a time**:
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

*What's happening:*
- The first line makes a **"virtual environment"** — a private sandbox in this
  folder so the tool's packages don't interfere with anything else on your
  laptop.
- The second line **switches into** that sandbox. (You'll see `(venv)` appear at
  the start of the line. Any time you come back to use the tool, run this line
  again first.)
- The third line **downloads the tool's packages**. This one takes a while and
  prints a lot of text — that's normal. Wait for it to finish.

> Your laptop doesn't have a gaming graphics card, so the tool runs on the
> regular processor (CPU). That's fine — you don't need to do anything special,
> and you can **ignore** the GPU instructions in the technical README.

### Step 4 — Install Ollama and download the summary model

1. Download Ollama from <https://ollama.com/download> and install it (just click
   through). It runs quietly in the background.
2. Back in PowerShell, download the AI model that writes the summaries:
   ```powershell
   ollama pull qwen2.5:7b
   ```
   This downloads ~4.7 GB once, then it's on your laptop forever.

*Why:* Ollama is what turns the transcript into a readable summary — **on your
laptop**, instead of sending it to a cloud AI service.

### Step 5 — Install FFmpeg (the audio helper)

Just run the helper script we included:
```powershell
.\presets\install-ffmpeg.ps1
```
It downloads FFmpeg and sets everything up for you. When it finishes, **close
PowerShell and open a new one**, then `cd` back into the folder and re-run
`venv\Scripts\Activate.ps1`.

*Why:* FFmpeg is a small free tool that lets the transcriber read the recorded
audio. (You might later see a one-line warning mentioning "torchcodec" — that's
harmless, you can ignore it.)

### Step 6 — Get a Hugging Face token (for the "who spoke" feature)

The part that labels **who said what** uses a free AI model that's hosted on a
site called Hugging Face. They just ask you to make a free account and click
"agree" once.

1. Make a free account at <https://huggingface.co>.
2. While logged in, open this page and click **"Agree and access repository"**:
   <https://huggingface.co/pyannote/speaker-diarization-community-1>
3. Go to <https://huggingface.co/settings/tokens>, click **"Create new token"**,
   choose the **Read** type, and copy the long code it gives you (it starts with
   `hf_`).
4. In PowerShell, paste this — with your code in the quotes:
   ```powershell
   setx MM_HF_TOKEN "hf_paste_your_code_here"
   ```

*Why:* the model that separates speakers is "gated" — the makers just want you
to have a (free) account. The token is how the tool proves you're allowed to
download it. **You only do this once.** (If you skip this, the tool still works —
it just won't label who spoke.)

> Keep that token private, like a password.

### Step 7 — Apply the laptop settings

One command sets all the right options for a laptop (and turns off a bit of
usage tracking the speaker model has on by default, so nothing leaves your
machine):
```powershell
.\presets\laptop-cpu.ps1
```
Then **close and reopen PowerShell** one more time so all settings take effect,
and `cd` back into the folder.

**Setup is done!** 🎉

---

## Using it day to day

Each time you want to use the tool, open PowerShell, then:
```powershell
cd $HOME\Desktop\meeting-minutes
venv\Scripts\Activate.ps1
```

**To record a meeting and get minutes automatically:**
```powershell
python main.py run
```
It starts recording. When the meeting is over, press **Enter** to stop. It will
then write down the conversation and create the minutes. (On a laptop this
processing step can take a while — roughly as long as, or longer than, the
meeting itself. That's normal; let it work.)

**Or record for a set number of minutes** (e.g. a 30-minute meeting = 1800
seconds), hands-free:
```powershell
python main.py run -d 1800
```

**Where your results go:** a folder called `minutes`:
- `…transcript.txt` — the full word-for-word transcript with speaker labels.
- `…minutes.md` — the tidy summary. (Open it in any text editor, or something
  like VS Code or Typora to see it nicely formatted.)

> **Tip — much better accuracy:** open the file `glossary.txt` and add the
> names, drug names, abbreviations, and jargon from your actual meetings. The
> tool uses this list to spell those words correctly and keep them in the
> summary. This makes a big difference for specialised vocabulary.

---

## Is this private?

**Yes.** After the one-time downloads in setup, the tool needs **no internet at
all**. Your recordings, transcripts, and summaries stay in folders on your
laptop and are never uploaded. There is no account to log into and nothing is
charged per use.

(The only nuance: the speaker-labelling model normally reports anonymous usage
stats — never your audio or words, just things like "a recording was
processed." The laptop setup in Step 7 **turns that off**, so truly nothing
leaves your machine. For extra peace of mind in a clinical setting, your IT team
can also block the tool from the internet entirely.)

---

## ⚠️ Before you use it for a real meeting

This tool **records people**, so please:

- **Tell people they're being recorded** and get their okay. Recording meetings
  without consent is often against the rules (and the law).
- **Clear it with your workplace's IT / data-protection person** first —
  especially on a work laptop. A fully-local tool like this is the easiest kind
  to get approved, but you should still ask.
- **Practise with a dummy recording first** (e.g. record yourself talking, or a
  podcast) until you're happy it works — **never** test on a real patient
  meeting.
- **Keep the `recordings` and `minutes` folders safe** (they hold sensitive
  content) and out of any cloud-synced folder like OneDrive.

---

## When something goes wrong

**"It says it can't run scripts / running scripts is disabled."**
You skipped the one-time command in Step 0. Run it, then try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Weird error mentioning "charmap" or strange symbols / it crashes when saving.**
This is a Windows text-encoding quirk. Fix it once:
```powershell
setx PYTHONUTF8 1
```
Then close and reopen PowerShell. (The laptop preset already sets this, so this
usually only happens if you skipped Step 7.)

**The summary step fails / "Could not reach Ollama".**
Make sure Ollama is installed and running (it normally starts itself; you can
also just reopen it from the Start menu), and that you ran
`ollama pull qwen2.5:7b` in Step 4.

**It says "403" or "access restricted" when labelling speakers.**
You haven't accepted the model terms or the token isn't set. Re-check Step 6 —
especially clicking "Agree and access repository" on the
`speaker-diarization-community-1` page.

**No speakers are labelled (everyone shows as "Speaker ?").**
Same as above — it means the speaker model couldn't load, usually a missing
token or un-accepted terms. The transcript and summary still work without it.

**My microphone isn't being recorded (only the other people are).**
Check your mic isn't muted (headset mute button / Windows mic settings). It's
worth doing a 10-second test recording and listening back before a real meeting.

**It's really slow.**
On a laptop without a gaming graphics card, transcribing is slow — expect it to
take a while, sometimes longer than the meeting. That's expected. If it's
unbearable, you can switch to a faster (slightly less accurate) setting by
running `setx MM_WHISPER_MODEL small` and reopening PowerShell.

---

Stuck on something not listed here? Send the error text to whoever set this up
for you — most issues are a missed step above.
