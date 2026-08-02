"""Typed parameters and SDL entities for Google Drive Connector."""

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class AccountScoped(BaseModel):
    account: str = Field(
        "", description="Connected Google account email. Omit when only one account is connected."
    )


class NoParams(BaseModel):
    pass


class AccountParam(BaseModel):
    account: str = Field("", description="Connected Google account email")


class ListAccountsParams(BaseModel):
    refresh: bool = Field(False, description="Verify each account against Google Drive")


class SearchFilesParams(AccountScoped):
    query: str = Field("", description="Text in the file name or full-text index")
    file_type: str = Field(
        "", description="Optional type: folder, document, spreadsheet, presentation, pdf, office, image"
    )
    source: str = Field("all", description="Source: all, my_drive, or shared_drives")
    modified_after: str = Field("", description="Optional ISO date, e.g. 2026-08-01")
    limit: int = Field(25, ge=1, le=100, description="Maximum files to return")
    page_token: str = Field("", description="Continuation token from the previous page")


class BrowseFolderParams(AccountScoped):
    folder: str = Field("root", description="Folder id; 'root' opens My Drive")
    drive_id: str = Field("", description="Shared drive id when browsing a Shared drive")
    limit: int = Field(50, ge=1, le=100, description="Maximum children to return")
    page_token: str = Field("", description="Continuation token from the previous page")


class ListSharedDrivesParams(AccountScoped):
    query: str = Field("", description="Optional Shared drive name fragment")
    limit: int = Field(50, ge=1, le=100, description="Maximum Shared drives to return")
    page_token: str = Field("", description="Continuation token from the previous page")


class FileParam(AccountScoped):
    file_id: str = Field(..., description="Google Drive file id from search or browse results")


class ReadFileParams(FileParam):
    max_characters: int = Field(
        20000, ge=200, le=100000, description="Maximum extracted characters to return"
    )


class ReadSheetRangeParams(FileParam):
    worksheet: str = Field(..., description="Worksheet/tab title")
    range: str = Field(..., description="A1 range inside the worksheet, e.g. A1:H100")
    max_cells: int = Field(2000, ge=1, le=5000, description="Maximum cells to return")


class PinFileParams(FileParam):
    pinned: bool = Field(True, description="True to pin, false to unpin")


class ListPinnedParams(AccountScoped):
    limit: int = Field(50, ge=1, le=100, description="Maximum pinned files to return")


class SetContextParams(AccountScoped):
    enabled: bool = Field(..., description="Allow Drive to support Webbee answers for this account")


class DriveAccount(sdl.Entity):
    email: str = ""
    provider: str = "google"
    active: bool = False
    state: str = "connected"
    context_enabled: bool = False
    last_checked: str = ""


class DriveAccountList(sdl.EntityList[DriveAccount]):
    pass


class DriveFile(sdl.Entity):
    file_id: str = ""
    mime_type: str = ""
    file_type: str = ""
    modified_time: str = ""
    created_time: str = ""
    size: int = 0
    owner: str = ""
    parent_ids: list[str] = Field(default_factory=list)
    drive_id: str = ""
    web_view_link: str = ""
    thumbnail_link: str = ""
    is_folder: bool = False
    pinned: bool = False


class DriveFileList(sdl.EntityList[DriveFile]):
    next_page_token: str = ""


class SharedDrive(sdl.Entity):
    drive_id: str = ""
    created_time: str = ""


class SharedDriveList(sdl.EntityList[SharedDrive]):
    next_page_token: str = ""


class FileContent(DriveFile):
    content: str = ""
    export_format: str = ""
    truncated: bool = False
    worksheets: list[str] = Field(default_factory=list)
    preview_supported: bool = True


class SheetRange(sdl.Entity):
    file_id: str = ""
    worksheet: str = ""
    a1_range: str = ""
    values: list[list[object]] = Field(default_factory=list)
    rows: int = 0
    columns: int = 0
    cells: int = 0
    trimmed: bool = False


class AccessReport(sdl.Entity):
    email: str = ""
    can_read_files: bool = False
    shared_drives_visible: int = 0
    context_enabled: bool = False
    explanation: str = ""


class SettingResult(sdl.Entity):
    account: str = ""
    enabled: bool = False
    action: str = ""
