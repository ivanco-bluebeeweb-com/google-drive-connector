# Google Drive Connector — Panel Component Sketches

**Status:** approved UX mapped to SDK primitives before implementation
**Date:** 2026-08-02

All strings shown to users are English. These sketches use only primitives documented in `Docs/imperal-docs/pages/en/sdk/ui-primitives-reference.md` and actions from `ui-actions-reference.md`.

## Panel topology

- `drive_nav` — left slot, persistent navigation and active-account state.
- `connect` — center overlay, first-run OAuth entry point.
- `home` — center overlay, overview and primary paths.
- `search` — center overlay, global server-side search.
- `folder` — center overlay, one-level folder browser with breadcrumbs.
- `shared_drives` — center overlay, Shared drives list.
- `file_detail` — center overlay, metadata and bounded preview.
- `accounts` — center overlay, account/access controls.

The left panel auto-opens `connect` when no account exists and `home` when an account exists. `auto_action` is attached to the left-panel root only.

## 1. Connect Google Drive

```text
ui.Page(title="Connect Google Drive")
└── ui.Stack(v)
    ├── ui.Alert(info, read-only access explanation)
    ├── ui.Card(title="What Webbee can access")
    │   └── ui.Stack(v)
    │       ├── ui.Text("My Drive")
    │       ├── ui.Text("Files shared with this account")
    │       └── ui.Text("Shared drives available to this account")
    ├── ui.Button("Connect Google account", primary,
    │             ui.Open(authorize_url))
    └── ui.Text(caption, privacy explanation)
```

OAuth result UI is platform-owned. On return, the left panel detects the newly persisted account and opens Home.

## 2. Drive Home

```text
ui.Page(title="Google Drive", subtitle=active_account_email)
└── ui.Stack(v)
    ├── ui.Card(title=account_name, subtitle=connection health)
    │   └── ui.Toggle("Use Drive as context", account-specific,
    │                 ui.Call("set_context_permission"))
    ├── ui.Grid(columns=3)
    │   ├── ui.Card("Search files", on_click=panel search)
    │   ├── ui.Card("Browse folders", on_click=panel folder root)
    │   └── ui.Card("Shared drives", on_click=panel shared_drives)
    ├── ui.Section("Recently changed")
    │   └── ui.List(server-fetched rows; searchable=False)
    ├── ui.Section("Pinned")
    │   └── ui.List(rows or ui.Empty with pinning guidance)
    └── ui.Row(quick type filter buttons)
```

`ui.List(searchable=True)` is deliberately not used for global Drive search because it only filters the loaded rows client-side.

## 3. Search Results

```text
ui.Page(title="Search Google Drive")
└── ui.Stack(v)
    ├── ui.Form(action="__panel__search")
    │   ├── ui.Input(query)
    │   ├── ui.Select(source: all/my-drive/shared-drives)
    │   ├── ui.Select(file_type)
    │   ├── ui.DatePicker(modified_after)
    │   └── submit "Search"
    ├── ui.Text(result count / continuation state)
    ├── ui.List(searchable=False, server-returned page)
    │   └── ui.ListItem(..., on_click=file detail or folder,
    │                   actions=[pin/unpin])
    └── ui.Row(previous / next page buttons when applicable)
```

Drive `nextPageToken` is passed only through panel actions. Search always executes against the Drive API.

## 4. Folder Browser

```text
ui.Page(title=current_folder_name, subtitle=account_email)
└── ui.Stack(v)
    ├── ui.Row(breadcrumb ui.Link nodes using panel calls)
    ├── ui.List(folders first, then files)
    │   ├── ui.ListItem(folder, on_click=nested folder)
    │   └── ui.ListItem(file, on_click=file detail, pin action)
    └── ui.Row(previous / next page buttons when applicable)
```

No recursive tree is loaded. Each navigation fetches one level.

## 5. Shared Drives

```text
ui.Page(title="Shared drives")
└── ui.Stack(v)
    ├── ui.Input(server-side name query, on_submit=panel call)
    └── ui.List(searchable=False)
        └── ui.ListItem(drive, on_click=folder browser at drive root)
```

No Shared drives returns `ui.Empty`; it is not rendered as an error.

## 6. File Details and Preview

```text
ui.Page(title=file_name, subtitle=mime_label)
└── ui.Stack(v)
    ├── ui.Row
    │   ├── ui.Button("Open in Google Drive", ui.Open(webViewLink))
    │   ├── ui.Button("Ask Webbee about this file", ui.Send(grounded file id))
    │   └── ui.Button("Pin" / "Unpin", ui.Call(...))
    ├── ui.KeyValue(owner, location, created, modified, size)
    ├── ui.Row(parent-path ui.Link nodes)
    └── ui.Section("Preview")
        ├── Sheet:
        │   └── ui.Form(action="__panel__file_detail")
        │       ├── ui.Select(worksheet)
        │       ├── ui.Input(A1 range)
        │       └── submit "Load range"
        │   └── ui.DataTable(bounded rows) or ui.Code(CSV-like fallback)
        ├── Image: ui.Image(thumbnail, alt=file_name)
        ├── Readable text: ui.Markdown / ui.Code with truncation notice
        └── Unsupported: ui.Alert(info, open-original guidance)
```

Preview is loaded only for the selected file. Sheet range is validated and bounded before the API call.

## 7. Accounts and Access

```text
ui.Page(title="Accounts & access")
└── ui.Stack(v)
    ├── ui.List(accounts)
    │   └── ui.ListItem(email, active badge, on_click=switch account)
    ├── ui.Card(title="Context permission")
    │   └── ui.Toggle(account-specific, ui.Call("set_context_permission"))
    ├── ui.Alert(info, scopes in human language)
    └── ui.Row
        ├── ui.Button("Re-check access", ui.Call("check_access"))
        ├── ui.Button("Connect another account", ui.Open(authorize_url))
        └── ui.Button("Disconnect", destructive,
                      ui.Call("disconnect_account"), confirmed by host/dialog)
```

Disconnect removes only the Imperal account record/tokens and account-specific local settings. It never calls a Drive mutation endpoint.

## Empty and failure states

- No accounts → Connect screen.
- No search results → `ui.Empty("No matching files are accessible to this account.")`.
- No Shared drives → calm informational empty state.
- Revoked/expired grant → error alert with `Reconnect Google account`; never claim a file is missing.
- File unavailable → explain only that the selected account cannot currently access it.
- Unsupported preview → metadata and `Open in Google Drive` remain available.
- Rate limit/backend failure → structured error, retry guidance, no fabricated cause.
