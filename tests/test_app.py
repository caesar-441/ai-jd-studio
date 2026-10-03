from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from core import Draft, UserError
from test_core import SOURCE, quality

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def button(at, label):
    return next(b for b in at.button if label in b.label)


def test_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert button(at, "Generate JD").disabled
    at.radio[0].set_value("تحسين / Improve").run()
    assert not at.exception
    button(at, "Load sample").click().run()
    assert len(at.text_area[0].value) > 80
    assert button(at, "Improve JD").disabled


def test_create_score_download_persistence_and_clear(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    at = AppTest.from_file(APP).run()
    button(at, "Generate JD").click().run()
    assert at.error
    values = ["HR Specialist", "HR", "Services", "Riyadh"]
    for field, value in zip(at.text_input, values):
        field.set_value(value)
    at.text_area[0].set_value("Employee records, recruitment, Excel")
    with patch("core.JDService.generate", return_value=Draft(jd=SOURCE, notes=["Confirm KPIs"])):
        button(at, "Generate JD").click().run()
    assert not at.exception
    assert at.session_state["create_result"]["draft"].jd == SOURCE
    assert len(at.get("download_button")) == 2
    assert at.code[0].value == SOURCE
    at.session_state["last_request"] = -100
    with patch("core.JDService.analyze", return_value=quality()):
        button(at, "Analyze this draft").click().run()
    assert not at.exception
    assert at.metric[0].value == "70/100"
    assert len(at.get("download_button")) == 3
    at.radio[0].set_value("تحسين / Improve").run()
    at.radio[0].set_value("إنشاء / Create").run()
    assert at.metric[0].value == "70/100"
    button(at, "Clear session").click().run()
    assert not at.exception
    assert len(at.metric) == 0


def test_analyze_to_improve_and_error_keeps_result(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    at = AppTest.from_file(APP).run()
    at.radio[0].set_value("تحليل / Analyze").run()
    at.text_area[0].set_value(SOURCE)
    with patch("core.JDService.analyze", return_value=quality(4)):
        button(at, "Analyze quality").click().run()
    assert not at.exception
    assert at.metric[0].value == "40/100"
    button(at, "Improve this JD").click().run()
    assert not at.exception
    assert at.radio[0].value == "تحسين / Improve"
    assert at.text_area[0].value == SOURCE
    at.session_state["last_request"] = -100
    with patch("core.JDService.improve", return_value=Draft(jd=SOURCE + "\nProposed KPI: reporting accuracy.", notes=["Proposed KPI"])):
        button(at, "Improve JD").click().run()
    assert not at.exception
    saved = at.session_state["improve_result"]["draft"].jd
    at.session_state["last_request"] = -100
    with patch("core.JDService.improve", side_effect=UserError("Connection failed")):
        button(at, "Improve JD").click().run()
    assert at.error[0].value == "Connection failed"
    assert at.session_state["improve_result"]["draft"].jd == saved
    assert not at.exception


def test_no_accidental_debug_output(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert len(at.get("doc_string")) == 0
    assert len(at.code) == 0


def test_generated_html_and_links_are_inert(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    at = AppTest.from_file(APP).run()
    content = SOURCE + '\n## Skills\n- **Excel**\n<img src="https://invalid.example/pixel">\n![image](https://invalid.example/pixel)'
    at.session_state["create_result"] = {"draft": Draft(jd=content, notes=[]), "quality": None, "language": "English"}
    at.run()
    rendered = "\n".join(element.value for element in at.markdown)
    assert "<img src=" not in rendered
    assert "&lt;img" in rendered
    assert '<h4 dir="auto">Skills</h4>' in rendered
    assert '<strong>Excel</strong>' in rendered
    assert not at.exception
