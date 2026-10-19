"""Log in to a web app, visit every unique page, and record its interactive elements.

The crawl is read-only by design: it follows links and clicks link-like elements to discover
client-side navigation, but never clicks anything that looks destructive (logout, delete,
pay, ...) and never submits forms other than the login form.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter, deque
from collections.abc import Callable
from urllib.parse import urljoin, urlparse

from . import config
from .naming import element_name, page_class_name, unique, url_template
from .schemas import CrawlResult, Element, PageModel

Progress = Callable[[float, str], None]


class CrawlError(RuntimeError):
    pass


# Runs in the page: list candidate elements with everything needed to build a locator.
_COLLECT_JS = r"""
(max) => {
  const sel = 'a, button, input:not([type=hidden]), select, textarea, [role=button], [role=link],'
            + '[role=checkbox], [role=radio], [role=tab], [role=menuitem], [role=switch],'
            + 'h1, h2, h3, [role=alert], [role=status], [data-testid], [data-test], [data-qa], [data-cy]';
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(sel)) {
    if (seen.has(el)) continue; seen.add(el);
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    const visible = r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
    let label = '';
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) label = l.innerText; }
    if (!label && el.closest('label')) label = el.closest('label').innerText;
    const tag = el.tagName.toLowerCase();
    const text = (tag === 'input' ? (el.value || '') : (el.innerText || el.textContent || '')).trim().replace(/\s+/g, ' ');
    out.push({
      tag, visible,
      type: (el.getAttribute('type') || '').toLowerCase(),
      role: el.getAttribute('role') || '',
      id: el.id || '',
      nameAttr: el.getAttribute('name') || '',
      testids: { 'data-testid': el.getAttribute('data-testid') || '', 'data-test': el.getAttribute('data-test') || '',
                 'data-qa': el.getAttribute('data-qa') || '', 'data-cy': el.getAttribute('data-cy') || '' },
      placeholder: el.getAttribute('placeholder') || '',
      ariaLabel: el.getAttribute('aria-label') || '',
      label: label.trim().replace(/\s+/g, ' '),
      text: text.slice(0, 80),
      href: el.getAttribute('href') || '',
    });
    if (out.length >= max) break;
  }
  return out;
}
"""

_TEST_ID_ATTRS = ["data-testid", "data-test", "data-qa", "data-cy"]
_AUTO_ID = re.compile(r"(^\d|[0-9a-f]{6,}|:r\d|ember\d|^react-|^mui-)", re.I)


def ensure_browser() -> None:
    """Install Chromium for Playwright if it isn't there yet (first run on Streamlit Cloud)."""
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def _kind(raw: dict) -> str:
    tag, typ, role = raw["tag"], raw["type"], raw["role"]
    if role in {"button", "link", "checkbox", "radio"}:
        return role
    if role in {"tab", "menuitem", "switch"}:
        return "button"
    if role in {"alert", "status"}:
        return "text"
    if tag not in {"a", "button", "input", "select", "textarea"}:
        return "text"
    if tag == "a":
        return "link"
    if tag == "button" or typ in {"submit", "button", "reset", "image"}:
        return "button"
    if tag == "select":
        return "dropdown"
    if tag == "textarea":
        return "textarea"
    if typ in {"checkbox", "radio"}:
        return typ
    return "input"


_ROLE_FOR_KIND = {
    "button": "button", "link": "link", "checkbox": "checkbox", "radio": "radio",
    "dropdown": "combobox", "input": "textbox", "textarea": "textbox", "text": "heading",
}


def _is_unsafe(*texts: str) -> bool:
    blob = " ".join(t.lower() for t in texts if t)
    return any(w in blob for w in config.UNSAFE_WORDS)


def _changes_state(*texts: str) -> bool:
    blob = " ".join(t.lower() for t in texts if t)
    return any(w in blob for w in config.STATE_CHANGING_WORDS)


