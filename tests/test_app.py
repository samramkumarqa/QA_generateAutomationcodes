"""Click through the Streamlit UI with the crawl and the model replaced by offline stand-ins."""

import io
import zipfile

from streamlit.testing.v1 import AppTest

from conftest import ROOT, SAVED_CRAWL
from fakes import FakePlannerLLM


def _app(monkeypatch, any_site=False, plans=None):
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
    monkeypatch.setattr(pwgen.llm, "GroqLLM", lambda api_key, model: FakePlannerLLM(*([plans] if plans else [])))
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
    assert not at.warning  # the sample pack fits saucedemo
    assert any("4 of 6 tests are fully automated" in c.value for c in at.caption)

    dl = next(b for b in at.get("download_button") if "Playwright project" in b.proto.label)
    assert dl.proto.label.startswith("⬇️ Download Playwright project")


def test_local_mode_asks_for_url_and_credentials(monkeypatch):
    at, _ = _app(monkeypatch, any_site=True)
    at.run()
    _button(at, "Use sample test pack").click().run()
    labels = [t.label for t in at.text_input]
    assert {"Login page URL", "Username", "Password"} <= set(labels)
    assert _button(at, "🕷️ Crawl").disabled  # no URL yet


def test_warns_when_test_cases_dont_fit_the_crawled_app(monkeypatch):
    from fakes import PRACTICE_SHOP_PLANS

    # Test cases for another app: only the first step of each maps, the rest can't.
    plans = {}
    for k, p in PRACTICE_SHOP_PLANS.items():
        q = p.model_copy(deep=True)
        q.unmapped = [s.comment for s in q.steps[1:]]
        q.steps = q.steps[:1]
        plans[k] = q
    at, _ = _app(monkeypatch, plans=plans)
    at.run()
    _button(at, "Use sample test pack").click().run()
    _button(at, "🕷️ Crawl").click().run()
    _button(at, "⚙️ Generate code").click().run()
    assert not at.exception, at.exception
    assert any("of the test steps match elements" in w.value for w in at.warning)
    assert any("0 of 6 tests are fully automated" in c.value for c in at.caption)
