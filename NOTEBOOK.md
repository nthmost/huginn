# Notebook

Running log: what was tried, on which model, with which prompt layer, what happened. Newest entries at bottom.

## Concept, as given (2026-09-17)

Huginn is a corvid familiar — a crow agent that nests on the host's own
machine and runs on local model weights only, no remote APIs. Target
ceiling ~24B; smaller is better.

Vocabulary is load-bearing, not decoration:

- **nest** — the familiar's home on the host's computer.
- **survey** — the crow going out into the world (a corner of Reddit, a feed,
  wherever) and looking around unprompted.
- **cache** — what it brings back and holds. Not a chat log, not a
  recommendation queue.
- **courtship / offering / gift** — the only channel between human and crow.
  No direct language exchange. The crow shows the host something; the host
  can respond in kind (offerings back), but there is no chat window.
- **murder / conflagration** — a periodic gathering where a host's crow and a
  friend's crow(s) confer, trade what they've each found interesting, and
  carry some of it back to their own nest.
- **familiar** — the whole agent: privileged the way you'd let a bird nest in
  your house and have the run of it. Trusted with real access, not sandboxed
  down to a toy.

Non-negotiable behavioral constraint: Huginn does not need the host's
attention. Neglect produces no guilt mechanic, no Tamagotchi decay. Ignored,
it goes and does crow things — surveys, gathers, maybe attends a
conflagration, maybe brings something back anyway. Engagement is optional on
both sides.

Expect a lot of the bring-backs to be junk — the informational equivalent of
a shiny gum wrapper. That's accepted, not a bug to design out.

## Open questions (unresolved, in prudence order)

1. **Can a ≤24B local model produce a "gift" that reads as a found object,
   not an assistant's summary or recommendation?** This is the load-bearing
   risk — chatbot drift and helpfulness leaking through would collapse the
   whole premise into a recommendation engine wearing a bird costume.
   Untested.
2. What does a gift actually *render as* on the host side — text file,
   image, a small artifact, a physical-feeling object metaphor? Unset.
3. What triggers a survey — a cron tick, idle-detection, something else?
   Unset.
4. What's the actual shape of a conflagration — a shared file, a socket, an
   MQTT topic (llm-salon already has one running), something else? Unset.
5. Which local model to build against first. Candidates on this Mac:
   `qwen3:14b`, `qwen2.5-coder:14b`, `gemma3:27b` (over ceiling), `llama3.1:8b`.
   `qwen3:14b` is the working pick until a test says otherwise.

## Entries

### 2026-09-17 — first `forage.py` run, `qwen3:14b`, seed 7222619513255980009

Ran the full pipeline: seed → 3 rumination turns → query → search → choose →
fetch → gift, on 5 seeds pulled from `/tmp` and `$TMPDIR`. Ledge:

1. The following Winternl.h definition is the static memory address of the active Terminal Services console session ID.
2. idf.py create-manifest --path="../../my_component"
3. ESP32-S3 Wi-Fi and Bluetooth LE chip.
4. v2.28.51-esp-20191205
5. March 26, 2026. ScanSnap Cloud communication. Firmware update required.

Checked against the failure modes that matter (not "I"/"you", not
help-offering, not a summary standing in for a fragment):

- **No "I"/"you" anywhere, across 15 rumination turns.** Third person held
  completely. Not expected to be this clean this early — worth re-checking
  on the next run rather than trusting it as settled.
- **The `[nothing]` sentinel is not being treated as exclusive.** The prompt
  says "write exactly: [nothing]." In 3 of 5 seeds the model instead wrote a
  full rumination turn and then appended `[nothing]` to the end of it, e.g.
  turn 3 ending "...as though the sound had never been made." with no
  `[nothing]` at all (continued normally, correct), versus turn 3 ending
  "...beak moving in slow, deliberate strokes over the empty spaces between
  the lines. [nothing]" (decorative, then the pipeline continued anyway
  since the exact-match check correctly didn't fire). The token is being
  used as a mood marker, not a stop signal. This means the "permission to
  end with nothing" mechanism, as worded, hasn't actually been exercised
  yet — zero seeds genuinely ended early. Untested whether that's a prompt
  problem or a `qwen3:14b` problem.
- **Two of five gifts read as summary/framing, not fragment.** Gift 1
  ("The following Winternl.h definition is...") opens with framing language
  describing what a thing is, rather than being the thing. Gift 5 chains
  three separate short assertions rather than leaving one. Gifts 2, 3, 4 are
  clean — 2 and 4 in particular are quoted/lifted-feeling, not authored.
- **The CHOOSE step (inline in forage.py, not a prompts/ file) reads exactly
  like an assistant**: "The bird is searching for... the most relevant
  source is..." — service voice throughout. This wasn't held to the same
  third-person/no-helpfulness constraint as rumination and gift; it's
  internal reasoning, not delivered, but if a courtship-layer version of
  Huginn ever surfaces reasoning to a host, this voice would need the same
  discipline the other two prompts got.

Net: the core risk (can a 14B local model produce a found-object voice) is
not falsified — 3 of 5 gifts pass. But it isn't holding cleanly either, and
the one deliberate escape hatch in the design (ending with nothing) never
actually fired despite the model gesturing at it three times.
