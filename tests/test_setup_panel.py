import pytest

import panels
from imperal_sdk.testing import MockSecretStore


def _walk(node):
    yield node
    props = node.get("props", {}) if isinstance(node, dict) else {}
    for value in props.values():
        if isinstance(value, dict) and "type" in value:
            yield from _walk(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "type" in item:
                    yield from _walk(item)


@pytest.mark.asyncio
async def test_missing_oauth_secrets_show_complete_on_screen_setup(ctx):
    ctx.secrets = MockSecretStore()

    page = (await panels._connect(ctx)).to_dict()
    nodes = list(_walk(page))
    titles = {n.get("props", {}).get("title") for n in nodes}
    text = "\n".join(
        str(n.get("props", {}).get(key, ""))
        for n in nodes
        for key in ("content", "message", "label")
    )

    assert page["props"]["title"] == "Set up Google Drive"
    assert {
        "1. Enable the Google APIs",
        "2. Configure the OAuth consent screen",
        "3. Create an OAuth client",
        "4. Save credentials in Imperal",
    } <= titles
    assert panels.REDIRECT_URI in text
    assert "google_client_id" in text
    assert "google_client_secret" in text


@pytest.mark.asyncio
async def test_setup_screen_has_direct_official_and_imperal_links(ctx):
    ctx.secrets = MockSecretStore()

    nodes = list(_walk((await panels._connect(ctx)).to_dict()))
    urls = {
        n.get("props", {}).get("on_click", {}).get("url")
        for n in nodes
        if n.get("type") == "Button"
    }

    assert {
        panels.GOOGLE_DRIVE_API_URL,
        panels.GOOGLE_SHEETS_API_URL,
        panels.GOOGLE_OAUTH_URL,
        panels.GOOGLE_CREDENTIALS_URL,
        panels.IMPERAL_SECRETS_URL,
        panels.OAUTH_DOCS_URL,
    } <= urls
