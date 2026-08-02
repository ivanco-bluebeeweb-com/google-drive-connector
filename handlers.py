"""Chat tools for accounts, files, sheets, pins and context permission."""

from imperal_sdk import ActionResult

import accounts
import drive_client as dc
import drive_files as df
from app import chat
from models import (
    AccessReport, AccountParam, BrowseFolderParams, DriveAccount, DriveAccountList,
    DriveFile, DriveFileList, FileContent, FileParam, ListAccountsParams,
    ListPinnedParams, ListSharedDrivesParams, NoParams, PinFileParams,
    ReadFileParams, ReadSheetRangeParams, SearchFilesParams, SetContextParams,
    SettingResult, SharedDrive, SharedDriveList, SheetRange,
)

PINS = "google_drive_pins"


def _error(out: dict) -> ActionResult:
    return ActionResult.error(out.get("error") or "Google Drive request failed.",
                              bool(out.get("retryable")), code=out.get("code") or dc.RESPONSE_UNEXPECTED)


def _success(data, summary: str, refresh=None) -> ActionResult:
    return ActionResult.success(data, summary=summary, refresh_panels=refresh)


async def _resolved(ctx, email: str = "") -> dict:
    return await accounts.resolve_account(ctx, email)


async def _pinned_ids(ctx, email: str) -> set[str]:
    page = await ctx.store.query(PINS, where={"email": email.lower()}, limit=100)
    return {str((x.data or {}).get("file_id") or "") for x in page.data}


def _file_entity(row: dict, pinned_ids: set[str] | None = None) -> DriveFile:
    row = dict(row)
    row["pinned"] = row.get("file_id") in (pinned_ids or set())
    return DriveFile(**row)


@chat.function("connect_google_drive", "Connect another Google account to Google Drive.",
               action_type="write", effects=["oauth.connect"],
               event="google-drive-connector-bluebee.account.updated", data_model=SettingResult)
async def connect_google_drive(ctx, params: NoParams) -> ActionResult:
    """Return the platform-owned Google authorization URL when OAuth is configured."""
    client_id = await ctx.secrets.get("google_client_id")
    client_secret = await ctx.secrets.get("google_client_secret")
    if not client_id or not client_secret:
        return ActionResult.error(
            "Google OAuth is not configured yet. The app owner must save its Google client ID and client secret in the app's Secrets before an account can connect.",
            retryable=False,
            code="GOOGLE_OAUTH_NOT_CONFIGURED",
        )
    if client_id == client_secret:
        return ActionResult.error(
            "Google Client ID and Client Secret contain the same value. Save each credential in its matching Secrets field before connecting.",
            retryable=False,
            code="GOOGLE_OAUTH_CREDENTIALS_DUPLICATED",
        )
    url = await ctx.oauth_authorize_url("google")
    return _success(SettingResult(id="google", title="Google OAuth", account="", enabled=True,
                                  action=url), "Open the Google authorization link to connect Drive.")


@chat.function("list_accounts", "List connected Google Drive accounts and connection state.",
               action_type="read", data_model=DriveAccountList)
async def list_accounts(ctx, params: ListAccountsParams) -> ActionResult:
    """List connected accounts and optionally verify their Drive access."""
    rows = []
    for doc in await accounts.all_accounts(ctx):
        data = doc.data or {}
        email = accounts.account_email(doc)
        label = accounts.account_label(doc)
        settings = await accounts.setting(ctx, email)
        state = str(settings.get("state") or "connected")
        checked = str(settings.get("last_checked") or "")
        if accounts.identity_missing(doc):
            state = "reconnect_required"
            email = ""
        elif params.refresh:
            verified = await accounts.verify(ctx, doc)
            state = "connected" if verified.get("ok") else "error"
            checked = str(verified.get("last_checked") or checked)
            email = str(verified.get("email") or email)
            label = email or label
        rows.append(DriveAccount(id=doc.id, title=label, email=email,
                                 active=bool(data.get("is_active")), state=state,
                                 context_enabled=bool(settings.get("context_enabled")), last_checked=checked))
    return _success(DriveAccountList(items=rows), f"Found {len(rows)} connected Google account(s).")


@chat.function("switch_account", "Change the active Google Drive account used by default.",
               action_type="write", effects=["account.active.update"],
               event="google-drive-connector-bluebee.account.updated", data_model=SettingResult)
