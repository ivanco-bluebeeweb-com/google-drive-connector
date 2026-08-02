import pytest

import accounts
import drive_client as dc
import handlers
from models import PinFileParams, SetContextParams


@pytest.mark.asyncio
async def test_multiple_accounts_require_explicit_choice(ctx, account):
    await ctx.store.create(accounts.ACCOUNTS, {
        "email": "other@example.com", "access_token": "x", "is_active": False,
    })
    account.data["is_active"] = False
    await ctx.store.update(accounts.ACCOUNTS, account.id, {"is_active": False})
    out = await accounts.resolve_account(ctx)
    assert out["code"] == dc.ACCOUNT_AMBIGUOUS


@pytest.mark.asyncio
async def test_context_permission_defaults_off_and_is_account_scoped(ctx, account):
    before = await accounts.setting(ctx, "vlad@example.com")
    assert before["context_enabled"] is False
    result = await handlers.set_context_permission(ctx, SetContextParams(account="vlad@example.com", enabled=True))
    assert result.status == "success"
    after = await accounts.setting(ctx, "vlad@example.com")
    other = await accounts.setting(ctx, "other@example.com")
    assert after["context_enabled"] is True
    assert other["context_enabled"] is False


@pytest.mark.asyncio
async def test_pin_is_stored_locally_and_does_not_write_to_google(ctx, account):
    ctx.http.push({"id": "f1", "name": "Brief", "mimeType": "text/plain",
                   "webViewLink": "https://drive.google.com/file/d/f1/view"})
    result = await handlers.pin_file(ctx, PinFileParams(account="vlad@example.com", file_id="f1", pinned=True))
    assert result.status == "success"
    pins = await ctx.store.query(handlers.PINS, where={"email": "vlad@example.com"}, limit=10)
    assert len(pins.data) == 1
    assert all(call["method"] == "GET" for call in ctx.http.calls)


@pytest.mark.asyncio
async def test_unpin_does_not_call_google(ctx, account):
    await ctx.store.create(handlers.PINS, {"email": "vlad@example.com", "file_id": "f1", "title": "Brief"})
    result = await handlers.pin_file(ctx, PinFileParams(account="vlad@example.com", file_id="f1", pinned=False))
    assert result.status == "success"
    assert ctx.http.calls == []


def test_unknown_oauth_identity_has_reconnect_label():
    class Doc:
        data = {"email": "unknown"}

    assert accounts.identity_missing(Doc()) is True
    assert accounts.account_label(Doc()) == "Google account needs reconnecting"


@pytest.mark.asyncio
async def test_list_accounts_never_exposes_unknown_as_account_name(ctx):
    await ctx.store.create(accounts.ACCOUNTS, {
        "email": "unknown", "access_token": "access-token", "is_active": True,
    })

    result = await handlers.list_accounts(ctx, handlers.ListAccountsParams(refresh=False))
    item = result.data.items[0]

    assert item.title == "Google account needs reconnecting"
    assert item.email == ""
    assert item.state == "reconnect_required"


@pytest.mark.asyncio
async def test_verify_repairs_unknown_identity_from_drive_about(ctx):
    doc = await ctx.store.create(accounts.ACCOUNTS, {
        "email": "unknown", "access_token": "access-token", "is_active": True,
    })
    ctx.http.push({
        "user": {"emailAddress": "vlad@example.com", "displayName": "Vlad"},
        "storageQuota": {"usage": "1"},
    })

    out = await accounts.verify(ctx, doc)

    assert out["ok"] is True
    assert out["email"] == "vlad@example.com"
    saved = await ctx.store.get(accounts.ACCOUNTS, doc.id)
    assert saved.data["email"] == "vlad@example.com"
    assert saved.data["display_name"] == "Vlad"
