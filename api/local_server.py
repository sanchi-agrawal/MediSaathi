"""Local accounts; offline OCR by default, with explicit normal-factory opt-in."""
from .local_auth import create_local_app
import os
app=create_local_app(offline=os.getenv('MEDISAATHI_LOCAL_OFFLINE','1')!='0')
