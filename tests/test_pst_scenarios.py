"""Plausible Scenario Tests (PST) -- Google Drive Connector.

Method: Docs/session-notes/SCENARIO_TESTING_STANDARD.md. This app has 14
chat functions and 31 existing tests across 5 files, with real coverage of
account resolution, token refresh, and drive_files.py's HTTP-layer
functions directly. A name-based coverage audit (does any test call this
exact chat-function name?) found 8 functions never exercised at the
@chat.function (handlers.py) level, even though some of their underlying
drive_files.py helpers are tested indirectly:

    browse_folder, check_access, get_file, list_pinned_files,
    list_shared_drives, read_file, search_files, switch_account

This file targets exactly those 8, using the existing conftest.py
QueueHTTP/account fixtures.
"""
from __future__ import annotations

import pytest

import drive_files as df
import handlers as h
from models import (
    AccountParam, BrowseFolderParams, FileParam, ListPinnedParams,
    ListSharedDrivesParams, PinFileParams, ReadFileParams, SearchFilesParams,
)


# ── happy: every previously-untested handler, once each ────────────────────

@pytest.mark.asyncio
async def test_happy_search_files(ctx, account):
    ctx.http.push({"files": [{"id": "f1", "name": "KSR Brief", "mimeType": df.GDOC}]})
    out = await h.search_files(ctx, SearchFilesParams(query="KSR"))
    assert out.error is None
    assert out.data.items[0].title == "KSR Brief"


@pytest.mark.asyncio
async def test_happy_browse_folder(ctx, account):
    ctx.http.push({"files": [{"id": "d1", "name": "Clients", "mimeType": df.FOLDER}]})
    out = await h.browse_folder(ctx, BrowseFolderParams(folder="root"))
    assert out.error is None
    assert out.data.items[0].is_folder is True


@pytest.mark.asyncio
async def test_happy_list_shared_drives(ctx, account):
    ctx.http.push({"drives": [{"id": "sd1", "name": "Marketing"}]})
    out = await h.list_shared_drives(ctx, ListSharedDrivesParams())
    assert out.error is None
    assert out.data.items[0].title == "Marketing"


@pytest.mark.asyncio
async def test_happy_get_file(ctx, account):
    ctx.http.push({"id": "f1", "name": "Contract", "mimeType": "application/pdf"})
    out = await h.get_file(ctx, FileParam(file_id="f1"))
    assert out.error is None
    assert out.data.title == "Contract"


@pytest.mark.asyncio
async def test_happy_read_file_google_doc(ctx, account):
    ctx.http.push({"id": "doc1", "name": "Brief", "mimeType": df.GDOC})
    ctx.http.push("Hello world")
    out = await h.read_file(ctx, ReadFileParams(file_id="doc1"))
    assert out.error is None
    assert out.data.content == "Hello world"


@pytest.mark.asyncio
async def test_error_read_file_unsupported_type(ctx, account):
    """Binary types (images etc.) are correctly refused, not silently
    downloaded -- the safety behaviour drive_files.read_content enforces."""
    ctx.http.push({"id": "img1", "name": "Photo", "mimeType": "image/png"})
    out = await h.read_file(ctx, ReadFileParams(file_id="img1"))
    assert out.error is not None
    assert out.error_code == "GOOGLE_DRIVE_UNSUPPORTED_PREVIEW"


@pytest.mark.asyncio
async def test_happy_check_access(ctx, account):
    ctx.http.push({"user": {"emailAddress": "vlad@example.com", "displayName": "Vlad"},
                   "storageQuota": {}})
    ctx.http.push({"drives": []})
    out = await h.check_access(ctx, AccountParam())
    assert out.error is None
    assert out.data.can_read_files is True
    assert out.data.shared_drives_visible == 0


@pytest.mark.asyncio
async def test_happy_list_pinned_files_then_pin_shows_up(ctx, account):
    """list_pinned_files starts empty, then reflects a pin_file call --
    an ordinary two-step scenario exercising both together."""
    empty = await h.list_pinned_files(ctx, ListPinnedParams())
    assert empty.error is None
    assert empty.data.items == []

    ctx.http.push({"id": "f1", "name": "Roadmap", "mimeType": df.GDOC})
    pinned = await h.pin_file(ctx, PinFileParams(file_id="f1", pinned=True))
    assert pinned.error is None

    after = await h.list_pinned_files(ctx, ListPinnedParams())
    assert after.error is None
    assert len(after.data.items) == 1
    assert after.data.items[0].title == "Roadmap"


# ── switch_account: happy two-account lifecycle ─────────────────────────────

@pytest.mark.asyncio
async def test_happy_switch_account_between_two(ctx, account):
    second = await ctx.store.create("google_drive_accounts", {
        "email": "second@example.com", "provider": "google",
        "access_token": "tok2", "refresh_token": "ref2",
        "expires_at": "2099-01-01T00:00:00+00:00", "is_active": False,
    })
    out = await h.switch_account(ctx, AccountParam(account="second@example.com"))
    assert out.error is None
    assert out.data.account == "second@example.com"

    # Confirm the switch actually flipped is_active, not just returned text.
    refreshed_first = await ctx.store.get("google_drive_accounts", account.id)
    refreshed_second = await ctx.store.get("google_drive_accounts", second.id)
    assert refreshed_first.data["is_active"] is False
    assert refreshed_second.data["is_active"] is True


# ── blocked: no account connected at all ────────────────────────────────────

@pytest.mark.asyncio
async def test_blocked_check_access_with_no_account_connected(ctx):
    out = await h.check_access(ctx, AccountParam())
    assert out.error is not None
    assert out.error_code == "GOOGLE_DRIVE_ACCOUNT_MISSING"


@pytest.mark.asyncio
async def test_blocked_switch_account_unknown_email(ctx, account):
    out = await h.switch_account(ctx, AccountParam(account="nobody@example.com"))
    assert out.error is not None
    assert out.error_code == "GOOGLE_DRIVE_ACCOUNT_MISSING"


# ── adversarial: rejected before any HTTP call is made ──────────────────────

@pytest.mark.asyncio
async def test_adversarial_search_files_unknown_type_makes_no_http_call(ctx, account):
    out = await h.search_files(ctx, SearchFilesParams(file_type="carrier_pigeon"))
    assert out.error is not None
    assert ctx.http.calls == []


# ── recovery: expired token is refreshed transparently mid read_file ───────

@pytest.mark.asyncio
async def test_recovery_get_file_after_token_refresh(ctx, account):
    ctx.http.push({"error": "expired"}, status=401)
    ctx.http.push({"access_token": "fresh-token", "expires_in": 3600})
    ctx.http.push({"id": "f1", "name": "Recovered", "mimeType": df.GDOC})
    out = await h.get_file(ctx, FileParam(file_id="f1"))
    assert out.error is None
    assert out.data.title == "Recovered"
