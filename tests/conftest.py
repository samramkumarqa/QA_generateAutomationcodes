import functools
import http.server
import socket
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

SAMPLE = ROOT / "samples" / "sample_testcases.xlsx"
SAVED_CRAWL = ROOT / "tests" / "data" / "practice_shop_crawl.json"


@pytest.fixture(scope="session")
def site_url():
    """Serve tests/site (the practice shop) on a free local port."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "tests" / "site"))
    handler.log_message = lambda *a, **k: None
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture
def test_cases():
    from pwgen.testcases import read_test_cases

    return read_test_cases(SAMPLE.read_bytes())


@pytest.fixture
def saved_crawl():
    from pwgen.schemas import CrawlResult

    return CrawlResult.model_validate_json(SAVED_CRAWL.read_text())
