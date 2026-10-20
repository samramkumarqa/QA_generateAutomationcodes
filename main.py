"""Streamlit UI: approved test cases + a crawl of the app -> Playwright JS Page Object Model project.

Flow: 1) load test cases  2) log in and crawl the app  3) generate and download the project.
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from pwgen import config
from pwgen.crawler import CrawlError, crawl, ensure_browser
from pwgen.llm import GroqLLM, is_bad_generation
from pwgen.planner import plan_tests
from pwgen.renderer import build_project, zip_project
from pwgen.schemas import CrawlResult
from pwgen.testcases import TestCaseFileError, read_test_cases

ROOT = Path(__file__).parent
SAMPLE = ROOT / "samples" / "sample_testcases.xlsx"
load_dotenv()

st.set_page_config(page_title="AI Automation Code Generator", page_icon="🎭", layout="wide")


def configured_key() -> str:
    try:
        key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        key = ""
    return key or os.getenv("GROQ_API_KEY", "")


@st.cache_resource(show_spinner="Preparing the browser (first run only)…")
def browser_ready() -> bool:
    ensure_browser()
    return True


def progress_bar(label: str):
    bar = st.progress(0.0, text=label)
    return lambda f, m: bar.progress(min(max(f, 0.0), 1.0), text=m)


def fail(e: Exception) -> None:
    msg = str(e)
    if "401" in msg or "invalid_api_key" in msg.lower():
        st.error("Groq rejected the API key. Check it in the sidebar.")
    elif is_bad_generation(e):
        st.error("The model returned an incomplete answer three times. Try again, or switch to the 20B model.")
    elif "429" in msg or "rate limit" in msg.lower():
        st.error("Groq's rate limit was reached. Wait a minute, or switch to the 20B model.")
    else:
        st.error(f"Something went wrong: {msg[:500]}")
    st.stop()


# ---------------------------------------------------------------- sidebar

any_site = config.allow_any_site()
with st.sidebar:
    st.header("Settings")
    key = configured_key()
    if key:
        st.success("Groq API key configured", icon="🔑")
    else:
        key = st.text_input("Groq API key", type="password", help="Free at console.groq.com. Not stored.")
    model = st.selectbox("Model", list(config.MODELS), format_func=lambda m: config.MODELS[m])
    st.divider()
    if any_site:
        st.info("Local mode: you can crawl any site.", icon="🖥️")
    else:
        st.info(
            "Demo mode: crawling is limited to public practice sites. Run the app locally "
            "with ALLOW_ANY_SITE=true to crawl your own application.",
            icon="🔒",
        )
    st.caption("Built with Groq · Playwright · Streamlit")

st.title("🎭 AI Automation Code Generator")
st.markdown(
    "Turn approved manual test cases into a ready-to-run **Playwright (JavaScript) Page Object "
    "Model** project. The app logs in to your application, visits every unique page, records its "
    "elements with reliable locators, then maps each test step onto them."
)

# ---------------------------------------------------------------- 1 · test cases

st.subheader("1 · Load approved test cases")
c1, c2 = st.columns([3, 2])
with c1:
    upload = st.file_uploader(
        "Excel test pack from the AI Test Case Generator", type=["xlsx"],
        help="Uses the 'Test Cases' sheet: Test Case ID, Requirement ID, Title, Steps, Test Data, Expected Result.",
    )
with c2:
    st.write("No file handy?")
    use_sample = st.button("Use sample test pack (Swag Labs)")
    st.download_button("Download sample Excel", SAMPLE.read_bytes(), SAMPLE.name)

try:
    if upload is not None and st.session_state.get("tc_source") != upload.name:
        st.session_state.test_cases = read_test_cases(upload.getvalue())
        st.session_state.tc_source = upload.name
        st.session_state.pop("project", None)
    elif use_sample:
        st.session_state.test_cases = read_test_cases(SAMPLE.read_bytes())
        st.session_state.tc_source = SAMPLE.name
        st.session_state.pop("project", None)
except TestCaseFileError as e:
    st.error(str(e))

test_cases = st.session_state.get("test_cases")
if not test_cases:
    st.stop()

st.success(f"{len(test_cases)} test cases loaded from **{st.session_state.tc_source}**", icon="📋")
with st.expander("Preview test cases"):
    st.dataframe(
        pd.DataFrame([{"ID": t.id, "Requirement": t.requirement_id, "Title": t.title, "Steps": len(t.steps)}
                      for t in test_cases]),
        hide_index=True, width="stretch",
    )

# ---------------------------------------------------------------- 2 · crawl

st.subheader("2 · Crawl your application")
st.caption(
    "A browser logs in, follows links and link-like buttons, and records every page's elements. "
    "It never clicks Logout, Delete, Pay and similar, and never submits forms other than the login."
)

selectors = {}
target = st.radio("What to crawl", ["My application", "A practice site"], horizontal=True) if any_site else "A practice site"
if target == "My application":
    c1, c2, c3 = st.columns(3)
    url = c1.text_input("Login page URL", placeholder="https://your-app.example.com/login")
    username = c2.text_input("Username")
    password = c3.text_input("Password", type="password")
    with st.expander("Advanced"):
        max_pages = st.slider("Maximum pages to visit", 3, 60, config.MAX_PAGES)
        st.caption("Only needed if the login form isn't detected automatically (CSS selectors).")
        a1, a2, a3 = st.columns(3)
        selectors = {
            "username": a1.text_input("Username field selector"),
            "password": a2.text_input("Password field selector"),
            "submit": a3.text_input("Login button selector"),
        }
else:
    site = st.selectbox("Practice site", list(config.DEMO_SITES))
    demo = config.DEMO_SITES[site]
    url, username, password = demo["url"], demo["username"], demo["password"]
    st.caption(f"{url} · public test login **{username}** / **{password}**")
    max_pages = config.MAX_PAGES

c1, c2 = st.columns([1, 3])
crawl_clicked = c1.button("🕷️ Crawl", type="primary", disabled=not url)
prior = c2.file_uploader("…or reuse a saved crawl (JSON)", type=["json"], label_visibility="collapsed")

if crawl_clicked:
    if not url.startswith(("http://", "https://")):
        st.error("Enter a full http(s):// URL.")
        st.stop()
    try:
        browser_ready()
        st.session_state.crawl = crawl(
            url, username, password, max_pages=max_pages, selectors={k: v for k, v in selectors.items() if v},
            progress=progress_bar("Starting browser…"),
        )
        st.session_state.pop("project", None)
    except CrawlError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:
        st.error(f"The crawl failed: {str(e)[:400]}")
        st.stop()
elif prior is not None and st.session_state.get("crawl_source") != prior.name:
    try:
        st.session_state.crawl = CrawlResult.model_validate_json(prior.getvalue())
        st.session_state.crawl_source = prior.name
        st.session_state.pop("project", None)
    except Exception as e:
        st.error(f"That isn't a crawl file from this app: {e}")

result: CrawlResult | None = st.session_state.get("crawl")
if not result:
    st.stop()

n_el = sum(len(p.elements) for p in result.pages) + (len(result.common.elements) if result.common else 0)
st.success(f"Found **{len(result.pages)} pages** and **{n_el} elements** on {result.base_url}", icon="🕸️")
rows = ([{"Page object": result.common.name, "URL": "(shared on every page)", "Elements": len(result.common.elements)}]
        if result.common else [])
rows += [{"Page object": p.name, "URL": p.url, "Elements": len(p.elements)} for p in result.pages]
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
with st.expander("Elements by page"):
    for p in ([result.common] if result.common else []) + result.pages:
        st.markdown(f"**{p.name}** `{p.url or 'shared'}`")
        st.dataframe(
            pd.DataFrame([{"Name": e.name, "Kind": e.kind, "Locator": e.strategy, "Value": e.value,
                           "Visible": e.visible} for e in p.elements]),
            hide_index=True, width="stretch",
        )
if result.log:
    with st.expander("Crawl log (what was clicked and where it led)"):
        st.code("\n".join(result.log), language="text")
st.download_button("Save crawl (JSON)", result.model_dump_json(indent=1), "crawl.json", "application/json")

# ---------------------------------------------------------------- 3 · generate

st.subheader("3 · Generate the Playwright project")
if not key:
    st.warning("Add a Groq API key in the sidebar to continue.")
    st.stop()

batches = -(-len(test_cases) // config.PLAN_BATCH_SIZE)
if st.button(f"⚙️ Generate code for {len(test_cases)} test cases", type="primary"):
    try:
        plans = plan_tests(test_cases, result, GroqLLM(api_key=key, model=model),
                           progress=progress_bar(f"Mapping test steps to page elements ({batches} calls)…"))
    except Exception as e:
        fail(e)
    st.session_state.project = build_project(result, test_cases, plans)
    st.session_state.plans = plans

files: dict[str, bytes] | None = st.session_state.get("project")
if not files:
    st.stop()

plans = st.session_state.plans
mapped = sum(len(p.steps) for p in plans)
todo = sum(len(p.unmapped) for p in plans)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Test cases", len(plans))
m2.metric("Automated steps", mapped)
m3.metric("Steps left as TODO", todo)
m4.metric("Files", len(files))
complete = sum(1 for p in plans if p.steps and not p.unmapped)
coverage = mapped / (mapped + todo) if mapped + todo else 0.0
if coverage < config.MIN_STEP_COVERAGE:
    st.warning(
        f"Only **{coverage:.0%}** of the test steps match elements found on {result.base_url}. "
        "Are these test cases written for this application? Generated code for steps that don't "
        "match won't work: crawl the application the test cases describe, or load matching test cases.",
        icon="⚠️",
    )
st.caption(
    f"{complete} of {len(plans)} tests are fully automated. Tests with TODO steps still run their "
    "automated steps, then end as **fixme** (skipped) in the report instead of passing."
)
if todo:
    with st.expander(f"⚠️ {todo} step(s) need attention (left as // TODO in the specs)"):
        for p in plans:
            for u in p.unmapped:
                st.markdown(f"- **{p.test_case_id}**: {u}")

paths = sorted(files)
root = paths[0].split("/")[0]
choice = st.selectbox("Browse the generated files", paths, format_func=lambda x: x.split("/", 1)[1],
                      index=next((i for i, p in enumerate(paths) if p.endswith(".spec.js")), 0))
lang = {"js": "javascript", "json": "json", "md": "markdown"}.get(choice.rsplit(".", 1)[-1], "text")
if choice.endswith(".xlsx"):
    st.info("Excel input sheet: RunControl (Run Y/N per test) and TestData (key/value per test).")
else:
    st.code(files[choice].decode(), language=lang)

st.download_button(
    "⬇️ Download Playwright project (.zip)", zip_project(files), f"{root}.zip", "application/zip", type="primary"
)
st.caption("Unzip, then: npm install · npx playwright install chromium · cp .env.example .env · npm test")
