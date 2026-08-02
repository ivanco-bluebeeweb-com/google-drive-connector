"""Connected-account resolution and per-account settings."""

from __future__ import annotations

from datetime import datetime, timezone

import drive_client as dc

ACCOUNTS = "google_drive_accounts"
SETTINGS = "google_drive_settings"


async def all_accounts(ctx) -> list:
    page = await ctx.store.query(ACCOUNTS, limit=100)
    return list(page.data)


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
    return {"ok": True, "about": data, "last_checked": checked}


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
