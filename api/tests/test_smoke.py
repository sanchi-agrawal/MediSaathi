"""Offline smoke-runner regressions. 'Live' tests inject a fake reader only."""
import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.dependencies import reader
from api.smoke.server import create_smoke_app, fixture_validator, load_credentials

HEADERS = {"Origin":"http://localhost:5173", "X-MediSaathi-Action":"review"}
FIXTURE = Path(__file__).resolve().parents[1] / "smoke/fictional_demo.png"


def client_for(app):
    client = TestClient(app,base_url="https://localhost",headers=HEADERS)
    assert client.post("/api/session").status_code == 200
    return client


def upload(client,data):
    return client.post("/api/prescriptions",content=data,headers={"Content-Type":"image/png"})


def analyze(client,state):
    return client.post(f'/api/prescriptions/{state["analysis_id"]}/analyze',json={"revision":state["revision"]})


def reencoded_fixture():
    out = BytesIO()
    with Image.open(FIXTURE) as image:
        image.save(out,format="PNG",compress_level=9)
    return out.getvalue()


def test_fixture_full_decode_and_existing_limits():
    data = FIXTURE.read_bytes()
    with Image.open(BytesIO(data)) as image:
        assert image.format == "PNG"
        assert image.size == (541,721)
        assert image.n_frames == 1
        image.verify()
    with Image.open(BytesIO(data)) as image:
        image.load()
        assert image.width*image.height == 390061
    assert reader._validate_image(data) == "image/png"


def test_lossless_reencoded_fixture_is_not_invalid_image():
    original, changed = FIXTURE.read_bytes(), reencoded_fixture()
    assert original != changed
    assert reader._validate_image(changed) == "image/png"
    fixture_validator(original)(changed)
    client = client_for(create_smoke_app("mock"))
    state = upload(client,changed).json()
    result = analyze(client,state).json()
    assert result["status"] == "succeeded"
    assert result["error"] is None


def test_policy_mismatch_is_distinct_from_corrupt_image_and_does_not_consume_guard(tmp_path):
    app = create_smoke_app("live",result_path=tmp_path/"result.json")
    client = client_for(app)
    stream = BytesIO()
    Image.new("RGB",(4,4),"white").save(stream,format="PNG")
    response = upload(client,stream.getvalue())
    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "smoke_fixture_required"
    response = upload(client,b"corrupt")
    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "image_validation_error"
    assert not (tmp_path/"result.json").exists()
    assert client.get("/api/smoke/status").json()["live_attempt_available"]


def test_live_mode_passes_exact_bytes_to_real_reader_boundary_and_no_mock_fallback(monkeypatch,tmp_path):
    seen = []
    monkeypatch.setattr(reader,"read_prescription",lambda data: seen.append(data) or [])
    marker = tmp_path/"result.json"
    client = client_for(create_smoke_app("live",result_path=marker))
    assert seen == [] and not marker.exists()  # startup never extracts
    data = reencoded_fixture()
    first = analyze(client,upload(client,data).json()).json()
    assert first["status"] == "succeeded" and first["records"] == []
    assert seen == [data]
    second = analyze(client,upload(client,data).json()).json()
    assert second["status"] == "failed" and second["records"] is None
    assert len(seen) == 1
    assert not client.get("/api/smoke/status").json()["live_attempt_available"]
    with pytest.raises(RuntimeError,match="already recorded"):
        create_smoke_app("live",result_path=marker)


def test_live_failure_consumes_attempt_without_retry_or_mock_fallback(monkeypatch,tmp_path):
    calls = []
    def failing(data):
        calls.append(data)
        raise reader.PrescriptionAPIError("private provider response")
    monkeypatch.setattr(reader,"read_prescription",failing)
    marker = tmp_path/"result.json"
    client = client_for(create_smoke_app("live",result_path=marker))
    result = analyze(client,upload(client,FIXTURE.read_bytes()).json()).json()
    assert result["status"] == "failed" and result["records"] is None
    assert result["error"]["category"] == "api_error"
    assert len(calls) == 1
    assert "private provider response" not in json.dumps(result)
    assert "private provider response" not in marker.read_text()
    assert json.loads(marker.read_text())["status"] == "failed"
    analyze(client,result)
    assert len(calls) == 1


def test_existing_image_validation_is_not_weakened():
    client = client_for(create_smoke_app("mock"))
    response = upload(client,b"x"*(reader.MAX_IMAGE_BYTES+1))
    assert response.status_code == 413
    stream = BytesIO()
    Image.new("RGB",(4001,2000)).save(stream,format="PNG")
    assert upload(client,stream.getvalue()).status_code == 422


def test_credentials_loaded_in_server_environment_only(monkeypatch,tmp_path,capsys):
    path = tmp_path/"fictional.env"
    path.write_text("GEMINI_API_KEY=fake-test-key\nGEMINI_MODEL=fake-test-model\n")
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    monkeypatch.delenv("GEMINI_MODEL",raising=False)
    # Preserve env cleanup since the loader deliberately sets only process env.
    monkeypatch.setenv("GEMINI_API_KEY","")
    monkeypatch.setenv("GEMINI_MODEL","")
    assert load_credentials(path) == (True,"fake-test-model")
    assert capsys.readouterr().out == ""
