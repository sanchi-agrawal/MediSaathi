import copy
import threading
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.dependencies import AIIntegration, reader
from api.main import create_app
from api.sessions import COOKIE, TTL_SECONDS

HEADERS = {"Origin": "http://localhost:5173", "X-MediSaathi-Action": "review"}
RECORD = dict(raw_text="Fictional-A BD", name="Fictional-A", salt=None, strength=None,
              form="tablet", frequency_pattern="BD", duration_days=None, timing=None,
              confidence=None, needs_review=True)


def image_bytes(fmt="PNG", size=(4, 4)):
    stream = BytesIO()
    Image.new("RGB", size, "white").save(stream, format=fmt)
    return stream.getvalue()


def make_client(extractor=None, **kwargs):
    factory = lambda: AIIntegration(extractors={"medicines": extractor or (lambda _: [copy.deepcopy(RECORD)])})
    app = create_app(factory=factory, **kwargs)
    client = TestClient(app, base_url="https://localhost", headers=HEADERS)
    response = client.post("/api/session")
    assert response.status_code == 200
    return client, app


def upload(client, data=None, mime="image/png"):
    response = client.post("/api/prescriptions", content=image_bytes() if data is None else data,
                           headers={"Content-Type": mime})
    assert response.status_code == 200, response.text
    return response.json()


def post(client, state, action, **extra):
    return client.post(f'/api/prescriptions/{state["analysis_id"]}/{action}',
                       json={"revision": state["revision"], **extra})


def extracted(client):
    return post(client, upload(client), "analyze").json()


def reviewed(client, state=None, records=None):
    state = state or extracted(client)
    return client.put(f'/api/prescriptions/{state["analysis_id"]}/review',
                      json={"revision": state["revision"], "records": state["records"] if records is None else records})


def confirmed(client):
    state = reviewed(client).json()
    response = post(client, state, "confirm")
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("language", ["en", "hi", "hinglish"])
def test_real_adapter_review_confirm_explain(language):
    calls = []
    client, _ = make_client(lambda data: calls.append(data) or [copy.deepcopy(RECORD)])
    state = upload(client)
    assert calls == []  # upload/status never call Gemini
    assert client.get(f'/api/prescriptions/{state["analysis_id"]}').status_code == 200
    assert calls == []
    state = post(client, state, "analyze").json()
    assert len(calls) == 1
    assert state["records"] == [RECORD]
    assert set(state["records"][0]) == set(RECORD)
    assert post(client, state, "confirm").status_code == 409
    assert post(client, state, "explanation", language=language).status_code == 409
    state = reviewed(client, state).json()
    state = post(client, state, "confirm").json()
    assert state["confirmed"] is True
    result = post(client, state, "explanation", language=language).json()
    assert result["payload"]["language"] == language
    assert result["payload"]["medicines"][0]["record"]["salt"] is None
    assert result["payload"]["issues"]
    assert len(calls) == 1


