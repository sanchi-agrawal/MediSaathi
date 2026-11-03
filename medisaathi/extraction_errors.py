"""Request-local sanitized error observer. Never receives messages or records."""
from contextvars import ContextVar
from contextlib import contextmanager
_observer=ContextVar('extraction_error_observer',default=None)

@contextmanager
def observe(callback):
    token=_observer.set(callback)
    try:yield
    finally:_observer.reset(token)

def classify(error):
    # Reuse the existing tested allowlisted classifier; suppressed exception
    # context is inspected while the wrapped exception is still alive.
    from api.smoke.diagnostics import safe_failure_diagnostics
    diagnostic=safe_failure_diagnostics(error)
    callback=_observer.get()
    if callback:
        try:callback(diagnostic)
        except Exception:pass # A diagnostic sink must never change clinical state.
    return {'quota_or_rate_limit':'quota_exceeded','authentication_error':'authentication_error',
            'permission_error':'permission_denied','model_or_resource_unavailable':'model_unavailable',
            'provider_bad_request':'provider_bad_request','provider_server_error':'provider_error',
            'provider_client_error':'provider_error','network_timeout':'extraction_timeout',
            'network_error':'network_error'}.get(diagnostic['category'])
