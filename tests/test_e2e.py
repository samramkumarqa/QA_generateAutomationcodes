"""Generate a project from the practice shop, npm-install it and run it with Playwright.

Slow (npm install + browser); skipped when node/npm aren't available.
Set PW_TEST_VERSION to pin @playwright/test to the browser build installed on this machine.
"""

import io
import json
import os
import shutil
import subprocess

import pytest
from openpyxl import load_workbook

from fakes import FakePlannerLLM
from pwgen.planner import plan_tests
from pwgen.renderer import build_project

pytestmark = pytest.mark.skipif(not shutil.which("npm"), reason="npm not installed")


def _run(cmd, cwd, env=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, shell=True)


def test_generated_project_runs_green(tmp_path, test_cases, saved_crawl, site_url):
    files = build_project(saved_crawl, test_cases, plan_tests(test_cases, saved_crawl, FakePlannerLLM()), "gen")
    for path, data in files.items():
        out = tmp_path / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    proj = tmp_path / "gen"

    # Turn TC-002 off in the input sheet to prove RunControl is honoured.
    xlsx = proj / "test-data" / "TestData.xlsx"
    wb = load_workbook(xlsx)
    for row in wb["RunControl"].iter_rows(min_row=2):
        if row[0].value == "TC-002":
            row[3].value = "N"
    wb.save(xlsx)

    pin = os.getenv("PW_TEST_VERSION")
    if pin:  # match the browser build installed on this machine
        pkg = json.loads((proj / "package.json").read_text())
        pkg["devDependencies"]["@playwright/test"] = pin
        (proj / "package.json").write_text(json.dumps(pkg, indent=2))

    # One command, as a user would run it: the pretest step installs the packages first.
    env = {**os.environ, "BASE_URL": f"{site_url}/", "APP_USERNAME": "standard_user", "APP_PASSWORD": "secret_sauce"}
    r = _run("npm test -- --reporter=line", proj, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    assert "First run: installing npm packages" in out
    # TC-002: Run = N. TC-005 and TC-006: their automated steps run (and would fail the test if
    # they broke), but each has a TODO step, so they end as fixme (skipped) instead of passing.
    # TC-005 opens a product: the site changes the URL before it redraws, like saucedemo, so
    # waitForPage() must wait for the details page itself, not just the URL.
    assert "3 passed" in out and "3 skipped" in out and "failed" not in out, out[-4000:]

    # Second run: nothing to install.
    r = _run("npm test -- --reporter=line", proj, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0 and "First run" not in out, out[-2000:]
