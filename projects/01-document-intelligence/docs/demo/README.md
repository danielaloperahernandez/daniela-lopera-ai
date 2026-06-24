# Demo assets

Place the demo recording here as `demo.gif` (and/or link a 2-minute Loom in the project
README). A short clip beats a thousand lines of code for a recruiter.

## Suggested 90-second script

1. Show the FastAPI docs at `http://localhost:8000/docs` and the `/health` response.
2. In n8n, open the "Doc Intelligence - Invoice Orchestration" workflow (canvas view).
3. Send a test email with a PDF invoice attached (or click "Execute Workflow" with a pinned item).
4. Watch the execution light up: Email Trigger -> Call Extraction API -> Save to Postgres -> Notify.
5. Show the resulting row in Postgres and the Telegram success message.
6. Optional: trigger a failure (stop the API) to show the Error Handler firing a Telegram alert.

## How to record

- Loom (browser) or ScreenToGif / ShareX (Windows) for a lightweight GIF.
- Keep it under ~2 minutes; trim dead time.
- Update the link/path in [`../../README.md`](../../README.md) once recorded.

> Placeholder: replace this file's folder with the actual `demo.gif`.
