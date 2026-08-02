"""Connected-account resolution and per-account settings."""

from __future__ import annotations

from datetime import datetime, timezone

import drive_client as dc

ACCOUNTS = "google_drive_accounts"
SETTINGS = "google_drive_settings"
UNKNOWN_EMAILS = {"", "unknown", "unknown@unknown", "google account"}


def account_email(doc) -> str:
    return str((doc.data or {}).get("email") or "").strip()


def account_label(doc) -> str:
    email = account_email(doc)
    if email.lower() not in UNKNOWN_EMAILS:
        return email
    name = str((doc.data or {}).get("display_name") or "").strip()
    return name if name and name.lower() != "unknown" else "Google account needs reconnecting"


def identity_missing(doc) -> bool:
    return account_email(doc).lower() in UNKNOWN_EMAILS


async def all_accounts(ctx) -> list:
    page = await ctx.store.query(ACCOUNTS, limit=100)
    return list(page.data)


async def repair_identity(ctx, doc):
    """Recover an incomplete OAuth identity from Drive's read-only about endpoint."""
    if not identity_missing(doc):
        return {"ok": True, "account": doc, "email": account_email(doc)}
    out = await verify(ctx, doc)
    if not out.get("ok") or not out.get("email"):
        return out
    repaired = await ctx.store.get(ACCOUNTS, doc.id)
    return {"ok": True, "account": repaired or doc, "email": out["email"]}


async def disconnect(ctx, account_id: str, *, pins_collection: str = "google_drive_pins") -> dict:
    """Remove one OAuth account record and its account-scoped local data from Imperal."""
    doc = await ctx.store.get(ACCOUNTS, account_id)
    if not doc:
        return dc.fail(dc.ACCOUNT_MISSING, "That Google Drive account is no longer connected.")
    email = account_email(doc).lower()
    if email:
        for collection in (SETTINGS, pins_collection):
            page = await ctx.store.query(collection, where={"email": email}, limit=100)
            for item in page.data:
                await ctx.store.delete(collection, item.id)
    await ctx.store.delete(ACCOUNTS, account_id)
    remaining = await all_accounts(ctx)
    if remaining and not any(bool((x.data or {}).get("is_active")) for x in remaining):
        await ctx.store.update(ACCOUNTS, remaining[0].id, {"is_active": True})
    return {"ok": True, "account_id": account_id, "label": account_label(doc)}


async def resolve_account(ctx, reference: str = "") -> dict:
    docs = await all_accounts(ctx)
    if not docs:
        return dc.fail(dc.ACCOUNT_MISSING)
    wanted = (reference or "").strip().lower()
    if wanted:
        matches = [d for d in docs if str((d.data or {}).get("email") or "").lower() == wanted]
        if not matches:
            matches = [d for d in docs if wanted in str((d.data or {}).get("email") or "").lower()]
        if not matches:
            emails = ", ".join(str((d.data or {}).get("email") or "unknown") for d in docs)
            return dc.fail(dc.ACCOUNT_MISSING, f"That Google account is not connected. Connected: {emails}.")
        if len(matches) > 1:
            return dc.fail(dc.ACCOUNT_AMBIGUOUS)
        return {"ok": True, "account": matches[0]}
    active = [d for d in docs if bool((d.data or {}).get("is_active"))]
    if len(active) == 1:
        return {"ok": True, "account": active[0]}
    if len(docs) == 1:
        return {"ok": True, "account": docs[0]}
    emails = ", ".join(str((d.data or {}).get("email") or "unknown") for d in docs)
    return dc.fail(dc.ACCOUNT_AMBIGUOUS, f"Several Google accounts are connected; name one: {emails}.")


async def setting(ctx, email: str) -> dict:
    page = await ctx.store.query(SETTINGS, where={"email": email.lower()}, limit=1)
    if not page.data:
        return {"context_enabled": False, "last_checked": ""}
    return dict(page.data[0].data or {})


async def update_setting(ctx, email: str, fields: dict) -> dict:
    key = email.lower()
    page = await ctx.store.query(SETTINGS, where={"email": key}, limit=1)
    payload = {"email": key, **fields}
    if page.data:
        doc = await ctx.store.update(SETTINGS, page.data[0].id, payload)
    else:
        doc = await ctx.store.create(SETTINGS, payload)
    return dict(doc.data or payload)


async def verify(ctx, account_doc) -> dict:
    out = await dc.request(ctx, account_doc, "GET", f"{dc.DRIVE_API}/about",
                           params={"fields": "user(displayName,emailAddress),storageQuota(limit,usage)"})
    email = str((account_doc.data or {}).get("email") or "")
    checked = datetime.now(timezone.utc).isoformat()
    await update_setting(ctx, email, {"last_checked": checked, "state": "connected" if out.get("ok") else "error"})
    if not out.get("ok"):
        return out
    data = out.get("data") if isinstance(out.get("data"), dict) else {}
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    verified_email = str(user.get("emailAddress") or "").strip()
    display_name = str(user.get("displayName") or "").strip()
    repair = {}
    if verified_email and identity_missing(account_doc):
        repair["email"] = verified_email
    if display_name:
        repair["display_name"] = display_name
    if repair:
        await ctx.store.update(ACCOUNTS, account_doc.id, repair)
        account_doc.data.update(repair)
    return {"ok": True, "about": data, "email": verified_email or account_email(account_doc),
            "last_checked": checked}


async def activate(ctx, email: str) -> dict:
    found = await resolve_account(ctx, email)
    if not found.get("ok"):
        return found
    chosen = found["account"]
    for doc in await all_accounts(ctx):
        desired = doc.id == chosen.id
        if bool((doc.data or {}).get("is_active")) != desired:
            await ctx.store.update(ACCOUNTS, doc.id, {"is_active": desired})
    return {"ok": True, "account": chosen}
