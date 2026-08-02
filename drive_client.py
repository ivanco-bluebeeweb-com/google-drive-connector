"""Google Drive/Sheets HTTP funnel, token refresh and structured errors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"

ACCOUNT_MISSING = "GOOGLE_DRIVE_ACCOUNT_MISSING"
ACCOUNT_AMBIGUOUS = "GOOGLE_DRIVE_ACCOUNT_AMBIGUOUS"
TOKEN_REJECTED = "GOOGLE_DRIVE_TOKEN_REJECTED"
NOT_FOUND = "GOOGLE_DRIVE_NOT_FOUND"
VALIDATION_FAILED = "GOOGLE_DRIVE_VALIDATION_FAILED"
RESPONSE_UNEXPECTED = "GOOGLE_DRIVE_RESPONSE_UNEXPECTED"
UNSUPPORTED_PREVIEW = "GOOGLE_DRIVE_UNSUPPORTED_PREVIEW"
UNREACHABLE = "GOOGLE_DRIVE_UNREACHABLE"

_MESSAGES = {
    ACCOUNT_MISSING: "No Google Drive account is connected yet.",
    ACCOUNT_AMBIGUOUS: "Several Google accounts are connected; name the account to use.",
    TOKEN_REJECTED: "Google rejected this connection. Reconnect the Google account and try again.",
    NOT_FOUND: "Google Drive has no such file, or this account cannot access it.",
    VALIDATION_FAILED: "Google rejected the request as invalid.",
    RESPONSE_UNEXPECTED: "Google returned a response the connector could not safely interpret.",
    UNSUPPORTED_PREVIEW: "This file type cannot be previewed safely in the connector.",
    UNREACHABLE: "Could not reach Google Drive.",
    "PERMISSION_DENIED": "This Google account is not allowed to access that item.",
    "RATE_LIMITED": "Google Drive is rate-limiting requests; try again shortly.",
    "BACKEND_5XX": "Google Drive returned a server error; try again shortly.",
    "BACKEND_TIMEOUT": "Google Drive took too long to respond; try again shortly.",
}
_RETRYABLE = {"RATE_LIMITED", "BACKEND_5XX", "BACKEND_TIMEOUT", UNREACHABLE}


def fail(code: str, error: str = "") -> dict:
    return {"ok": False, "code": code, "error": error or _MESSAGES.get(code, "Google Drive request failed."),
            "retryable": code in _RETRYABLE}


def _body(resp):
    body = resp.body
    if isinstance(body, (str, bytes, bytearray)):
        try:
            return resp.json()
        except Exception:
            return body
    return body


def classify(status: int, body) -> dict:
    detail = ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            detail = str(err.get("message") or "")
    if status == 400:
        code = VALIDATION_FAILED
    elif status == 401:
        code = TOKEN_REJECTED
    elif status == 403:
        code = "RATE_LIMITED" if "rate" in detail.lower() or "quota" in detail.lower() else "PERMISSION_DENIED"
    elif status == 404:
        code = NOT_FOUND
    elif status == 429:
        code = "RATE_LIMITED"
    elif 500 <= status < 600:
        code = "BACKEND_5XX"
    else:
        code = RESPONSE_UNEXPECTED
    message = _MESSAGES.get(code, "Google Drive request failed.")
    if code == VALIDATION_FAILED and detail:
        message = f"Google rejected the request: {detail}"
    return fail(code, message)


def _timeout_code(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    return "BACKEND_TIMEOUT" if "timeout" in name or "timedout" in name else UNREACHABLE


async def refresh_access_token(ctx, account_doc) -> dict:
    """Refresh one saved OAuth account without exposing credentials."""
    data = account_doc.data or {}
    refresh_token = str(data.get("refresh_token") or "")
    if not refresh_token:
        return fail(TOKEN_REJECTED, "Google did not provide a refresh token. Reconnect the account and approve offline access.")
    try:
        client_id = await ctx.secrets.get("google_client_id")
        client_secret = await ctx.secrets.get("google_client_secret")
    except Exception:
        return fail(UNREACHABLE, "The connector could not read its OAuth configuration just now.")
    if not client_id or not client_secret:
        return fail(TOKEN_REJECTED, "Google OAuth is not configured for this connector yet.")
    try:
        resp = await ctx.http.post(
            TOKEN_URL,
            data={"client_id": client_id, "client_secret": client_secret,
                  "refresh_token": refresh_token, "grant_type": "refresh_token"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30,
        )
    except Exception as exc:
        return fail(_timeout_code(exc))
    body = _body(resp)
    if resp.status_code >= 400:
        return fail(TOKEN_REJECTED)
    if not isinstance(body, dict) or not body.get("access_token"):
        return fail(RESPONSE_UNEXPECTED)
    expires = datetime.now(timezone.utc) + timedelta(seconds=int(body.get("expires_in") or 3600))
    updated = {"access_token": str(body["access_token"]), "expires_at": expires.isoformat()}
    try:
        await ctx.store.update("google_drive_accounts", account_doc.id, updated)
    except Exception:
        return fail(UNREACHABLE, "The refreshed Google connection could not be saved.")
    return {"ok": True, "access_token": updated["access_token"]}


async def request(ctx, account_doc, method: str, url: str, *, params: dict | None = None,
                  retry_auth: bool = True, timeout: int = 30) -> dict:
    """Call Google once, refresh on 401, and return a normalized envelope."""
    token = str((account_doc.data or {}).get("access_token") or "")
    if not token:
        return fail(TOKEN_REJECTED)
    kwargs = {"headers": {"Authorization": f"Bearer {token}", "Accept": "application/json"},
              "timeout": timeout}
    if params:
        kwargs["params"] = params
    try:
        resp = await getattr(ctx.http, method.lower())(url, **kwargs)
    except Exception as exc:
        return fail(_timeout_code(exc))
    body = _body(resp)
    if resp.status_code == 401 and retry_auth:
        fresh = await refresh_access_token(ctx, account_doc)
        if not fresh.get("ok"):
            return fresh
        account_doc.data["access_token"] = fresh["access_token"]
        return await request(ctx, account_doc, method, url, params=params, retry_auth=False, timeout=timeout)
    if resp.status_code >= 400:
        return classify(resp.status_code, body)
    return {"ok": True, "data": body, "response": resp}


FILE_FIELDS = "id,name,mimeType,modifiedTime,createdTime,size,owners(displayName,emailAddress),parents,driveId,webViewLink,thumbnailLink,trashed"


def escape_query(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


def encoded_a1(worksheet: str, a1_range: str) -> str:
    return quote(f"'{worksheet.replace(chr(39), chr(39) * 2)}'!{a1_range}", safe="")
