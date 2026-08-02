import ast
from pathlib import Path

from imperal_sdk import ui

ROOT = Path(__file__).resolve().parents[1]


def test_every_ui_primitive_exists_in_installed_sdk():
    tree = ast.parse((ROOT / "panels.py").read_text())
    names = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "ui"}
    missing = sorted(n for n in names if not hasattr(ui, n))
    assert missing == []


def test_oauth_requests_identity_and_read_only_drive_scopes():
    source = (ROOT / "app.py").read_text()
    assert '"openid"' in source
    assert '"email"' in source
    assert '"profile"' in source
    assert "drive.readonly" in source
    assert "spreadsheets.readonly" in source


def test_mvp_has_no_google_mutation_requests():
    source = "\n".join(p.read_text() for p in ROOT.glob("*.py"))
    forbidden = ["ctx.http.put(", "ctx.http.patch(", "ctx.http.delete(", "/permissions"]
    assert [x for x in forbidden if x in source] == []


def test_context_permission_defaults_to_false():
    source = (ROOT / "accounts.py").read_text()
    assert '"context_enabled": False' in source


def test_search_form_dispatches_to_server_panel():
    source = (ROOT / "panels.py").read_text()
    assert 'ui.Form(action="__panel__drive", submit_label="Search"' in source
    assert 'defaults={"view": "search", "account": account}' in source
    assert "searchable=True" not in source


def test_component_sketch_exists_before_panel_implementation():
    sketch = ROOT / "design" / "component-sketches.md"
    assert sketch.exists()
    text = sketch.read_text()
    normalized = text.lower()
    for screen in ["Connect Google Drive", "Drive Home", "Search Results", "Folder Browser",
                   "Shared Drives", "File Details", "Accounts and Access"]:
        assert screen.lower() in normalized
