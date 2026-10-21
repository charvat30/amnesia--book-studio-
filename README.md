# Amnesia Book Studio — ChatGPT Action starter

A Czech-first starter backend for a custom GPT Action to manage book projects from manuscript intake to print approval.

## What is included
- FastAPI backend with SQLite persistence
- OpenAPI 3.1 schema for GPT Actions
- API-key authentication using `AMNESIA_API_KEY`
- CRUD for book projects
- Workflow checklist and progress updates
- Printer brief generation
- Printer quote tracking
- No manuscript content is fabricated; book records are only metadata/placeholders

## Run locally
Requires Python 3.11+.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Set an API key before starting:

```powershell
# Windows PowerShell
$env:AMNESIA_API_KEY="replace-with-a-long-random-secret"
uvicorn app:app --reload
```

```bash
# macOS/Linux
export AMNESIA_API_KEY="replace-with-a-long-random-secret"
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000/docs` to test endpoints.

## Connect to ChatGPT
GPT Actions need a publicly reachable HTTPS API. A localhost address will not work from ChatGPT. Deploy this backend to a host that supports Python/FastAPI and configure the secret environment variable there. Then:

1. Create a GPT in ChatGPT (GPT creation availability depends on your plan/workspace).
2. In the GPT editor, open **Configure → Actions → Create new action**.
3. Paste/import `openapi.yaml`, replacing `https://YOUR-PUBLIC-HTTPS-HOST` with the deployed HTTPS origin.
4. Configure API-key authentication using header name `X-API-Key` and the same secret value as `AMNESIA_API_KEY`.
5. Test `listBooks`, `createBook`, `updateBook`, `getChecklist`, `updateChecklist`, `generatePrinterBrief`, and `addPrinterQuote`.
6. Keep the API private. Never put secrets into the OpenAPI file or public repository.

## Important print-production limits
This starter tracks readiness but does not itself guarantee print compliance. Final bleed, spine width, PDF/X settings, color profile, image DPI and cover dimensions must be confirmed with the chosen printer and the final page count/paper stock. Do not send a final print file until the printer approves its specifications.

## Data and security
- SQLite database is stored in `amnesia_books.db` beside the app.
- API key is read from environment; it is not hardcoded.
- For a public production deployment, add HTTPS, backups, access controls, rate limits, privacy policy and a durable database.
- This is a starter implementation, not yet deployed or connected to ChatGPT.
