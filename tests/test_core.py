from types import SimpleNamespace
from unittest.mock import Mock
import json

import httpx2 as httpx
import pytest
from openai import AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError, BadRequestError
from pydantic import ValidationError

from core import CRITERIA, Draft, JobInput, Quality, JDService, UserError, validate_jd, quality_markdown

SOURCE = "HR specialist in Riyadh. Maintain employee files, coordinate recruitment and prepare monthly reports. Excel and communication skills required."


def quality(score=7):
    return Quality(**{k: {"score": score, "evidence": "Evidence from supplied JD", "recommendation": "Add measurable outcomes"} for k in CRITERIA}, summary="Review role-specific detail.")


def service(result):
    client = Mock()
    client.responses.parse.return_value = SimpleNamespace(status="completed", output_parsed=result)
    return JDService("test-key", client=client), client


@pytest.mark.parametrize("score,expected", [(0, 0), (7, 70), (10, 100)])
def test_score_boundaries(score, expected):
    assert quality(score).total == expected


def test_weighted_score():
    q = quality(0)
    q.clarity.score = 10
    q.kpis.score = 5
    assert q.total == 25
    assert "25/100" in quality_markdown(q)


@pytest.mark.parametrize("text", ["", " " * 90, "x" * 79, "x" * 16001])
def test_reject_invalid_source(text):
    with pytest.raises(UserError):
        validate_jd(text)


def test_input_limits():
    assert len(validate_jd("x" * 16000)) == 16000
    assert validate_jd("  " + SOURCE + "  ") == SOURCE
    with pytest.raises(ValidationError):
        quality(11)


def test_generate_contract():
    draft = Draft(jd=SOURCE, notes=["Confirm proposed KPIs."])
    svc, client = service(draft)
    job = JobInput(title="HR specialist", department="HR", seniority="Mid-level", industry="Services",
                   location="Riyadh", work_type="On-site", requirements="Excel and recruitment", language="English")
    assert svc.generate(job) == draft
    call = client.responses.parse.call_args.kwargs
    assert call["store"] is False
    assert call["text_format"] is Draft
    assert json.loads(call["input"][1]["content"])["title"] == "HR specialist"
    assert "untrusted DATA" in call["input"][0]["content"]


def test_improve_and_analyze_contracts():
    svc, client = service(Draft(jd=SOURCE, notes=[]))
    assert svc.improve(SOURCE, "Arabic").jd == SOURCE
    assert json.loads(client.responses.parse.call_args.kwargs["input"][1]["content"])["source_jd"] == SOURCE
    client.responses.parse.return_value.output_parsed = quality()
    assert svc.analyze(SOURCE, "Arabic").total == 70
    assert client.responses.parse.call_args.kwargs["text_format"] is Quality
    assert "Assess ONLY the supplied JD" in client.responses.parse.call_args.kwargs["input"][0]["content"]


@pytest.mark.parametrize("status,result", [("incomplete", None), ("completed", None), ("completed", {"jd": "short", "notes": []})])
def test_refusal_truncation_invalid_output(status, result):
    svc, client = service(result)
    client.responses.parse.return_value.status = status
    with pytest.raises(UserError):
        svc.improve(SOURCE, "English")


@pytest.mark.parametrize("error_cls,code", [(AuthenticationError, 401), (RateLimitError, 429), (BadRequestError, 400)])
def test_api_error_redaction(error_cls, code):
    svc, client = service(None)
    response = httpx.Response(code, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    client.responses.parse.side_effect = error_cls("SECRET SHOULD NOT APPEAR", response=response, body=None)
    with pytest.raises(UserError) as exc:
        svc.analyze(SOURCE, "English")
    assert "SECRET" not in str(exc.value)


@pytest.mark.parametrize("error_cls", [APIConnectionError, APITimeoutError])
def test_connection_errors(error_cls):
    svc, client = service(None)
    client.responses.parse.side_effect = error_cls(request=httpx.Request("POST", "https://api.openai.com"))
    with pytest.raises(UserError):
        svc.analyze(SOURCE, "English")


def test_no_key_and_no_call_on_invalid_input():
    with pytest.raises(UserError):
        JDService(" ")
    svc, client = service(None)
    with pytest.raises(UserError):
        svc.improve("short", "English")
    client.responses.parse.assert_not_called()


def test_real_sdk_serialization_and_structured_parsing():
    """Exercise the installed SDK with a local HTTP transport; no network or key."""
    from openai import OpenAI
    requests = []
    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(200, json={
            "id": "resp_test", "object": "response", "created_at": 0, "status": "completed",
            "model": "gpt-4.1-mini", "output": [{"type": "message", "id": "msg_test", "role": "assistant",
                "status": "completed", "content": [{"type": "output_text", "text": quality(6).model_dump_json(), "annotations": []}]}],
        })
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with OpenAI(api_key="test-key", http_client=http_client, max_retries=0) as client:
            result = JDService("test-key", client=client).analyze(SOURCE, "English")
    assert result.total == 60
    assert requests[0]["store"] is False
    assert requests[0]["text"]["format"]["type"] == "json_schema"
    assert requests[0]["text"]["format"]["strict"] is True
