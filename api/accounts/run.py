"""Local server entrypoint. Load private configuration before importing the app."""
import os
from pathlib import Path
from dotenv import load_dotenv,dotenv_values
def main():
    load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
    original=os.getenv('MEDISAATHI_GEMINI_ENV_FILE')
    if original:
        values=dotenv_values(original)
        for field in ('GEMINI_API_KEY','GEMINI_MODEL'):
            if values.get(field) and not os.getenv(field):os.environ[field]=values[field]
    import uvicorn
    target='api.accounts.fictional:app' if os.getenv('MEDISAATHI_FICTIONAL_OCR')=='1' else 'api.main:app'
    uvicorn.run(target,host='127.0.0.1',port=int(os.getenv('MEDISAATHI_API_PORT','8000')),access_log=False)
if __name__=='__main__':main()
