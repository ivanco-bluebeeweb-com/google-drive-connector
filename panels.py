"""Approved Google Drive panel flows mapped to SDK primitives."""

from __future__ import annotations

from imperal_sdk import ui

import accounts
import drive_files as df
from app import ext

PINS = "google_drive_pins"


def _email(doc) -> str:
    return str((doc.data or {}).get("email") or "")


async def _current(ctx, requested: str = ""):
    out = await accounts.resolve_account(ctx, requested)
    return out.get("account") if out.get("ok") else None


def _file_item(row: dict, account: str):
    file_id = row.get("file_id", "")
    if row.get("is_folder"):
        action = ui.Call("__panel__drive", view="folder", account=account,
                         folder_id=file_id, drive_id=row.get("drive_id", ""), folder_name=row.get("title", "Folder"))
    else:
        action = ui.Call("__panel__drive", view="file", account=account, file_id=file_id)
    kind = row.get("file_type", "file").replace("_", " ").title()
    changed = str(row.get("modified_time") or "")[:16].replace("T", " ")
    subtitle = " · ".join(x for x in [kind, changed, row.get("owner", "")] if x)
    return ui.ListItem(id=file_id, title=row.get("title", "Untitled"), subtitle=subtitle,
                       icon="Folder" if row.get("is_folder") else "FileText", on_click=action)


@ext.panel("drive_nav", slot="left", title="Google Drive", icon="HardDrive",
           default_width=280, min_width=220, max_width=400,
           refresh="on_event:google-drive-connector.account.updated")
async def drive_nav(ctx, account="", **kwargs):
    docs = await accounts.all_accounts(ctx)
    if not docs:
        root = ui.Stack(children=[
            ui.Empty(message="No Google Drive account connected."),
            ui.Button("Connect Google account", icon="Plus",
                      on_click=ui.Call("__panel__drive", view="connect")),
        ])
        root.props["auto_action"] = ui.Call("__panel__drive", view="connect")
        return root
    active = await _current(ctx, account)
    active_email = _email(active) if active else _email(docs[0])
    items = [
        ui.ListItem(id="home", title="Home", icon="Home",
                    on_click=ui.Call("__panel__drive", view="home", account=active_email)),
        ui.ListItem(id="search", title="Search files", icon="Search",
                    on_click=ui.Call("__panel__drive", view="search", account=active_email)),
        ui.ListItem(id="folders", title="My Drive", icon="Folder",
                    on_click=ui.Call("__panel__drive", view="folder", account=active_email, folder_id="root")),
        ui.ListItem(id="shared", title="Shared drives", icon="Users",
                    on_click=ui.Call("__panel__drive", view="shared", account=active_email)),
        ui.ListItem(id="accounts", title="Accounts & access", icon="Settings",
                    on_click=ui.Call("__panel__drive", view="accounts", account=active_email)),
    ]
    root = ui.Stack(children=[
        ui.Text(active_email, variant="caption"), ui.List(items=items),
        ui.Button("Connect another account", icon="Plus", variant="ghost",
                  on_click=ui.Call("__panel__drive", view="connect")),
    ])
    if not kwargs.get("view"):
        root.props["auto_action"] = ui.Call("__panel__drive", view="home", account=active_email)
    return root


@ext.panel("drive", slot="center", title="Google Drive", icon="HardDrive", center_overlay=True)
async def drive(ctx, view="home", account="", query="", file_type="", source="all",
                modified_after="", folder_id="root", folder_name="", drive_id="",
                file_id="", worksheet="", a1_range="A1:H100", **kwargs):
    if view == "connect":
        return await _connect(ctx)
    doc = await _current(ctx, account)
    if not doc:
        return await _connect(ctx)
    account = _email(doc)
    if view == "search":
        return await _search(ctx, doc, account, query, file_type, source, modified_after)
    if view == "folder":
        return await _folder(ctx, doc, account, folder_id, folder_name, drive_id)
    if view == "shared":
        return await _shared(ctx, doc, account, query)
    if view == "file" and file_id:
        return await _file(ctx, doc, account, file_id, worksheet, a1_range)
    if view == "accounts":
        return await _accounts(ctx, account)
    return await _home(ctx, doc, account)


async def _connect(ctx):
    try:
        url = await ctx.oauth_authorize_url("google")
    except Exception:
        return ui.Page(title="Connect Google Drive", children=[
            ui.Alert("Google OAuth is not configured for this connector yet.", type="error")
        ])
    return ui.Page(title="Connect Google Drive", children=[
        ui.Alert("Imperal can only read files this Google account can already access. The connector is read-only."),
        ui.Card(title="What Webbee can access", content=ui.Stack(children=[
            ui.Text("My Drive"), ui.Text("Files shared with this account"),
            ui.Text("Shared drives available to this account"),
        ])),
        ui.Button("Connect Google account", icon="ExternalLink", on_click=ui.Open(url)),
        ui.Text("Google handles authorization. Imperal never asks for your Google password.", variant="caption"),
    ])