def _candidates(raw: dict, kind: str, test_id_attr: str) -> list[tuple[str, str, str]]:
    """Locator options in order of preference: (strategy, value, role)."""
    opts: list[tuple[str, str, str]] = []
    tid = raw["testids"].get(test_id_attr)
    if tid:
        opts.append(("testId", tid, ""))
    for attr in _TEST_ID_ATTRS:
        v = raw["testids"].get(attr)
        if v and attr != test_id_attr:
            opts.append(("css", f'[{attr}="{v}"]', ""))
    if raw["id"] and not _AUTO_ID.search(raw["id"]):
        opts.append(("css", f"#{raw['id']}" if raw["id"].replace("-", "").replace("_", "").isalnum()
                     else f'[id="{raw["id"]}"]', ""))
    acc_name = raw["ariaLabel"] or raw["label"] or (raw["text"] if kind not in {"input", "textarea", "dropdown"} else "")
    role = raw["role"] if raw["role"] in {"tab", "menuitem", "switch", "alert", "status"} else _ROLE_FOR_KIND.get(kind, "")
    if role and acc_name and kind != "text":
        opts.append(("role", acc_name, role))
    if raw["label"] and kind in {"input", "textarea", "dropdown", "checkbox", "radio"}:
        opts.append(("label", raw["label"], ""))
    if raw["placeholder"]:
        opts.append(("placeholder", raw["placeholder"], ""))
    if raw["nameAttr"]:
        opts.append(("css", f'{raw["tag"]}[name="{raw["nameAttr"]}"]', ""))
    if raw["text"] and kind in {"text", "link", "button"}:
        opts.append(("text", raw["text"], ""))
    return opts


def _locator(page, strategy: str, value: str, role: str, test_id_attr: str):
    if strategy == "testId":
        return page.locator(f'[{test_id_attr}="{value}"]')
    if strategy == "role":
        return page.get_by_role(role, name=value, exact=True)
    if strategy == "label":
        return page.get_by_label(value, exact=True)
    if strategy == "placeholder":
        return page.get_by_placeholder(value, exact=True)
    if strategy == "text":
        return page.get_by_text(value, exact=True)
    return page.locator(value)


def _describe(kind: str, raw: dict) -> str:
    shown = (raw["label"] or raw["ariaLabel"] or raw["placeholder"] or raw["text"] or raw["nameAttr"] or raw["id"]
             or next((v for v in raw["testids"].values() if v), ""))
    return f'{kind.capitalize()} "{shown[:50]}"' if shown else kind.capitalize()


def _build_elements(page, raws: list[dict], test_id_attr: str) -> list[Element]:
    taken: set[str] = set()
    seen_locators: set[tuple] = set()
    out: list[Element] = []
    for raw in raws:
        kind = _kind(raw)
        if kind == "link" and not (raw["text"] or raw["ariaLabel"] or any(raw["testids"].values()) or raw["id"]):
            continue  # anonymous link with nothing to name it by
        chosen = None
        for strategy, value, role in _candidates(raw, kind, test_id_attr):
            key = (strategy, value, role)
            if key in seen_locators:
                continue
            try:
                if _locator(page, strategy, value, role, test_id_attr).count() == 1:
                    chosen = key
                    break
            except Exception:
                continue
        if not chosen:
            continue
        seen_locators.add(chosen)
        source = (
            raw["testids"].get(test_id_attr) or raw["label"] or raw["ariaLabel"] or raw["placeholder"]
            or raw["text"] or raw["nameAttr"] or raw["id"] or kind
        )
        out.append(
            Element(
                name=element_name(source, kind, taken),
                kind="input" if kind == "textarea" else kind,
                strategy=chosen[0], value=chosen[1], role=chosen[2],
                description=_describe(kind, raw), visible=raw["visible"],
            )
        )
    return out


def _detect_test_id_attr(raws: list[dict]) -> str:
    counts = Counter(a for r in raws for a in _TEST_ID_ATTRS if r["testids"].get(a))
    return counts.most_common(1)[0][0] if counts else "data-testid"