async def switch_account(ctx, params: AccountParam) -> ActionResult:
    """Select one connected Google account as the default."""
    out = await accounts.activate(ctx, params.account)
    if not out.get("ok"): return _error(out)
    email = str((out["account"].data or {}).get("email") or params.account)
    return _success(SettingResult(id=email, title=email, account=email, enabled=True, action="activated"),
                    f"{email} is now the active Google Drive account.", ["drive_nav", "drive"])


@chat.function("check_access", "Verify what the selected Google account can read in Drive.",
               action_type="read", data_model=AccessReport)
async def check_access(ctx, params: AccountParam) -> ActionResult:
    """Verify Drive access and report visible Shared drives."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    doc = resolved["account"]
    verified = await accounts.verify(ctx, doc)
    if not verified.get("ok"): return _error(verified)
    email = str(verified.get("email") or (doc.data or {}).get("email") or "")
    drives = await df.shared_drives(ctx, doc, limit=100)
    count = len(drives.get("drives", [])) if drives.get("ok") else 0
    settings = await accounts.setting(ctx, email)
    entity = AccessReport(id=email, title=email, email=email, can_read_files=True,
                          shared_drives_visible=count, context_enabled=bool(settings.get("context_enabled")),
                          explanation="This account can read files already shared with it. The connector cannot grant itself access.")
    return _success(entity, "Google Drive access is working.")


@chat.function("search_files", "Search accessible Google Drive files by name or indexed content.",
               action_type="read", data_model=DriveFileList)
async def search_files(ctx, params: SearchFilesParams) -> ActionResult:
    """Run a server-side search over files accessible to one account."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    doc = resolved["account"]
    out = await df.search(ctx, doc, query=params.query, kind=params.file_type, source=params.source,
                          modified_after=params.modified_after, limit=params.limit, page_token=params.page_token)
    if not out.get("ok"): return _error(out)
    email = str((doc.data or {}).get("email") or ""); pins = await _pinned_ids(ctx, email)
    rows = [_file_entity(x, pins) for x in out["files"]]
    return _success(DriveFileList(items=rows, next_page_token=out["next_page_token"]),
                    f"Found {len(rows)} Drive item(s).")


@chat.function("browse_folder", "List one Google Drive folder level, including Shared drives.",
               action_type="read", data_model=DriveFileList)
async def browse_folder(ctx, params: BrowseFolderParams) -> ActionResult:
    """Read one folder level without crawling the Drive tree."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    doc = resolved["account"]
    out = await df.browse(ctx, doc, folder=params.folder, drive_id=params.drive_id,
                          limit=params.limit, page_token=params.page_token)
    if not out.get("ok"): return _error(out)
    pins = await _pinned_ids(ctx, str((doc.data or {}).get("email") or ""))
    rows = [_file_entity(x, pins) for x in out["files"]]
    return _success(DriveFileList(items=rows, next_page_token=out["next_page_token"]),
                    f"Listed {len(rows)} item(s) in this folder.")


@chat.function("list_shared_drives", "List Shared drives available to a connected Google account.",
               action_type="read", data_model=SharedDriveList)
async def list_shared_drives(ctx, params: ListSharedDrivesParams) -> ActionResult:
    """List Shared drives already available to one Google account."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    out = await df.shared_drives(ctx, resolved["account"], query=params.query,
                                 limit=params.limit, page_token=params.page_token)
    if not out.get("ok"): return _error(out)
    rows = [SharedDrive(**x) for x in out["drives"]]
    return _success(SharedDriveList(items=rows, next_page_token=out["next_page_token"]),
                    f"Found {len(rows)} Shared drive(s).")


@chat.function("get_file", "Read metadata for one accessible Google Drive file or folder.",
               action_type="read", data_model=DriveFile)
async def get_file(ctx, params: FileParam) -> ActionResult:
    """Read metadata for exactly one Drive item."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    out = await df.get_file(ctx, resolved["account"], params.file_id)
    if not out.get("ok"): return _error(out)
    pins = await _pinned_ids(ctx, str((resolved["account"].data or {}).get("email") or ""))
    return _success(_file_entity(out["file"], pins), f"Loaded {out['file']['title']}.")


@chat.function("read_file", "Read bounded text from a Google Doc, Slides file, or plain text file.",
               action_type="read", data_model=FileContent)
async def read_file(ctx, params: ReadFileParams) -> ActionResult:
    """Read bounded text or return the worksheets available in a Sheet."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    out = await df.read_content(ctx, resolved["account"], params.file_id, params.max_characters)
    if not out.get("ok"): return _error(out)
    return _success(FileContent(**out["file"], content=out["content"], export_format=out["export_format"],
                                truncated=out["truncated"], worksheets=out["worksheets"],
                                preview_supported=out["preview_supported"]),
                    "File content loaded." if out["content"] else "Choose a worksheet and range to read this spreadsheet.")


