"""The Selenium (Java + TestNG + Maven) project: layout, content, and that every Java file compiles.

Compilation runs against small API stubs in tests/java_stubs (no Maven download needed), which
catches syntax and type errors in the generated code. Running it for real needs Maven: mvn test.
"""

import io
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
from openpyxl import load_workbook

from conftest import ROOT
from fakes import FakePlannerLLM
from pwgen.planner import plan_tests
from pwgen.selenium import build_selenium_project, constant, jcomment
from pwgen.renderer import build_project

J = "demo/src/test/java/com/automation"
R = "demo/src/test/resources"


@pytest.fixture
def plans(test_cases, saved_crawl):
    return plan_tests(test_cases, saved_crawl, FakePlannerLLM())


@pytest.fixture
def project(test_cases, saved_crawl, plans):
    return build_selenium_project(saved_crawl, test_cases, plans, project_name="demo")


def test_layout(project):
    names = {p.split("/", 1)[1] for p in project}
    expected = {
        "pom.xml", "testng.xml", ".env.example", ".gitignore", "README.md",
        "src/test/resources/config.properties", "src/test/resources/test-data/TestData.xlsx",
        "src/test/resources/object-repository/CommonPage.json", "src/test/resources/object-repository/LoginPage.json",
        "src/test/java/com/automation/base/BaseTest.java", "src/test/java/com/automation/base/DriverFactory.java",
        "src/test/java/com/automation/pages/BasePage.java", "src/test/java/com/automation/pages/CommonPage.java",
        "src/test/java/com/automation/pages/LoginPage.java", "src/test/java/com/automation/pages/InventoryPage.java",
        "src/test/java/com/automation/utils/Config.java", "src/test/java/com/automation/utils/TestData.java",
        "src/test/java/com/automation/tests/FR01Test.java", "src/test/java/com/automation/tests/FR05Test.java",
    }
    assert expected <= names


def test_pom_and_suite_are_valid_xml(project):
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    pom = ET.fromstring(project["demo/pom.xml"])
    deps = {d.find("m:artifactId", ns).text for d in pom.find("m:dependencies", ns)}
    assert deps == {"selenium-java", "testng", "jackson-databind", "poi-ooxml",
                    "log4j-to-slf4j", "slf4j-api", "slf4j-nop"}  # the last three keep the console quiet
    version = pom.find("m:properties/m:selenium.version", ns).text
    assert tuple(map(int, version.split("."))) >= (4, 52, 0)  # supports Chrome DevTools up to v156
    suite = ET.fromstring(project["demo/testng.xml"].split(b"\n", 2)[2])  # skip the DOCTYPE line
    assert [c.get("name") for c in suite.iter("class")] == [f"com.automation.tests.FR0{i}Test" for i in range(1, 6)]


def test_same_object_repository_and_input_sheet_as_playwright(project, test_cases, saved_crawl, plans):
    pw = build_project(saved_crawl, test_cases, plans, project_name="demo")
    for page in ("LoginPage", "CommonPage", "InventoryPage"):
        assert project[f"{R}/object-repository/{page}.json"] == pw[f"demo/object-repository/{page}.json"]
    wb = load_workbook(io.BytesIO(project[f"{R}/test-data/TestData.xlsx"]))
    assert ("TC-004", "postalCode", "637211") in list(wb["TestData"].iter_rows(min_row=2, values_only=True))
    assert json.loads(project[f"{R}/object-repository/LoginPage.json"])["url"] == "/index.html"
    props = project[f"{R}/config.properties"].decode()
    assert f"testIdAttribute={saved_crawl.test_id_attribute}" in props
    assert "secret_sauce" not in project["demo/.env.example"].decode()


def test_tests_use_page_objects_waits_and_mark_todos(project):
    fr3 = project[f"{J}/tests/FR03Test.java"].decode()
    assert "public class FR03Test extends BaseTest" in fr3
    assert '@Test(description = "TC-004: Verify checkout requires the first name")' in fr3
    assert "loginPage.login();" in fr3
    assert 'checkoutStepOnePage.type(CheckoutStepOnePage.LAST_NAME_INPUT, data.get("lastName"));' in fr3
    assert ('Assert.assertTrue(checkoutStepOnePage.containsText(CheckoutStepOnePage.ERROR_TEXT, data.get("expectedError")), '
            '"errorText should contain " + data.get("expectedError"));') in fr3
    assert "SkipException(\"1 step" not in fr3  # complete test
    detail = project[f"{J}/tests/FR04Test.java"].decode()
    assert ("inventoryPage.click(InventoryPage.TRAIL_BACKPACK_LINK);\n"
            "        // Product name is shown\n"
            "        itemPage.waitForPage();\n") in detail
    fr5 = project[f"{J}/tests/FR05Test.java"].decode()
    assert "// TODO (not automated)" in fr5
    assert fr5.rstrip().endswith('throw new SkipException("1 step(s) not automated yet: complete the TODOs above");\n    }\n}')
    login = project[f"{J}/pages/LoginPage.java"].decode()
    assert "public class LoginPage extends BasePage" in login
    assert 'public static final String USERNAME_INPUT = "usernameInput";' in login
    assert "copy .env.example to .env" in login and "didn't succeed" in login
    inv = project[f"{J}/pages/InventoryPage.java"].decode()
    assert "public class InventoryPage extends CommonPage" in inv and 'super(driver, "InventoryPage");' in inv


