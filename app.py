"""Google Drive Connector declaration and unified OAuth configuration."""

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "google-drive-connector-bluebee",
    version="0.1.3",
    display_name="Google Drive Connector",
    description=(
        "PAUSED — Google OAuth/API limitations currently prevent a reliable "
        "Google Drive connection. Development is on hold."
    ),
    icon="icon.svg",
    capabilities=["google-drive:read", "google-drive:settings"],
    actions_explicit=True,
)

chat = ChatExtension(
    ext,
    tool_name="google_drive",
    description=(
        "Google Drive Connector -- connect Google accounts, search and browse "
        "accessible files, read documents and bounded spreadsheet ranges, and "
        "manage pins and explicit Drive-context permission."
    ),
)

# Drive metadata/read-only covers search, folders, downloads/exports and Shared
# drives without granting any mutation permission. Sheets readonly is separate.
ext.oauth(
    "google",
    collection="google_drive_accounts",
    scopes=[
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ],
)

# Developer-owned OAuth app credentials. They are set once in the Developer
# Portal and are never shown to end users.
ext.secret(
    "google_client_id",
    "Google OAuth client ID for Google Drive Connector.",
    required=True,
    scope="app",
)(lambda: None)
ext.secret(
    "google_client_secret",
    "Google OAuth client secret for Google Drive Connector.",
    required=True,
    scope="app",
)(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Fast configuration health; no third-party call."""
    try:
        page = await ctx.store.query("google_drive_accounts", limit=1)
        count = len(page.data)
    except Exception:
        count = 0
    return {
        "healthy": count > 0,
        "accounts_configured": count,
        "detail": "Google account connected." if count else "No Google account connected yet.",
        "version": "0.1.3",
    }