@chat.function("read_sheet_range", "Read a specific worksheet and bounded A1 range from Google Sheets.",
               action_type="read", data_model=SheetRange)
async def read_sheet_range(ctx, params: ReadSheetRangeParams) -> ActionResult:
    """Read a user-selected worksheet and bounded A1 range."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    out = await df.read_sheet_range(ctx, resolved["account"], params.file_id, params.worksheet,
                                    params.range, params.max_cells)
    if not out.get("ok"): return _error(out)
    return _success(SheetRange(id=params.file_id, title=out["a1_range"], file_id=params.file_id,
                               worksheet=params.worksheet, a1_range=out["a1_range"], values=out["values"],
                               rows=out["rows"], columns=out["columns"], cells=out["cells"], trimmed=out["trimmed"]),
                    f"Read {out['cells']} cell(s) from {out['a1_range']}.")


@chat.function("pin_file", "Pin or unpin a Drive file in Imperal without changing Google Drive.",
               action_type="write", effects=["pin.update"],
               event="google-drive-connector-bluebee.pin.updated", data_model=SettingResult)
async def pin_file(ctx, params: PinFileParams) -> ActionResult:
    """Change only the Imperal pin record; never mutate Google Drive."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    doc = resolved["account"]; email = str((doc.data or {}).get("email") or "").lower()
    existing = await ctx.store.query(PINS, where={"email": email, "file_id": params.file_id}, limit=10)
    if params.pinned and not existing.data:
        meta = await df.get_file(ctx, doc, params.file_id)
        if not meta.get("ok"): return _error(meta)
        f = meta["file"]
        await ctx.store.create(PINS, {"email": email, "file_id": params.file_id, "title": f["title"],
                                      "mime_type": f["mime_type"], "web_view_link": f["web_view_link"]})
    if not params.pinned:
        for row in existing.data: await ctx.store.delete(PINS, row.id)
    action = "pinned" if params.pinned else "unpinned"
    return _success(SettingResult(id=params.file_id, title=params.file_id, account=email,
                                  enabled=params.pinned, action=action), f"File {action} in Imperal.", ["drive"])


@chat.function("list_pinned_files", "List files pinned in Imperal for one Google Drive account.",
               action_type="read", data_model=DriveFileList)
async def list_pinned_files(ctx, params: ListPinnedParams) -> ActionResult:
    """List account-specific file pins stored in Imperal."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    email = str((resolved["account"].data or {}).get("email") or "").lower()
    page = await ctx.store.query(PINS, where={"email": email}, limit=params.limit)
    rows = [DriveFile(id=str((x.data or {}).get("file_id") or ""), title=str((x.data or {}).get("title") or "Untitled"),
                      file_id=str((x.data or {}).get("file_id") or ""), mime_type=str((x.data or {}).get("mime_type") or ""),
                      file_type=df.file_type(str((x.data or {}).get("mime_type") or "")),
                      web_view_link=str((x.data or {}).get("web_view_link") or ""), pinned=True) for x in page.data]
    return _success(DriveFileList(items=rows), f"Found {len(rows)} pinned file(s).")


@chat.function("set_context_permission", "Enable or disable explicit Drive context permission for one account.",
               action_type="write", effects=["context.permission.update"],
               event="google-drive-connector-bluebee.context.updated", data_model=SettingResult)
async def set_context_permission(ctx, params: SetContextParams) -> ActionResult:
    """Persist explicit per-account context permission in Imperal."""
    resolved = await _resolved(ctx, params.account)
    if not resolved.get("ok"): return _error(resolved)
    email = str((resolved["account"].data or {}).get("email") or "")
    await accounts.update_setting(ctx, email, {"context_enabled": params.enabled})
    state = "enabled" if params.enabled else "disabled"
    return _success(SettingResult(id=email, title=email, account=email, enabled=params.enabled,
                                  action="context_permission"), f"Drive context is {state} for {email}.", ["drive_nav", "drive"])
