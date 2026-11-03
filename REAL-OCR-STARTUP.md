# Local accounts with real Gemini OCR

`api.local_server:app` uses fixture validation only when `MEDISAATHI_LOCAL_OFFLINE` is not `0`. Set it explicitly to `0` for the normal AIIntegration/Gemini path. PNG and JPEG bytes are validated by the existing reader; real mode has no fixture hashes or filename allowlist. No mock fallback is used on provider failure.

The large recognition information panel has been removed without leaving DOM space. Mode detection remains a session-bound GET with no image submission. Real mode uses **Analyze Prescription with AI** / **AI से पर्चे का विश्लेषण करें**. Offline mode retains a distinct simulation button and source labels. Existing handwriting warnings, original source values, manual review and independent confirmations remain.

## Restart API (PowerShell)

Stop the existing API with Ctrl+C in its own terminal first. Do not launch competing listeners on 8005. Account rows and auth sessions survive restart; temporary medical workspaces do not.

```powershell
Set-Location C:\Users\ASHTAMI\MediSaathi-TeamIntegration
$env:PYTHONPATH = 'C:\Users\ASHTAMI\MediSaathi-TeamIntegration\api\.venv\deps'
$env:MEDISAATHI_LOCAL_OFFLINE = '0'
$env:MEDISAATHI_LOCAL_HTTPS = '0' # Loopback HTTP; HTTPS environments retain Secure cookies.
$python = 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -c "from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASHTAMI\MediSaathi\medisaathi\.env'); import uvicorn; uvicorn.run('api.local_server:app', host='127.0.0.1', port=8005, access_log=False, proxy_headers=False)"
```

This loads the existing original AI workspace `.env` read-only into the Python process. It neither copies the file nor modifies that worktree. Existing process environment takes precedence. The reader supports server environment variables `GEMINI_API_KEY` and `GEMINI_MODEL`, with its adjacent `medisaathi/.env` as fallback. Never set VITE-prefixed secret variables. Startup does not call Gemini, including model listing.

## Frontend (second terminal)

```powershell
Set-Location C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET = 'http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Use `http://localhost:5177` consistently. Existing authentication cookies are sent through the `/api` proxy. No authentication architecture or SQLite account data changes are required.

## Verification and limits

Offline tests exercise the actual real-mode factory and reader using a mocked Google SDK: arbitrary nonfixture PNG/JPEG acceptance; literal Hindi/mixed source preservation; no extraction on upload; one SDK invocation for a valid response; failure without fake records; invalid/oversized file rejection; mandatory review before confirmation. Existing suites cover other scopes and safeguards. This is not real end-to-end Gemini verification or an OCR accuracy benchmark.

The original AI workspace credential file contains both required configuration values (presence checked without displaying them). Availability, permissions and quota require a deliberately triggered real request. Only click Analyze when ready to send that image to Gemini. For a first manual test use synthetic, non-patient data, select only the medicine scope, inspect returned records, save corrections and explicitly confirm before explanation. Do not use this normal runtime to bypass any separately guarded diagnostic attempt.

The normal reader's existing malformed-response retry policy is unchanged; this is not the one-provider-call diagnostic runner. No live Gemini or Telegram request was made during these changes. Real handwritten recognition remains experimental and real multilingual accuracy is unmeasured.
