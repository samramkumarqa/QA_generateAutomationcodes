"""Turn URLs and element text into stable, valid JavaScript identifiers."""

import re
from urllib.parse import urlparse

JS_RESERVED = {
    "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete", "do",
    "else", "export", "extends", "finally", "for", "function", "if", "import", "in", "instanceof",
    "new", "return", "super", "switch", "this", "throw", "try", "typeof", "var", "void", "while",
    "with", "yield", "let", "static", "enum", "await", "implements", "package", "protected",
    "interface", "private", "public", "null", "true", "false", "undefined",
}
# Members of BasePage / page classes that an element getter must not shadow.
RESERVED_MEMBERS = {"page", "repo", "el", "goto", "url", "login", "constructor", "name", "elements"}

_ID_SEGMENT = re.compile(r"^(\d+|[0-9a-f]{8,}|[0-9a-f-]{32,36})$", re.I)


def url_template(url: str) -> str:
    """Canonical page key: path only, with IDs collapsed, so /item/4 and /item/5 are one page."""
    path = urlparse(url).path or "/"
    parts = [":id" if _ID_SEGMENT.match(p) else p for p in path.split("/")]
    path = "/".join(parts)
    if len(path) > 1:
        path = path.rstrip("/")
    return path.lower()


def words(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)  # split camelCase
    return [w for w in re.split(r"[^A-Za-z0-9]+", text) if w]


def camel(text: str, max_words: int = 6) -> str:
    ws = [w.lower() for w in words(text)][:max_words]
    if not ws:
        return ""
    out = ws[0] + "".join(w.capitalize() for w in ws[1:])
    if out[0].isdigit():
        out = "n" + out
    return out


def pascal(text: str, max_words: int = 5) -> str:
    c = camel(text, max_words)
    return c[:1].upper() + c[1:] if c else ""


def page_class_name(path_template: str, title: str = "") -> str:
    segs = [s for s in path_template.split("/") if s and s != ":id"]
    if segs:
        last = re.sub(r"\.(html?|php|aspx?|jsp)$", "", segs[-1])
        base = pascal(last) or pascal(title)
        if path_template.endswith(":id"):
            base += "Detail"
    else:
        base = "Home"
    base = base or "Page"
    return base if base.endswith("Page") else base + "Page"


KIND_SUFFIX = {
    "button": "Button", "link": "Link", "input": "Input", "textarea": "Input",
    "dropdown": "Dropdown", "checkbox": "Checkbox", "radio": "Radio", "text": "Text",
}


def element_name(source_text: str, kind: str, taken: set[str]) -> str:
    base = camel(source_text) or kind
    suffix = KIND_SUFFIX.get(kind, "")
    if suffix and not base.lower().endswith(suffix.lower()):
        base += suffix
    base = base[:48]
    if base in JS_RESERVED or base in RESERVED_MEMBERS:
        base += "El"
    name, n = base, 2
    while name in taken:
        name, n = f"{base}{n}", n + 1
    taken.add(name)
    return name


def unique(name: str, taken: set[str]) -> str:
    out, n = name, 2
    while out in taken:
        out, n = f"{name}{n}", n + 1
    taken.add(out)
    return out
