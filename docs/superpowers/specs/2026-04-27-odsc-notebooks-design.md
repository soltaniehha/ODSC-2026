# ODSC 2026 Tutorial Notebooks: Design Spec

Date: 2026-04-27
Owner: Mohammad Soltaniehha
Scope: Two Colab notebooks built from the existing `01-Simple-Voice.py` and `05-Realtime-Agent.py` samples. Notebook 3 is intentionally out of scope for this iteration.

## Goal

Two public-facing, beginner-friendly Colab notebooks that demonstrate:

1. A LiveKit voice agent (STT + LLM + TTS) on the LiveKit Cloud free tier.
2. The current OpenAI Realtime voice model with prompt injection support.

Both notebooks run entirely inside the notebook (no jumping to a hosted playground), use Colab Secrets for credentials, and demonstrate layered safeguards.

## Non-goals

- Notebook 3 (any avatar variant) is not built in this iteration.
- No production-grade deployment guidance, no telemetry, no auth flows beyond what Colab Secrets provides.
- No custom React frontends or external hosting for the in-notebook widget.

## Audience and tone

ODSC tutorial attendees, mixed Python experience. Prose is plain and declarative. No em-dashes. No emojis. No marketing language. Short sentences. Headings only where they aid navigation. Code is class-free wherever the SDK allows.

## Output files (repo root, alongside existing samples)

- `01-LiveKit-Voice-Agent.ipynb`
- `02-OpenAI-Realtime-Voice.ipynb`

## Shared notebook skeleton

Each notebook follows the same 8 to 12 cell structure:

1. Title and 2-3 sentence description with a link to the official source doc.
2. Prerequisites cell listing the exact Colab secrets to add and where to get each key.
3. Install cell (`%pip install ...`).
4. Imports and secret loading via `google.colab.userdata.get(...)` with a clear error if missing.
5. Configuration cell (system prompt, voice, safeguard toggle).
6. Safeguards cell (layered defense).
7. Connect cell that starts the session and renders the in-notebook widget.
8. Cleanup cell to stop the session cleanly.

## Notebook 1: LiveKit Voice Agent

### Stack

- STT: Deepgram Nova 3 via LiveKit Inference (`inference.STT("deepgram/nova-3")`).
- LLM: GPT 4.1 mini via LiveKit Inference (`llm="openai/gpt-4.1-mini"`).
- TTS: Cartesia Sonic 3 via LiveKit Inference (`inference.TTS("cartesia/sonic-3", voice=...)`).
- VAD + turn detection: Silero VAD + multilingual turn detector.

### Colab secrets

Required:
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

Optional (only for the OpenAI Moderation safeguard cell):
- `OPENAI_API_KEY`

### Free tier coverage

LiveKit Cloud Build plan (no credit card) includes ~50 minutes of inference credit and 1000 agent-session minutes. Adequate for a tutorial. We will state this in the prerequisites cell with the signup link.

### Worker startup pattern

`livekit.agents.cli.run_app(server)` is CLI-only. In Colab we run the worker on a background `threading.Thread` with its own asyncio loop. Approximate shape (the build agent will refine against the current API):

```python
import asyncio, threading
from livekit.agents import AgentServer

def _run_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.run())  # or equivalent current entry

worker_thread = threading.Thread(target=_run_worker, daemon=True)
worker_thread.start()
```

### In-notebook frontend

There is no LiveKit-hosted page that accepts a token via URL query string. The notebook embeds an `IPython.display.HTML` block that:

- Loads `livekit-client` from a CDN (e.g., `https://unpkg.com/livekit-client/dist/livekit-client.umd.min.js`).
- Renders a "Connect" and "Disconnect" button.
- Uses a Python-minted access token (`livekit.api.AccessToken().with_identity(...).with_grants(VideoGrants(room_join=True, room=...)).to_jwt()`).
- Captures mic via `getUserMedia`, attaches the agent's audio track to an inline `<audio>` element.
- Shows a small connection-state log.

Approximate widget size: 60 lines of vanilla JS, no frameworks.

### Layered safeguards

**Layer A (input moderation)**: Override `on_user_turn_completed(turn_ctx, new_message)` on the agent to send the user's transcribed text through OpenAI Moderation (`omni-moderation-latest`). If `flagged`, replace the message content with a fixed refusal token before it reaches the LLM. Second cell shows the same pattern using `Detoxify` with no API key (heavier first run, no signups).

**Layer B (prompt-level)**: Scoped system prompt with explicit topic boundaries and refusal language. Demonstrates how prompt-level guardrails complement API-level moderation.

**Layer C (tool gating)**: Keep `get_current_time` from the source sample. Show how to gate which tools fire by overriding `llm_node` to filter the tools list per turn, or by setting `tool_choice="none"` for a turn where moderation flagged anything.

### Acceptable class usage

The current LiveKit Agents API requires subclassing `Agent` to register hooks like `on_user_turn_completed`. We will keep that one class, comment it explicitly as the only one, and use functions for everything else (tools via `@function_tool`, worker entry as a module-level function).

