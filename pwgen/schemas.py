"""Data passed between the crawler, the planner and the code generator."""

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- crawl results

Strategy = Literal["testId", "role", "label", "placeholder", "text", "css"]


class Element(BaseModel):
    name: str                      # camelCase identifier used in the page class
    kind: str                      # button, link, input, dropdown, checkbox, radio, textarea, text
    strategy: Strategy
    value: str                     # test id / accessible name / label / css selector ...
    role: str = ""                 # only for strategy == "role"
    description: str = ""          # human-readable, e.g. 'Button "Login"'
    visible: bool = True


class PageModel(BaseModel):
    name: str                      # class name, e.g. InventoryPage
    url: str                       # path relative to the site root, e.g. /inventory.html
    title: str = ""
    is_login: bool = False
    elements: list[Element] = []


class CrawlResult(BaseModel):
    base_url: str                  # scheme://host
    start_url: str
    test_id_attribute: str = "data-testid"
    login_page: str = ""           # name of the login page class, if one was found
    common: PageModel | None = None  # elements shared by most pages (header, menu ...)
    pages: list[PageModel] = []
    skipped: list[str] = []        # URLs/links deliberately not followed, for the report
    log: list[str] = []            # what the explorer clicked and where it landed, for debugging


# ---------------------------------------------------------------- test cases (input)

class TestCaseIn(BaseModel):
    __test__ = False  # not a pytest test class

    id: str
    requirement_id: str = ""
    title: str
    preconditions: str = ""
    steps: list[str]
    test_data: str = ""
    expected_result: str = ""


# ---------------------------------------------------------------- LLM plan (strict schema)

ActionName = Literal[
    "login",              # log in with the credentials from .env
    "goto",               # open a page by its URL
    "click", "fill", "select", "check", "uncheck", "hover",
    "expectVisible", "expectHidden", "expectText", "expectValue", "expectCount",
    "expectUrlContains",  # value = part of the URL
    "expectTextOnPage",   # value = text that should appear anywhere (for messages not captured by the crawl)
]


class PlannedStep(BaseModel):
    action: ActionName
    page: str = Field(description="Page class name from the catalog, or empty string.")
    element: str = Field(description="Element name from that page in the catalog, or empty string.")
    data_key: str = Field(
        description="For fill/select/expectText/expectValue: key into this test's data, else empty."
    )
    value: str = Field(
        description="Literal for expectUrlContains / expectTextOnPage / expectCount, else empty."
    )
    comment: str = Field(description="The original test step this implements, shortened.")


class DataItem(BaseModel):
    key: str = Field(description="camelCase key, e.g. username, productName.")
    value: str


class TestPlan(BaseModel):
    test_case_id: str
    title: str
    data: list[DataItem]
    steps: list[PlannedStep]
    unmapped: list[str] = Field(
        description="Test steps that could not be mapped to any page element. Empty if none."
    )


class PlanBatch(BaseModel):
    plans: list[TestPlan]
