# Google Drive Connector

Read-only Google Drive context for Webbee: connect Google accounts through the platform OAuth flow, search accessible files, browse My Drive and Shared drives, preview bounded text, read an explicit Google Sheets range, pin important files in Imperal, and opt in to general Drive context per account.

## Product boundaries

- Google scopes are `drive.readonly` and `spreadsheets.readonly`.
- The connector does not create, edit, move, share, trash or delete Drive files.
- It never crawls the whole Drive in the background.
- Google Sheets require a worksheet plus an exact bounded A1 range.
- Pins live in Imperal and do not change Google Drive.
- General Drive context is disabled by default and enabled explicitly per Google account.

## Developer setup

The extension uses `ext.oauth("google", collection="google_drive_accounts", ...)`. Set the app-scoped `google_client_id` and `google_client_secret` in the Imperal Developer Portal. The platform owns the callback, token exchange and connected-account record.

Google Cloud must have the Drive API and Sheets API enabled, and its OAuth consent screen must include the same read-only scopes declared in `app.py`.

## Local checks

```bash
imperal build .
imperal validate .
pytest
```

The approved UX lives in `docs/ux-spec.md`; the required pre-code component tree is in `design/component-sketches.md`.
