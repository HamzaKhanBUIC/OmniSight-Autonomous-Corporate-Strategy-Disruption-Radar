"""The dashboard must escape scan data before it reaches innerHTML."""
import json
import os
import re
import shutil
import subprocess

import pytest

INDEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "index.html")

# Interpolations that only ever hold fixed markup or class names built in the page itself
TRUSTED = {"bgClass", "usIcon", "themIcon", "icon1", "icon2"}


def page():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def html_templates(source):
    """Template literals that are written into HTML (innerHTML or the vault's html buffer)."""
    return re.findall(r"(?:innerHTML|\bhtml)\s*\+?=\s*`(.*?)`", source, re.DOTALL)


def test_every_interpolation_in_html_templates_is_escaped():
    templates = html_templates(page())
    assert len(templates) >= 7
    for template in templates:
        for expr in re.findall(r"\$\{([^}]*)\}", template):
            expr = expr.strip()
            ok = expr.startswith("escapeHtml(") or expr in TRUSTED or expr.startswith("isEven ?")
            assert ok, f"unescaped interpolation in innerHTML template: ${{{expr}}}"


def test_markdown_analysis_is_escaped_before_formatting():
    assert "escapeHtml(data.detailed_analysis)" in page()


def test_no_untrusted_values_inside_inline_handlers():
    assert not re.search(r"on\w+=\"[^\"]*\$\{", page())


def test_terminal_feed_uses_text_nodes():
    body = re.search(r"function addTerminalLine\(text\) \{(.*?)\n        \}", page(), re.DOTALL).group(1)
    assert "createTextNode" in body and "innerHTML" not in body


def extract_function(source, name):
    start = source.index(f"function {name}(")
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[start:i + 1]
    raise AssertionError(f"{name} not closed")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_escape_html_function():
    script = extract_function(page(), "escapeHtml") + """
    const cases = JSON.parse(process.argv[1]);
    process.stdout.write(JSON.stringify(cases.map(escapeHtml)));
    """
    cases = ['<img src=x onerror=alert(1)>', '"><script>x</script>', "' onmouseover='a", "R&D", None, 42]
    out = subprocess.run(["node", "-e", script, json.dumps(cases)],
                         capture_output=True, text=True, check=True, timeout=30).stdout
    assert json.loads(out) == [
        "&lt;img src=x onerror=alert(1)&gt;",
        "&quot;&gt;&lt;script&gt;x&lt;/script&gt;",
        "&#39; onmouseover=&#39;a",
        "R&amp;D",
        "",
        "42",
    ]