## Notebook 2: OpenAI Realtime Voice

### Stack

- Model: `gpt-realtime` (alias). The `gpt-4o-realtime-preview` family is deprecated.
- Voice: `marin` by default (recommended by OpenAI), with `cedar`, `alloy`, `ash`, `ballad`, `coral`, `echo`, `sage`, `shimmer`, `verse` listed in a comment.
- Transport: WebRTC direct from the browser to OpenAI. No Python audio plumbing.

### Colab secret

Required:
- `OPENAI_API_KEY` (used only by Python to mint a short-lived ephemeral token; never sent to the browser).

### Token mint cell

Python `requests.post` to `https://api.openai.com/v1/realtime/client_secrets` with payload:

```json
{
  "expires_after": { "anchor": "created_at", "seconds": 600 },
  "session": {
    "type": "realtime",
    "model": "gpt-realtime",
    "instructions": "<user-edited system_prompt>",
    "audio": {
      "input": {
        "transcription": { "model": "gpt-4o-transcribe" },
        "turn_detection": { "type": "semantic_vad" }
      },
      "output": { "voice": "marin" }
    }
  }
}
```

Returns `value` (ephemeral token) and `expires_at`. The token is passed into the HTML widget via Python string interpolation when the cell renders.

### Prompt injection

A clearly labeled cell: `system_prompt = """..."""`. The user edits the string. The next cell (token mint) reads the variable and bakes it into the session config. Re-running mints a new token.

### In-notebook widget

`IPython.display.HTML` block (no frameworks, vanilla JS). Behavior:

- "Start session" and "Stop" buttons.
- On start: `getUserMedia({audio: true})`, create `RTCPeerConnection`, add mic track, attach remote audio track to inline `<audio>`, create `oai-events` data channel, send SDP offer to `https://api.openai.com/v1/realtime/calls` with `Authorization: Bearer <ephemeral_token>`, set remote answer.
- Data channel listener:
  - Logs key event types in a small inline log area.
  - On `conversation.item.input_audio_transcription.completed`, runs the transcript through Moderation (Layer C below).
- "Stop" closes the peer connection cleanly.

Approximate widget size: 80 to 100 lines of vanilla JS, presented as one literal string.

### Layered safeguards

**Layer A (prompt sanitization at mint time)**: Before posting to `/realtime/client_secrets`, run `system_prompt` through OpenAI Moderation. If flagged, refuse to mint the token and tell the user to revise their prompt. Catches accidental jailbreak content the user pasted.

**Layer B (instructions-level)**: The `system_prompt` itself contains explicit refusal language and topic boundaries.

**Layer C (live transcript moderation)**: The widget calls a tiny Python-backed proxy or directly calls `https://api.openai.com/v1/moderations` with a separate, longer-lived but moderation-only key for the per-turn check. To keep the notebook simple and avoid two key types, the build agent will choose between:
- (a) calling Moderation from the browser using a moderation-only ephemeral key (preferred if OpenAI supports scoping ephemeral tokens to moderation), or
- (b) checking moderation on the way out by sending a `session.update` event over the data channel that injects a stricter `instructions` string after a flagged turn (no separate Moderation call).

The build agent will pick the simpler path and document the trade-off in a one-line comment.

**Layer D (mid-flight tightening)**: Show a "Tighten safeguards" button that sends a `session.update` event with stricter `instructions` (e.g., refuse anything off-topic from now on). Demonstrates that safety can adapt during a session.

### Acceptable class usage

None. This notebook is fully function-based on the Python side. The widget is plain HTML/JS.

## Agent Teams workflow (after spec approval)

1. Builder agent for Notebook 1 (general-purpose, parallel).
2. Builder agent for Notebook 2 (general-purpose, parallel).
3. Reviewer agent (`pr-review-toolkit:code-reviewer`) checks code quality, classes-only-where-mandatory rule, secret usage, and prose for AI-tics (em-dashes, emoji, "Let's", marketing tone).
4. Verifier agent (general-purpose) does a static cell-by-cell read for import order, undefined references, leftover placeholders, and that safeguard cells are toggleable independently.

Builders run in parallel. Reviewer and verifier run in parallel after both builders finish. Feedback is integrated by the main session before reporting done.

## Open implementation questions deferred to build

- The exact current `AgentServer` programmatic-start coroutine name (the public docs show only `cli.run_app`; the build agent will inspect the installed `livekit-agents` package to confirm `server.run()` or the equivalent).
- Whether browser-side Moderation calls in Notebook 2 require a second key type or can use the same ephemeral token (build agent picks the simpler path).
- Exact `livekit-client` JS SDK CDN version pin to use (build agent picks a recent stable).

## Out of scope

- Notebook 3 (avatar / xai realtime / custom mode avatar) deferred to a later iteration.
- Production deployment, monitoring, billing dashboards.
- LiveKit Sandbox token server flow (requires console clicks; we mint locally instead).