def _settle(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(300)


def _login(page, username: str, password: str, user_sel: str = "", pass_sel: str = "", submit_sel: str = "") -> None:
    pwd = page.locator(pass_sel) if pass_sel else page.locator("input[type=password]:visible")
    if pwd.count() == 0:
        raise CrawlError("No password field found on the login page. Check the login URL.")
    pwd = pwd.first
    if user_sel:
        user = page.locator(user_sel).first
    else:
        # The visible text/email field closest before the password field.
        user = page.locator(
            "input:visible:not([type=password]):not([type=hidden]):not([type=checkbox]):not([type=radio])"
            ":not([type=submit]):not([type=button])"
        ).first
    if user.count() == 0:
        raise CrawlError("No username field found on the login page.")
    user.fill(username)
    pwd.fill(password)
    before = page.url
    if submit_sel:
        page.locator(submit_sel).first.click()
    else:
        form_submit = page.locator(
            "form button[type=submit]:visible, form input[type=submit]:visible, button:visible:has-text('log in'),"
            " button:visible:has-text('login'), button:visible:has-text('sign in')"
        )
        if form_submit.count():
            form_submit.first.click()
        else:
            pwd.press("Enter")
    try:
        page.wait_for_url(lambda u: u != before, timeout=config.NAV_TIMEOUT_MS)
    except Exception:
        pass
    _settle(page)
    if page.locator("input[type=password]:visible").count() and page.url == before:
        raise CrawlError("Login didn't succeed: still on the login page. Check the username and password.")


def crawl(
    start_url: str,
    username: str = "",
    password: str = "",
    *,
    max_pages: int = config.MAX_PAGES,
    selectors: dict | None = None,
    progress: Progress = lambda f, m: None,
    launch_options: dict | None = None,
) -> CrawlResult:
    from playwright.sync_api import sync_playwright

    selectors = selectors or {}
    origin = "{0.scheme}://{0.netloc}".format(urlparse(start_url))
    result = CrawlResult(base_url=origin, start_url=start_url)
    raw_pages: list[tuple[str, str, str, bool, list[dict]]] = []  # (template, url, title, is_login, raws)
    visited: set[str] = set()
    clicked_signatures: set[str] = set()

    def same_origin(u: str) -> bool:
        return urlparse(u).netloc == urlparse(origin).netloc

    with sync_playwright() as p:
        browser = p.chromium.launch(**(launch_options or {}))
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(config.NAV_TIMEOUT_MS)

        progress(0.02, f"Opening {start_url}")
        page.goto(start_url, wait_until="domcontentloaded")
        _settle(page)

        if username or password:
            raws = page.evaluate(_COLLECT_JS, config.MAX_ELEMENTS_PER_PAGE)
            key = url_template(page.url)
            raw_pages.append((key, page.url, page.title(), True, raws))
            visited.add(key)
            progress(0.06, "Logging in")
            _login(page, username, password, selectors.get("username", ""), selectors.get("password", ""),
                   selectors.get("submit", ""))

        queue: deque[str] = deque([page.url])
        while queue and len(raw_pages) < max_pages:
            url = queue.popleft()
            key = url_template(url)
            if key in visited:
                continue
            visited.add(key)
            progress(min(0.95, 0.1 + 0.85 * len(raw_pages) / max_pages), f"Page {len(raw_pages) + 1}: {urlparse(url).path}")
            try:
                if page.url != url:
                    page.goto(url, wait_until="domcontentloaded")
                    _settle(page)
            except Exception:
                result.skipped.append(f"{url} (failed to load)")
                continue
            if not same_origin(page.url):
                continue
            if url_template(page.url) != key and url_template(page.url) in visited:
                continue  # redirected to a page we already have (e.g. bounced to login)

            raws = page.evaluate(_COLLECT_JS, config.MAX_ELEMENTS_PER_PAGE)
            raw_pages.append((key, page.url, page.title(), False, raws))

            # 1) Plain links.
            for r in raws:
                if r["tag"] != "a" or not r["href"] or r["href"].startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                target = urljoin(page.url, r["href"])
                if not same_origin(target) or target.lower().endswith((".pdf", ".zip", ".png", ".jpg", ".csv", ".xlsx")):
                    continue
                if _is_unsafe(r["text"], r["href"]):
                    result.skipped.append(f"{target} (looks unsafe: {r['text'] or r['href']})")
                    continue
                if url_template(target) not in visited:
                    queue.append(target)

            # 2) Link-like elements that navigate with JavaScript (SPAs): click once each, note where we land.
            clicks = 0
            path = urlparse(url).path
            result.log.append(f"VISIT {path}: {len(raws)} elements")
            for idx, r in enumerate(raws):
                kind = _kind(r)
                label = (r["text"] or next((v for v in r["testids"].values() if v), "") or r["id"] or r["tag"])[:40]
                if clicks >= config.MAX_CLICKS_PER_PAGE:
                    break
                if not r["visible"]:
                    if kind == "link" and not (r["href"] and not r["href"].startswith(("#", "javascript:"))):
                        result.log.append(f"  skip  {kind} '{label}': not visible")
                    continue
                has_real_href = r["tag"] == "a" and r["href"] and not r["href"].startswith(("#", "javascript:"))
                navigational = (kind == "link" and not has_real_href) or (
                    kind == "button" and any(w in (r["text"] or "").lower() for w in config.NAV_BUTTON_WORDS)
                )
                labels = (r["text"], r["href"], r["id"], *r["testids"].values())
                if not navigational:
                    continue
                if _is_unsafe(*labels) or _changes_state(*labels):
                    result.log.append(f"  skip  {kind} '{label}': unsafe or changes data")
                    continue
                sig = url_template(url) + "|" + kind + "|" + re.sub(r"\d+", "N", r["id"] or r["text"])
                if sig in clicked_signatures:
                    result.log.append(f"  skip  {kind} '{label}': same as one already clicked")
                    continue
                clicked_signatures.add(sig)
                clicks += 1
                try:
                    # Fresh page before every click: an earlier click may have opened a menu or
                    # overlay that would block this one even though the URL didn't change.
                    page.goto(url, wait_until="domcontentloaded")
                    _settle(page)
                    page.locator(_COLLECT_SELECTOR_BY_INDEX).nth(idx).click(timeout=3000)
                    page.wait_for_timeout(config.SETTLE_MS)
                    landed = page.url
                    if landed == url or url_template(landed) == url_template(url):
                        result.log.append(f"  click {kind} '{label}': stayed on the page")
                    elif not same_origin(landed):
                        result.log.append(f"  click {kind} '{label}': left the site ({landed})")
                    else:
                        result.log.append(f"  click {kind} '{label}': -> {urlparse(landed).path}")
                        if url_template(landed) not in visited:
                            queue.append(landed)
                except Exception as exc:
                    result.log.append(f"  click {kind} '{label}': FAILED {type(exc).__name__}: {str(exc).splitlines()[0][:120]}")
                    continue
            if page.url != url:
                try:
                    page.goto(url, wait_until="domcontentloaded")
                except Exception:
                    pass

        ctx.close()
        browser.close()

        # Build page models (second pass needs a live page to verify locator uniqueness).
        all_raws = [r for *_, raws in raw_pages for r in raws]
        result.test_id_attribute = _detect_test_id_attr(all_raws)
        progress(0.96, "Choosing locators")
        browser = p.chromium.launch(**(launch_options or {}))
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(config.NAV_TIMEOUT_MS)
        class_names: set[str] = set()
        logged_in = False
        for key, url, title, is_login, raws in raw_pages:
            if not is_login and not logged_in and username:
                page.goto(start_url, wait_until="domcontentloaded")
                _settle(page)
                _login(page, username, password, selectors.get("username", ""), selectors.get("password", ""),
                       selectors.get("submit", ""))
                logged_in = True
            page.goto(url, wait_until="domcontentloaded")
            _settle(page)
            name = unique("LoginPage" if is_login else page_class_name(key, title), class_names)
            path = urlparse(url).path or "/"
            result.pages.append(
                PageModel(
                    name=name, url=path if ":id" not in key else path, title=title, is_login=is_login,
                    elements=_build_elements(page, raws, result.test_id_attribute),
                )
            )
            if is_login:
                result.login_page = name
        ctx.close()
        browser.close()

    extract_common(result)
    progress(1.0, f"Found {len(result.pages)} pages")
    return result


def extract_common(result: CrawlResult, share: float = 0.6) -> None:
    """Move elements that appear on most pages (header, menu, cart link ...) into CommonPage,
    which every page class extends, instead of repeating them in each page."""
    pages = [p for p in result.pages if not p.is_login]
    if len(pages) < 2:
        return
    key = lambda e: (e.strategy, e.value, e.role)
    counts = Counter(key(e) for p in pages for e in {key(x): x for x in p.elements}.values())
    threshold = max(2, -(-len(pages) * share // 1))
    common_keys = {k for k, n in counts.items() if n >= threshold}
    if not common_keys:
        return
    common: list[Element] = []
    seen: set = set()
    for p in pages:
        for e in p.elements:
            if key(e) in common_keys and key(e) not in seen:
                seen.add(key(e))
                common.append(e)
    names = {e.name for e in common}
    for p in pages:
        kept = [e for e in p.elements if key(e) not in common_keys]
        taken = set(names)
        for e in kept:
            if e.name in names:
                e.name = unique(e.name + "OnPage", taken)
            taken.add(e.name)
        p.elements = kept
    result.common = PageModel(name="CommonPage", url="", title="Shared elements", elements=common)


# Same selector as _COLLECT_JS, used to click the n-th collected element.
_COLLECT_SELECTOR_BY_INDEX = (
    "a, button, input:not([type=hidden]), select, textarea, [role=button], [role=link],"
    "[role=checkbox], [role=radio], [role=tab], [role=menuitem], [role=switch],"
    "h1, h2, h3, [role=alert], [role=status], [data-testid], [data-test], [data-qa], [data-cy]"
)
