"""Central settings shared by the app and the tests."""

import os

MODELS = {
    "openai/gpt-oss-120b": "GPT-OSS 120B (best quality)",
    "openai/gpt-oss-20b": "GPT-OSS 20B (faster, higher free-tier limits)",
}
DEFAULT_MODEL = "openai/gpt-oss-120b"

# ---- Crawler
MAX_PAGES = 25                 # unique pages to visit
MAX_CLICKS_PER_PAGE = 12       # link-like elements clicked to discover JS navigation
MAX_ELEMENTS_PER_PAGE = 150
NAV_TIMEOUT_MS = 15_000
SETTLE_MS = 800                # wait after a click for client-side navigation

# Never click or follow anything whose text/URL matches these (keeps the crawl read-only).
UNSAFE_WORDS = [
    "logout", "log out", "sign out", "signout", "log-out", "delete", "remove", "reset",
    "cancel order", "unsubscribe", "deactivate", "close account", "pay", "purchase",
    "place order", "finish", "confirm", "submit order", "buy now", "checkout complete",
]
# Buttons are only clicked during exploration when their text looks navigational.
# (Not "open"/"menu": those toggle overlays rather than navigate.)
NAV_BUTTON_WORDS = [
    "view", "details", "go to", "next", "continue shopping", "back", "checkout",
    "profile", "settings", "orders", "dashboard", "home",
]
# Clicking these changes the app's data, so exploration never clicks them (they are still recorded).
STATE_CHANGING_WORDS = ["add to", "add-to", "remove", "save", "update", "submit", "apply", "edit"]

# ---- Where the crawler may go
# On the public demo only these practice sites (with their published test logins) are allowed.
# Set ALLOW_ANY_SITE=true in your local .env to crawl any site from your own machine.
DEMO_SITES = {
    "Swag Labs (saucedemo.com)": {
        "url": "https://www.saucedemo.com/",
        "username": "standard_user",
        "password": "secret_sauce",
    },
    "The Internet (the-internet.herokuapp.com)": {
        "url": "https://the-internet.herokuapp.com/login",
        "username": "tomsmith",
        "password": "SuperSecretPassword!",
    },
}


def allow_any_site() -> bool:
    return os.getenv("ALLOW_ANY_SITE", "").strip().lower() in {"1", "true", "yes"}


# ---- Generation
PLAN_BATCH_SIZE = 2            # test cases per LLM call
PAGES_IN_PROMPT = 4            # most relevant pages shown to the model per test case
ELEMENTS_IN_PROMPT = 60        # per page
MIN_STEP_COVERAGE = 0.6       # below this share of mapped steps, warn that the tests may not fit the app
PLAYWRIGHT_VERSION = "^1.56.0"
