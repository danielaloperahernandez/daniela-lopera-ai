# Demo assets

Place a call recording / screen capture here as `demo.gif` (or link a Loom / call audio in
the project README). For a voice agent, a short recording of a real call is the most
convincing artifact.

## Suggested 2-3 minute script

1. Show the Vapi assistant config (system prompt + the two tools) briefly.
2. Place a call and ask a technical question (e.g. "se me esta saliendo agua del lavamanos")
   -> the agent consults the manual (RAG) and gives a safe, empathetic tip.
3. Ask to book a visit -> agent offers slots, you pick one -> agent confirms with code.
4. Call again from the same number and say "quiero cancelar mi cita" -> agent looks it up,
   confirms the details, and cancels it.
5. Show the n8n execution view and the Postgres `calls` / `appointment_slots` rows updating.
6. Optional: show a Telegram error alert by forcing a node failure.

## How to record

- Capture the n8n canvas + executions; for the voice side, attach the Vapi call recording.
- Keep it tight; trim silence.

> Placeholder: replace this folder's contents with the actual `demo.gif` / recording link.
