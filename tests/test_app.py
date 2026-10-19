"""Click through the Streamlit UI with the crawl and the model replaced by offline stand-ins."""

import io
import zipfile

from streamlit.testing.v1 import AppTest

from conftest import ROOT, SAVED_CRAWL
from fakes import FakePlannerLLM


def _app(monkeypatch, any_site=False):
    import pwgen.crawler
    import pwgen.llm
    from pwgen.schemas import CrawlResult

    calls = {}

    def fake_crawl(url, username, password, **kw):
        calls.update(url=url, username=username)
        return CrawlResult.model_validate_json(SAVED_CRAWL.read_text())

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("ALLOW_ANY_SITE", "true" if any_site else "false")
    monkeypatch.setattr(pwgen.crawler, "crawl", fake_crawl)
    monkeypatch.setattr(pwgen.crawler, "ensure_browser", lambda: None)
    monkeypatch.setattr(pwgen.llm, "GroqLLM", lambda api_key, model: FakePlannerLLM())
    return AppTest.from_file(str(ROOT / "main.py"), default_timeout=60), calls


def _button(at, label):
    return next(b for b in at.button if b.label.startswith(label))


def test_demo_mode_full_flow(monkeypatch):
    at, calls = _app(monkeypatch)
    at.run()
    assert not at.exception
    _button(at, "Use sample test pack").click().run()
    assert any("6 test cases loaded" in s.value for s in at.success)

    # Demo mode: only the practice sites, credentials pre-filled.
    site = next(s for s in at.selectbox if s.label == "Practice site")
    assert site.options[0].startswith("Swag Labs")
    _button(at, "🕷️ Crawl").click().run()
    assert not at.exception, at.exception
    assert calls == {"url": "https://www.saucedemo.com/", "username": "standard_user"}
    assert any("6 pages" in s.value for s in at.success)

    _button(at, "⚙️ Generate code").click().run()
    assert not at.exception, at.exception
    assert [m.value for m in at.metric] == ["6", "31", "2", "28"]

    dl = next(b for b in at.get("download_button") if "Playwright project" in b.proto.label)
    assert dl.proto.label.startswith("⬇️ Download Playwright project")


def test_local_mode_asks_for_url_and_credentials(monkeypatch):
    at, _ = _app(monkeypatch, any_site=True)
    at.run()
    _button(at, "Use sample test pack").click().run()
    labels = [t.label for t in at.text_input]
    assert {"Login page URL", "Username", "Password"} <= set(labels)
    assert _button(at, "🕷️ Crawl").disabled  # no URL yet