async def _home(ctx, doc, account):
    settings = await accounts.setting(ctx, account)
    recent = await df.search(ctx, doc, limit=10)
    recent_rows = recent.get("files", []) if recent.get("ok") else []
    pins_page = await ctx.store.query(PINS, where={"email": account.lower()}, limit=10)
    pin_items = [ui.ListItem(
        id=str((x.data or {}).get("file_id") or ""), title=str((x.data or {}).get("title") or "Untitled"),
        icon="Pin", on_click=ui.Call("__panel__drive", view="file", account=account,
                                     file_id=str((x.data or {}).get("file_id") or ""))) for x in pins_page.data]
    return ui.Page(title="Google Drive", subtitle=account, children=[
        ui.Card(title=account, subtitle="Connected", content=ui.Toggle(
            label="Allow Webbee to use Drive as supporting context",
            value=bool(settings.get("context_enabled")), param_name="enabled",
            on_change=ui.Call("set_context_permission", account=account))),
        ui.Stack(direction="h", wrap=True, children=[
            ui.Button("Search files", icon="Search", on_click=ui.Call("__panel__drive", view="search", account=account)),
            ui.Button("Browse folders", icon="Folder", variant="secondary",
                      on_click=ui.Call("__panel__drive", view="folder", account=account, folder_id="root")),
            ui.Button("Shared drives", icon="Users", variant="secondary",
                      on_click=ui.Call("__panel__drive", view="shared", account=account)),
        ]),
        ui.Section(title="Pinned", children=[ui.List(items=pin_items) if pin_items else ui.Empty("No pinned files yet.")]),
        ui.Section(title="Recently changed", children=[
            ui.List(items=[_file_item(x, account) for x in recent_rows]) if recent_rows else ui.Empty("No recent files available.")
        ]),
        ui.Stack(direction="h", wrap=True, children=[
            ui.Button(label, variant="ghost", size="sm", on_click=ui.Call(
                "__panel__drive", view="search", account=account, file_type=kind))
            for label, kind in [("Documents", "document"), ("Spreadsheets", "spreadsheet"),
                                ("Presentations", "presentation"), ("PDFs", "pdf"), ("Images", "image")]
        ]),
    ])


async def _search(ctx, doc, account, query, kind, source, modified_after):
    out = await df.search(ctx, doc, query=query, kind=kind, source=source,
                          modified_after=modified_after, limit=50)
    rows = out.get("files", []) if out.get("ok") else []
    filters = ui.Form(action="__panel__drive", submit_label="Search", defaults={"view": "search", "account": account}, children=[
        ui.Input(param_name="query", value=query, placeholder="Client, contract, proposal…"),
        ui.Select(param_name="file_type", value=kind, placeholder="Any file type", options=[
            {"label": "Any type", "value": ""}, {"label": "Folder", "value": "folder"},
            {"label": "Document", "value": "document"}, {"label": "Spreadsheet", "value": "spreadsheet"},
            {"label": "Presentation", "value": "presentation"}, {"label": "PDF", "value": "pdf"},
            {"label": "Office file", "value": "office"}, {"label": "Image", "value": "image"},
        ]),
        ui.Select(param_name="source", value=source, options=[
            {"label": "All accessible Drive", "value": "all"}, {"label": "My Drive", "value": "my_drive"},
            {"label": "Shared drives", "value": "shared_drives"},
        ]),
        ui.Input(param_name="modified_after", value=modified_after, placeholder="Modified after: YYYY-MM-DD"),
    ])
    body = ui.Alert(out.get("error", "Search failed."), type="error") if not out.get("ok") else (
        ui.List(items=[_file_item(x, account) for x in rows], total_items=len(rows)) if rows else ui.Empty("No matching files."))
    return ui.Page(title="Search Google Drive", subtitle=account, children=[filters, body])


async def _folder(ctx, doc, account, folder_id, folder_name, drive_id):
    out = await df.browse(ctx, doc, folder=folder_id or "root", drive_id=drive_id, limit=100)
    if not out.get("ok"):
        return ui.Page(title=folder_name or "My Drive", children=[ui.Alert(out.get("error", "Folder unavailable."), type="error")])
    title = folder_name or ("Shared drive" if drive_id else "My Drive")
    return ui.Page(title=title, subtitle=account, children=[
        ui.Button("Back to Home", icon="ArrowLeft", variant="ghost",
                  on_click=ui.Call("__panel__drive", view="home", account=account)),
        ui.List(items=[_file_item(x, account) for x in out["files"]], total_items=len(out["files"]))
        if out["files"] else ui.Empty("This folder is empty."),
    ])


