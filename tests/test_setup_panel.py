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


@pytest.mark.asyncio
async def test_broken_account_is_sent_to_reconnect_instead_of_drive(ctx):
    async def oauth_authorize_url(provider, **kwargs):
        assert provider == "google"
        return "https://accounts.google.com/o/oauth2/v2/auth?scope=drive.readonly"

    ctx.oauth_authorize_url = oauth_authorize_url
    await ctx.store.create("google_drive_accounts", {
        "email": "unknown", "access_token": "access-token", "is_active": True,
    })

    page = (await panels.drive(ctx, view="folder", folder_id="root")).to_dict()

    assert page["props"]["title"] == "Reconnect Google Drive"
    nodes = list(_walk(page))
    labels = {n.get("props", {}).get("label") for n in nodes}
    open_urls = {
        n.get("props", {}).get("on_click", {}).get("url")
        for n in nodes
        if n.get("props", {}).get("on_click", {}).get("action") == "open"
    }
    assert "Continue with Google" in labels
    assert "Disconnect account" in labels
    assert any(url and "accounts.google.com/o/oauth2/v2/auth" in url for url in open_urls)
    assert len(ctx.http.calls) == 1
