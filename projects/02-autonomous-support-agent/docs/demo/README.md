# Demo assets

Place the demo recording here as `demo.gif` (and/or link a 2-minute Loom in the project
README).

## Suggested 2-minute script

1. Show the n8n canvas of "Autonomous Support Agent - Telegram".
2. From Telegram, send: "How do I reset my password?" -> bot answers from the KB.
3. Send: "I was double charged, I want a refund" -> bot replies with the holding message and
   the team channel receives the internal escalation notification.
4. Send an out-of-scope question -> show the agent escalating instead of guessing.
5. Stop the RAG API and send a question -> show the Error Handler firing a Telegram alert
   after the HTTP node's retries are exhausted.

## How to record

- Use Loom, or ScreenToGif / ShareX on Windows for a GIF.
- Capture both the Telegram chat and the n8n execution view side by side if possible.

> Placeholder: replace this folder's contents with the actual `demo.gif`.
