"""Offline stand-ins for Groq: a planner that returns hand-written plans for the practice shop."""

from pwgen.schemas import DataItem, PlanBatch, PlannedStep, TestPlan


def S(action, page="", element="", data_key="", value="", comment=""):
    return PlannedStep(action=action, page=page, element=element, data_key=data_key, value=value, comment=comment)


# What a good model should produce for samples/sample_testcases.xlsx against tests/site.
PRACTICE_SHOP_PLANS = {
    "TC-001": TestPlan(
        test_case_id="TC-001", title="", unmapped=[],
        data=[DataItem(key="username", value="standard_user"), DataItem(key="password", value="secret_sauce")],
        steps=[
            S("goto", "LoginPage", comment="Open the login page"),
            S("fill", "LoginPage", "usernameInput", "username", comment="Enter username"),
            S("fill", "LoginPage", "passwordInput", "password", comment="Enter password"),
            S("click", "LoginPage", "loginButton", comment="Click the Login button"),
            S("expectUrlContains", value="inventory", comment="Products page is displayed"),
            S("expectVisible", "InventoryPage", "addToCartBackpackButton", comment="Products are listed"),
        ],
    ),
    "TC-002": TestPlan(
        test_case_id="TC-002", title="", unmapped=[],
        data=[DataItem(key="username", value="locked_out_user"), DataItem(key="password", value="secret_sauce"),
              DataItem(key="expectedError", value="Epic sadface: Sorry, this user has been locked out.")],
        steps=[
            S("goto", "LoginPage", comment="Open the login page"),
            S("fill", "LoginPage", "usernameInput", "username", comment="Enter locked out username"),
            S("fill", "LoginPage", "passwordInput", "password", comment="Enter password"),
            S("click", "LoginPage", "loginButton", comment="Click Login"),
            S("expectText", "LoginPage", "errorText", "expectedError", comment="Locked out error shown"),
        ],
    ),
    "TC-003": TestPlan(
        test_case_id="TC-003", title="", unmapped=[], data=[DataItem(key="badgeCount", value="1")],
        steps=[
            S("login", comment="User is logged in"),
            S("click", "InventoryPage", "addToCartBackpackButton", comment="Add the backpack to the cart"),
            S("expectText", "CommonPage", "shoppingCartBadgeText", "badgeCount", comment="Cart badge shows 1"),
        ],
    ),
    "TC-004": TestPlan(
        test_case_id="TC-004", title="", unmapped=[],
        data=[DataItem(key="lastName", value="Kumar"), DataItem(key="postalCode", value="637211"),
              DataItem(key="expectedError", value="Error: First Name is required")],
        steps=[
            S("login", comment="User is logged in"),
            S("click", "InventoryPage", "addToCartBackpackButton", comment="Add the backpack"),
            S("click", "CommonPage", "shoppingCartLink", comment="Open the cart"),
            S("click", "CartPage", "checkoutButton", comment="Click Checkout"),
            S("fill", "CheckoutStepOnePage", "lastNameInput", "lastName", comment="Enter last name"),
            S("fill", "CheckoutStepOnePage", "postalCodeInput", "postalCode", comment="Enter postal code"),
            S("click", "CheckoutStepOnePage", "continueButton", comment="Click Continue"),
            S("expectText", "CheckoutStepOnePage", "errorText", "expectedError", comment="First name error shown"),
        ],
    ),
    "TC-005": TestPlan(
        test_case_id="TC-005", title="", unmapped=["Check the product details (no specific value given)"],
        data=[],
        steps=[
            S("login", comment="User is logged in"),
            S("click", "InventoryPage", "trailBackpackLink", comment="Click the backpack product name"),
            S("expectVisible", "ItemPage", "inventoryItemNameText", comment="Product name is shown"),
            S("click", "ItemPage", "backToProductsButton", comment="Click Back to products"),
            S("expectUrlContains", value="inventory", comment="Back on the Products page"),
        ],
    ),
    "TC-006": TestPlan(
        test_case_id="TC-006", title="", unmapped=[], data=[],
        steps=[
            S("login", comment="User is logged in"),
            S("click", "CommonPage", "openMenuButton", comment="Open the menu"),
            S("click", "CommonPage", "logoutLink", comment="Click Logout"),
            S("expectVisible", "LoginPage", "loginButton", comment="Login page is shown"),
            # Deliberately wrong element: validation must drop it and record it as unmapped.
            S("click", "CommonPage", "noSuchElement", comment="Bogus step"),
        ],
    ),
}


class FakePlannerLLM:
    model = "fake"

    def __init__(self, plans=PRACTICE_SHOP_PLANS):
        self.plans = plans
        self.calls = []

    def generate(self, system, user, schema):
        import re

        self.calls.append((system, user, schema.__name__))
        ids = re.findall(r"^\[(TC-\d+)\]", user, flags=re.MULTILINE)
        return PlanBatch(plans=[self.plans[i].model_copy(deep=True) for i in ids if i in self.plans])