def test_helpers():
    assert constant("shoppingCartLink") == "SHOPPING_CART_LINK"
    assert constant("item4TitleLink") == "ITEM4_TITLE_LINK"
    assert jcomment("C:\\users\\me") == "C:\\ users\\me"  # javac reads \u even inside comments


@pytest.mark.skipif(not shutil.which("javac"), reason="javac not installed")
def test_every_java_file_compiles(project, tmp_path):
    src = []
    for path, data in project.items():
        if path.endswith(".java"):
            f = tmp_path / "src" / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
            src.append(str(f))
    stubs = [str(p) for p in (ROOT / "tests" / "java_stubs").rglob("*.java")]
    r = subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(tmp_path / "out"), *stubs, *src],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-3000:]
    assert (tmp_path / "out" / "com" / "automation" / "tests" / "FR03Test.class").exists()


# ---------------------------------------------------------------- the generated locator XPaths, in a real browser

HARNESS = """
import java.lang.reflect.Method;
public class LocatorHarness {
    static String call(String name, Class<?>[] types, Object... args) throws Exception {
        Method m = com.automation.pages.BasePage.class.getDeclaredMethod(name, types);
        m.setAccessible(true);
        return (String) m.invoke(null, args);
    }
    public static void main(String[] a) throws Exception {
        Class<?>[] one = {String.class}, two = {String.class, String.class};
        for (int i = 0; i < a.length; i += 3) {
            String kind = a[i], role = a[i + 1], value = a[i + 2];
            String x = kind.equals("role") ? call("roleXpath", two, role, value) : call(kind + "Xpath", one, value);
            System.out.println(x);
        }
    }
}
"""

# (strategy, role, value) -> id of the one element it must find
LOCATOR_CASES = [
    ("text", "", "Your orders", "h-orders"),
    ("text", "", "$29.99", "t-price"),
    ("text", "", "Free delivery", "t-nested"),
    ("role", "button", "Save", "b-save"),
    ("role", "button", "Log in", "b-submit"),
    ("role", "button", "Open menu", "b-role"),
    ("role", "button", "Close dialog", "b-aria"),
    ("role", "link", "Shopping cart", "l-cart"),
    ("role", "link", 'Bob\'s "best" deals', "l-quote"),
    ("role", "heading", "Your orders", "h-orders"),
    ("role", "textbox", "Email address", "f-email"),
    ("role", "textbox", "Order notes", "f-notes"),
    ("role", "textbox", "Search products", "f-search"),
    ("role", "checkbox", "I agree", "c-terms"),
    ("role", "combobox", "Sort by", "s-sort"),
    ("role", "img", "Company logo", "i-logo"),
    ("label", "", "Email address", "f-email"),
    ("label", "", "Phone", "f-phone"),
    ("label", "", "Order notes", "f-notes"),
    ("label", "", "Sort by", "s-sort"),
]


@pytest.mark.skipif(not shutil.which("javac"), reason="javac not installed")
def test_generated_xpaths_find_the_right_element(project, tmp_path):
    from playwright.sync_api import sync_playwright

    base = project[f"{J}/pages/BasePage.java"]
    (tmp_path / "BasePage.java").write_bytes(base)
    (tmp_path / "LocatorHarness.java").write_text(HARNESS)
    (tmp_path / "Config.java").write_bytes(project[f"{J}/utils/Config.java"])
    stubs = [str(p) for p in (ROOT / "tests" / "java_stubs").rglob("*.java")]
    out = tmp_path / "out"
    r = subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(out), *stubs, str(tmp_path / "Config.java"),
                        str(tmp_path / "BasePage.java"), str(tmp_path / "LocatorHarness.java")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    args = [x for kind, role, value, _ in LOCATOR_CASES for x in (kind, role or "-", value)]
    r = subprocess.run(["java", "-cp", str(out), "LocatorHarness", *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    xpaths = r.stdout.splitlines()
    assert len(xpaths) == len(LOCATOR_CASES)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto((ROOT / "tests" / "site" / "locators.html").as_uri())
        for (kind, role, value, expected), xp in zip(LOCATOR_CASES, xpaths):
            ids = page.evaluate(
                """x => { const r = document.evaluate(x, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                          return Array.from({length: r.snapshotLength}, (_, i) => r.snapshotItem(i).id); }""", xp)
            assert ids == [expected], f"{kind} {role} {value!r}: {xp} -> {ids}"
        browser.close()