def test_cookie_flags_and_origin_checks():
    client, app = make_client()
    fresh = TestClient(app, base_url="https://localhost", headers=HEADERS)
    cookie = fresh.post("/api/session").headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
    assert fresh.post("/api/session", headers={"Origin": "http://evil.example"}).status_code == 403
    assert TestClient(app, base_url="https://localhost").post("/api/session").status_code == 403
    response = client.get("/api/health")
    assert response.headers["cache-control"] == "no-store"
    preflight = client.options("/api/session", headers={"Origin":"http://localhost:5173","Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"X-MediSaathi-Action"})
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert preflight.headers["access-control-allow-credentials"] == "true"


def test_stale_analysis_and_revisions():
    client, _ = make_client()
    first = extracted(client)
    saved = reviewed(client, first).json()
    assert post(client, first, "confirm").status_code == 409
    second = upload(client)
    assert second["analysis_id"] != first["analysis_id"]
    assert post(client, saved, "confirm").status_code == 409
    assert client.get(f'/api/prescriptions/{first["analysis_id"]}').status_code == 409


def test_cross_session_cannot_confirm_or_read():
    client, app = make_client()
    state = confirmed(client)
    other = TestClient(app, base_url="https://localhost", headers=HEADERS)
    other.post("/api/session")
    assert post(other, state, "confirm").status_code == 409
    assert post(other, state, "explanation", language="en").status_code == 409
    assert other.get(f'/api/prescriptions/{state["analysis_id"]}').status_code == 409
    assert len(app.state.sessions.sessions) == 2


@pytest.mark.parametrize("extra", [{"event": "forged"}, {"acknowledged": True}, {"records": [dict(RECORD, dose=99)]}, {"scope": "instructions"}])
def test_forged_confirmation_payload_rejected(extra):
    client, _ = make_client()
    state = reviewed(client).json()
    response = post(client, state, "confirm", **extra)
    assert response.status_code == 422
    assert "Fictional-A" not in response.text
    assert post(client, state, "explanation", language="en").status_code == 409


@pytest.mark.parametrize("records", [[dict(RECORD, dose_quantity=2)], [{k:v for k,v in RECORD.items() if k!='salt'}], [dict(RECORD,duration_days=True)], [dict(RECORD,confidence="0.9")]])
def test_exact_ten_fields_and_strict_types(records):
    client, _ = make_client()
    state = extracted(client)
    assert reviewed(client, state, records).status_code == 422
    assert post(client, state, "confirm").status_code == 409


def test_edits_and_invalidation_block_old_explanations():
    client, app = make_client()
    state = confirmed(client)
    assert post(client, state, "explanation", language="en").status_code == 200
    dirty = post(client, state, "invalidate").json()
    assert not dirty["confirmed"] and not dirty["reviewed"]
    assert post(client, state, "explanation", language="en").status_code == 409
    assert post(client, dirty, "explanation", language="en").status_code == 409
    assert post(client, dirty, "confirm").status_code == 409
    saved = reviewed(client, dirty, [dict(RECORD,name="Corrected fictional text")]).json()
    session = next(iter(app.state.sessions.sessions.values()))
    assert session.ai.snapshot()["confirmed_scopes"] == []
    assert session.ai.snapshot()["derived"] == {}
    assert session.explanation is None
    assert not saved["confirmed"]
    saved = post(client, saved, "confirm").json()
    result = post(client, saved, "explanation", language="en").json()
    assert result["payload"]["medicines"][0]["record"]["name"] == "Corrected fictional text"


def test_empty_success_is_not_failure():
    client, _ = make_client(lambda _: [])
    state = extracted(client)
    assert state["status"] == "succeeded" and state["records"] == [] and state["error"] is None
    state = reviewed(client, state).json()
    state = post(client,state,"confirm").json()
    assert post(client,state,"explanation",language="en").json()["payload"]["status"] == "empty"


def test_malformed_extractor_result_is_failure_not_empty_success():
    client, _ = make_client(lambda _: [dict(RECORD, dose_quantity=99)])
    state = extracted(client)
    assert state["status"] == "failed"
    assert state["error"]["category"] == "invalid_response"
    assert state["records"] is None
    assert post(client,state,"confirm").status_code == 409


def test_rejected_edit_removes_existing_confirmation_gate():
    client, _ = make_client()
    state = confirmed(client)
    assert reviewed(client,state,[dict(RECORD,dose_quantity=99)]).status_code == 422
    fresh = client.get(f'/api/prescriptions/{state["analysis_id"]}').json()
    assert fresh["confirmed"] is False
    assert post(client,fresh,"explanation",language="en").status_code == 409


def test_failed_extraction_can_only_retry_explicitly():
    count = []
    def extract(_):
        count.append(1)
        if len(count) == 1:
            raise reader.PrescriptionAPIError("private provider message")
        return []
    client, _ = make_client(extract)
    state = extracted(client)
    assert state["status"] == "failed" and state["records"] is None
    assert state["error"]["category"] == "api_error"
    assert "private provider message" not in str(state)
    client.get(f'/api/prescriptions/{state["analysis_id"]}')
    assert len(count) == 1
    state = post(client, state,"analyze").json()
    assert state["status"] == "succeeded" and state["records"] == [] and len(count) == 2
    assert post(client,state,"analyze").status_code == 409


@pytest.mark.parametrize("data,mime,status", [(b"invalid","image/png",422),(b"","image/jpeg",422),(b"GIF89a","image/png",422),(b"x"*(reader.MAX_IMAGE_BYTES+1),"image/png",413),(b"text","text/plain",415)], ids=["corrupt","empty","gif","oversized","wrong-mime"])
def test_invalid_and_oversized_images(data,mime,status):
    client, _ = make_client()
    assert client.post("/api/prescriptions",content=data,headers={"Content-Type":mime}).status_code == status


def test_pixel_limit_and_jpeg_and_multiframe():
    client, _ = make_client()
    big = image_bytes(size=(4001,2000))
    assert client.post("/api/prescriptions",content=big,headers={"Content-Type":"image/png"}).status_code == 422
    assert upload(client,image_bytes(fmt="JPEG"),"image/jpeg")["status"] == "not_requested"
    stream = BytesIO()
    Image.new("RGB",(4,4)).save(stream,format="PNG",save_all=True,append_images=[Image.new("RGB",(4,4),"red")])
    assert client.post("/api/prescriptions",content=stream.getvalue(),headers={"Content-Type":"image/png"}).status_code == 422


def test_expiry_capacity_clear_and_disabled_routes():
    client, app = make_client(session_limit=1)
    newcomer = TestClient(app,base_url="https://localhost",headers=HEADERS)
    assert newcomer.post("/api/session").status_code == 503
    state = confirmed(client)
    assert client.delete("/api/prescriptions/current").status_code == 200
    assert post(client,state,"explanation",language="en").status_code == 409
    for route in ("schedule","pricing","reminders","instructions","strip"):
        assert post(client,state,route).status_code == 404
    session = next(iter(app.state.sessions.sessions.values()))
    session.created -= TTL_SECONDS+1
    assert client.get(f'/api/prescriptions/{state["analysis_id"]}').status_code == 401
    assert client.post("/api/session").status_code == 200


def test_replacement_during_extraction_cannot_attach_stale_result():
    started, release = threading.Event(), threading.Event()
    def extract(_):
        started.set()
        assert release.wait(5)
        return [copy.deepcopy(RECORD)]
    client, _ = make_client(extract)
    state = upload(client)
    responses = []
    worker = threading.Thread(target=lambda: responses.append(post(client,state,"analyze")))
    worker.start()
    assert started.wait(5)
    status = client.get(f'/api/prescriptions/{state["analysis_id"]}').json()
    assert status["status"] == "running"
    replacement = upload(client)
    release.set();worker.join(5)
    assert responses[0].status_code == 409
    current = client.get(f'/api/prescriptions/{replacement["analysis_id"]}').json()
    assert current["status"] == "not_requested" and current["records"] is None
