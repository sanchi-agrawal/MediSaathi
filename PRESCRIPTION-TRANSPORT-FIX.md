# Prescription transport verification

The failure reproduced through `http://localhost:5177` was `POST /api/prescriptions`: HTTP 500, plain text. The local API was in offline fixture mode. Uploading the older `api/smoke/fictional_demo.png` raised `reader.ImageInputError` in the fixture validator before AIIntegration's exception wrapper. It was not an authentication or proxy-routing failure. A fresh authenticated current-prescription lookup correctly returned JSON 404 (`no_current_prescription`).

The API now handles the validator exception as JSON HTTP 422, `image_validation_error`, without exposing input or weakening validation. In offline mode the message identifies the registered fixture. A rejected replacement preserves the existing reviewed/confirmed analysis. Authentication code, password storage and confirmation contracts are unchanged by this fix.

The running API was restarted on port 8005 with `MEDISAATHI_LOCAL_OFFLINE=1`. Existing SQLite accounts and authentication tokens remain; in-memory medical workspaces reset on restart. The Vite proxy on port 5177 reaches this API. Gemini configuration is incomplete in the checked server environment; this mode never calls Gemini. Do not present fixture simulation as actual OCR.

## Start offline locally (PowerShell, repository root)

```powershell
$env:PYTHONPATH = 'C:\Users\ASHTAMI\MediSaathi-TeamIntegration\api\.venv\deps'
$env:MEDISAATHI_LOCAL_OFFLINE = '1'
$env:MEDISAATHI_LOCAL_HTTPS = '0' # Loopback HTTP only; HTTPS uses Secure cookies.
$python = 'C:\Users\ASHTAMI\MediSaathi-Frontend\api\.venv\Scripts\python.exe'
& $python -m api.demo_fixture --write-fixtures
& $python -m uvicorn api.local_server:app --host 127.0.0.1 --port 8005 --no-access-log --no-proxy-headers
```

In another terminal:

```powershell
Set-Location C:\Users\ASHTAMI\MediSaathi-TeamIntegration\frontend
$env:MEDISAATHI_PROXY_TARGET = 'http://127.0.0.1:8005'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
```

Use `http://localhost:5177` consistently. Sign in, select `api/.venv/demo16c/fictional-prescription.png`, explicitly run the fixture simulation, review/save all fields, explicitly confirm and request explanations. Navigate away/back and refresh to verify restoration. An unrelated PNG must produce a JSON validation error and no success state. These steps still need human browser verification; the same route sequence passed HTTP verification through Vite with a disposable account, which was deleted afterward.

No Gemini/Telegram calls, commits, pushes or diagnostic guard changes were made. Real mode requires server-only Gemini configuration and separately authorized provider testing; it was not enabled here.
