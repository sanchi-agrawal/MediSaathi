"""Allowlisted diagnostics; never serialize exception messages or provider bodies.

Capture while handling the error: suppressed __context__ survives 'from None'.
Completed historical exceptions cannot be recovered. Walk both wrapping branches
with bounded traversal and prefer captured provider status over generic transport.
"""
import httpx
from google.genai import errors
from api.dependencies import reader


def _provider_result(base, code, upstream):
    code = code if type(code) is int and 100 <= code <= 599 else None
    result = {**base, "upstream_exception_type":upstream,
              "provider_http_status":code, "provider_response_observed":code is not None,
              "failure_stage":"provider_response", "category":"provider_api_error"}
    if code == 429:
        result["category"] = "quota_or_rate_limit"
    elif code == 401:
        result["category"] = "authentication_error"
    elif code == 403:
        result["category"] = "permission_error"
    elif code == 404:
        result["category"] = "model_or_resource_unavailable"
    elif code == 400:
        result["category"] = "provider_bad_request"
    elif code is not None and code >= 500:
        result["category"] = "provider_server_error"
    elif code is not None and 400 <= code < 500:
        result["category"] = "provider_client_error"
    return result


def safe_failure_diagnostics(error):
    result = {"category":"unexpected_backend_error", "failure_stage":"unknown",
              "exception_type":"Exception", "upstream_exception_type":None,
              "provider_http_status":None, "provider_response_observed":False}
    for cls in (reader.PrescriptionAPIError, reader.ModelResponseError,
                reader.ReaderConfigurationError, reader.ImageInputError):
        if isinstance(error, cls):
            result["exception_type"] = cls.__name__
            break
    seen, pending = set(), [error]
    transport = None
    http_status = None
    unknown_provider = None
    while pending and len(seen) < 16:
        current = pending.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, errors.APIError):
            upstream = "ClientError" if isinstance(current,errors.ClientError) else "ServerError" if isinstance(current,errors.ServerError) else "APIError"
            candidate = _provider_result(result,current.code,upstream)
            if candidate["provider_http_status"] is not None:
                return candidate
            unknown_provider = candidate
        elif isinstance(current,httpx.HTTPStatusError):
            candidate = _provider_result(result,current.response.status_code,"HTTPStatusError")
            if candidate["provider_http_status"] is not None:
                http_status = candidate
        elif isinstance(current,(httpx.TimeoutException,TimeoutError)):
            transport = {**result,"category":"network_timeout","failure_stage":"transport",
                         "upstream_exception_type":"TimeoutError"}
        elif isinstance(current,(httpx.HTTPError,ConnectionError)) and transport is None:
            transport = {**result,"category":"network_error","failure_stage":"transport",
                         "upstream_exception_type":"HTTPError"}
        pending.extend((current.__cause__,current.__context__))
    if http_status is not None:
        return http_status
    if unknown_provider is not None:
        return unknown_provider
    if transport is not None:
        return transport
    if isinstance(error,reader.ModelResponseError):
        result.update(category="invalid_response",failure_stage="response_validation")
    elif isinstance(error,reader.ReaderConfigurationError):
        result.update(category="configuration_error",failure_stage="configuration")
    elif isinstance(error,reader.ImageInputError):
        result.update(category="image_validation_error",failure_stage="image_validation")
    elif isinstance(error,reader.PrescriptionAPIError):
        result.update(category="api_or_transport_error_unknown",failure_stage="reader_api_boundary")
    return result