async def _shared(ctx, doc, account, query):
    out = await df.shared_drives(ctx, doc, query=query, limit=100)
    rows = out.get("drives", []) if out.get("ok") else []
    form = ui.Form(action="__panel__drive", submit_label="Search", defaults={"view": "shared", "account": account},
                   children=[ui.Input(param_name="query", value=query, placeholder="Shared drive name")])
    items = [ui.ListItem(id=x["drive_id"], title=x["title"], subtitle=x.get("created_time", "")[:10], icon="Users",
                         on_click=ui.Call("__panel__drive", view="folder", account=account,
                                          folder_id=x["drive_id"], folder_name=x["title"], drive_id=x["drive_id"])) for x in rows]
    return ui.Page(title="Shared drives", subtitle=account, children=[form,
        ui.List(items=items) if items else ui.Empty("No Shared drives are available to this account.")])


async def _file(ctx, doc, account, file_id, worksheet, a1_range):
    meta = await df.get_file(ctx, doc, file_id)
    if not meta.get("ok"):
        return ui.Page(title="File", children=[ui.Alert(meta.get("error", "File unavailable."), type="error")])
    f = meta["file"]
    details = ui.KeyValue(items=[
        {"key": "Type", "value": f["file_type"]}, {"key": "Owner", "value": f["owner"] or "—"},
        {"key": "Modified", "value": f["modified_time"] or "—"}, {"key": "Size", "value": str(f["size"]) if f["size"] else "—"},
    ], columns=2)
    actions = ui.Stack(direction="h", wrap=True, children=[
        ui.Button("Ask Webbee about this file", icon="MessageCircle", on_click=ui.Send(
            f"Read and help me with Google Drive file '{f['title']}' (file_id: {file_id}, account: {account}).")),
        ui.Button("Open in Google Drive", icon="ExternalLink", variant="secondary", on_click=ui.Open(f["web_view_link"]))
        if f["web_view_link"] else ui.Text("No Google Drive link available.", variant="caption"),
        ui.Button("Pin in Imperal", icon="Pin", variant="ghost", on_click=ui.Call("pin_file", account=account,
                                                                                   file_id=file_id, pinned=True)),
    ])
    preview = await df.read_content(ctx, doc, file_id, 20000)
    if preview.get("ok") and preview.get("export_format") == "sheet-range-required":
        sheets = preview.get("worksheets", [])
        chosen = worksheet if worksheet in sheets else (sheets[0] if sheets else "")
        form = ui.Form(action="__panel__drive", submit_label="Read range", defaults={
            "view": "file", "account": account, "file_id": file_id}, children=[
            ui.Select(param_name="worksheet", value=chosen,
                      options=[{"label": x, "value": x} for x in sheets], placeholder="Choose worksheet"),
            ui.Input(param_name="a1_range", value=a1_range, placeholder="A1:H100"),
        ])
        range_out = await df.read_sheet_range(ctx, doc, file_id, chosen, a1_range, 2000) if worksheet else None
        range_ui = ui.Empty("Choose a worksheet and exact A1 range.")
        if range_out and range_out.get("ok"):
            values = range_out["values"]
            range_ui = ui.Code("\n".join("\t".join(str(v) for v in row) for row in values), language="text")
        elif range_out:
            range_ui = ui.Alert(range_out.get("error", "Range unavailable."), type="error")
        preview_ui = ui.Stack(children=[form, range_ui])
    elif preview.get("ok"):
        preview_ui = ui.Code(preview.get("content", "") or "No text content.", language="text")
    else:
        preview_ui = ui.Alert(preview.get("error", "Preview unavailable. Open the original in Google Drive."), type="info")
    return ui.Page(title=f["title"], subtitle=f["file_type"].title(), children=[details, actions,
                                                                                ui.Section(title="Preview", children=[preview_ui])])


async def _accounts(ctx, active_email):
    docs = await accounts.all_accounts(ctx)
    items = []
    for doc in docs:
        email = _email(doc); settings = await accounts.setting(ctx, email)
        state = settings.get("state", "connected")
        items.append(ui.ListItem(id=doc.id, title=email, subtitle=f"{state} · Context {'on' if settings.get('context_enabled') else 'off'}",
                                 selected=email == active_email, icon="User",
                                 on_click=ui.Call("switch_account", account=email)))
    return ui.Page(title="Accounts & access", children=[
        ui.List(items=items),
        ui.Button("Re-check active account", icon="RefreshCw", on_click=ui.Call("check_access", account=active_email)),
        ui.Button("Connect another account", icon="Plus", variant="secondary",
                  on_click=ui.Call("__panel__drive", view="connect")),
        ui.Alert("Disconnecting an OAuth account is managed by the platform account connection settings.", type="info"),
    ])
