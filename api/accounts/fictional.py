"""Manual acceptance mode: REAL configured accounts/storage, fictional OCR only.

Importing demo_fixture blocks the Google SDK and supplies hash-registered images.
No fake account provider is installed here. Missing Supabase remains unavailable.
"""
from ..demo_fixture import factory,check
from ..main import create_app
app=create_app(factory=factory,upload_validator=check)
@app.get('/api/demo-info')
def info():return {'mode':'fictional-ocr-real-auth','gemini_enabled':False,'notifications_enabled':False,'auth_configured':app.state.accounts is not None}
