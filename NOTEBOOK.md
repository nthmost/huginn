# Notebook

Running log: what was tried, on which model, with which prompt layer, what happened. Newest entries at bottom.

## Concept, as given (2026-09-17)

Huginn is a corvid familiar. The first instance is **Hunin**, a crow agent that
nests on the host's own machine and runs on local model weights only — no
remote APIs. Target ceiling ~24B; smaller is better.

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

Non-negotiable behavioral constraint: Hunin does not need the host's
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

(none yet — first entry goes here once an experiment runs)
