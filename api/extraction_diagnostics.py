"""Persist allowlisted diagnostics without bodies, identifiers or credentials."""
import json,logging,os,secrets,threading
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from extraction_errors import observe
_lock=threading.Lock()
PATH=Path(__file__).parent/'runtime'/'extraction-errors.jsonl'

@contextmanager
def scope(section):
    reference=secrets.token_hex(8)
    def write(diagnostic):
        safe={key:diagnostic[key] for key in ('category','failure_stage','exception_type',
              'upstream_exception_type','provider_http_status','provider_response_observed')}
        safe.update(section=section,timestamp=datetime.now(timezone.utc).isoformat(),
                    diagnostic_reference=reference,
                    runtime_kind='test' if os.getenv('PYTEST_CURRENT_TEST') else 'app')
        with _lock:
            PATH.parent.mkdir(parents=True,exist_ok=True)
            with PATH.open('a',encoding='utf8') as output:output.write(json.dumps(safe)+'\n')
        logging.getLogger(__name__).warning('Extraction failed: category=%s status=%s',safe['category'],safe['provider_http_status'])
    with observe(write):
        yield reference
