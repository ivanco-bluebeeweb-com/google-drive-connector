"""Read-only Google Drive operations and safe content extraction."""

from __future__ import annotations

import re

import drive_client as dc

FOLDER = "application/vnd.google-apps.folder"
GDOC = "application/vnd.google-apps.document"
GSHEET = "application/vnd.google-apps.spreadsheet"
GSLIDES = "application/vnd.google-apps.presentation"

TYPE_MIMES = {
    "folder": [FOLDER],
    "document": [GDOC],
    "spreadsheet": [GSHEET],
    "presentation": [GSLIDES],
    "pdf": ["application/pdf"],
}


def file_type(mime: str) -> str:
    if mime == FOLDER:
        return "folder"
    if mime == GDOC:
        return "document"
    if mime == GSHEET:
        return "spreadsheet"
    if mime == GSLIDES:
        return "presentation"
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("image/"):
        return "image"
    if "officedocument" in mime or "msword" in mime or "ms-excel" in mime or "ms-powerpoint" in mime:
        return "office"
    if mime.startswith("text/") or mime in {"application/json", "application/xml"}:
        return "text"
    return "file"


def to_file(raw: dict) -> dict:
    owners = raw.get("owners") or []
    owner = ""
    if owners and isinstance(owners[0], dict):
        owner = str(owners[0].get("emailAddress") or owners[0].get("displayName") or "")
    return {
        "id": str(raw.get("id") or ""), "title": str(raw.get("name") or "Untitled"),
        "file_id": str(raw.get("id") or ""), "mime_type": str(raw.get("mimeType") or ""),
        "file_type": file_type(str(raw.get("mimeType") or "")),
        "modified_time": str(raw.get("modifiedTime") or ""), "created_time": str(raw.get("createdTime") or ""),
        "size": int(raw.get("size") or 0), "owner": owner, "parent_ids": list(raw.get("parents") or []),
        "drive_id": str(raw.get("driveId") or ""), "web_view_link": str(raw.get("webViewLink") or ""),
        "thumbnail_link": str(raw.get("thumbnailLink") or ""), "is_folder": raw.get("mimeType") == FOLDER,
    }


async def get_file(ctx, account_doc, file_id: str) -> dict:
    out = await dc.request(ctx, account_doc, "GET", f"{dc.DRIVE_API}/files/{file_id}",
                           params={"fields": dc.FILE_FIELDS, "supportsAllDrives": "true"})
    if not out.get("ok"):
        return out
    if not isinstance(out.get("data"), dict):
        return dc.fail(dc.RESPONSE_UNEXPECTED)
    return {"ok": True, "file": to_file(out["data"]), "raw": out["data"]}


def _type_clause(kind: str) -> str:
    kind = (kind or "").strip().lower()
    if not kind:
        return ""
    if kind in TYPE_MIMES:
        return "(" + " or ".join(f"mimeType = '{m}'" for m in TYPE_MIMES[kind]) + ")"
    if kind == "image":
        return "mimeType contains 'image/'"
    if kind == "office":
        return "(mimeType contains 'officedocument' or mimeType contains 'msword' or mimeType contains 'ms-excel' or mimeType contains 'ms-powerpoint')"
    return ""


async def search(ctx, account_doc, *, query: str = "", kind: str = "", source: str = "all",
                 modified_after: str = "", limit: int = 25, page_token: str = "") -> dict:
    clauses = ["trashed = false"]
    q = (query or "").strip()
    if q:
        safe = dc.escape_query(q)
        clauses.append(f"(name contains '{safe}' or fullText contains '{safe}')")
    type_q = _type_clause(kind)
    if kind and not type_q:
        return dc.fail(dc.VALIDATION_FAILED, "Unknown file type filter.")
    if type_q:
        clauses.append(type_q)
    if modified_after:
        date = modified_after.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return dc.fail(dc.VALIDATION_FAILED, "modified_after must be YYYY-MM-DD.")
        clauses.append(f"modifiedTime > '{date}T00:00:00Z'")
    params = {"q": " and ".join(clauses), "fields": f"nextPageToken,files({dc.FILE_FIELDS})",
              "pageSize": max(1, min(100, limit)), "spaces": "drive",
              "corpora": "user", "includeItemsFromAllDrives": "true", "supportsAllDrives": "true"}
    if source == "my_drive":
        params["corpora"] = "user"
    elif source == "shared_drives":
        params["corpora"] = "allDrives"
    elif source != "all":
        return dc.fail(dc.VALIDATION_FAILED, "source must be all, my_drive, or shared_drives.")
    if page_token:
        params["pageToken"] = page_token
    out = await dc.request(ctx, account_doc, "GET", f"{dc.DRIVE_API}/files", params=params)
    if not out.get("ok"):
        return out
    body = out.get("data")
    if not isinstance(body, dict) or not isinstance(body.get("files", []), list):
        return dc.fail(dc.RESPONSE_UNEXPECTED)
    return {"ok": True, "files": [to_file(x) for x in body.get("files", []) if isinstance(x, dict)],
            "next_page_token": str(body.get("nextPageToken") or "")}


async def browse(ctx, account_doc, *, folder: str = "root", drive_id: str = "",
                 limit: int = 50, page_token: str = "") -> dict:
    params = {"q": f"'{dc.escape_query(folder or 'root')}' in parents and trashed = false",
              "fields": f"nextPageToken,files({dc.FILE_FIELDS})", "pageSize": max(1, min(100, limit)),
              "orderBy": "folder,name_natural", "spaces": "drive", "supportsAllDrives": "true",
              "includeItemsFromAllDrives": "true"}
    if drive_id:
        params.update({"corpora": "drive", "driveId": drive_id})
    if page_token:
        params["pageToken"] = page_token
    out = await dc.request(ctx, account_doc, "GET", f"{dc.DRIVE_API}/files", params=params)
    if not out.get("ok"):
        return out
    body = out.get("data")
    if not isinstance(body, dict):
        return dc.fail(dc.RESPONSE_UNEXPECTED)
    return {"ok": True, "files": [to_file(x) for x in body.get("files", []) if isinstance(x, dict)],
            "next_page_token": str(body.get("nextPageToken") or "")}


async def shared_drives(ctx, account_doc, *, query: str = "", limit: int = 50,
                        page_token: str = "") -> dict:
    params = {"pageSize": max(1, min(100, limit)), "fields": "nextPageToken,drives(id,name,createdTime)"}
    if query:
        params["q"] = f"name contains '{dc.escape_query(query)}'"
    if page_token:
        params["pageToken"] = page_token
    out = await dc.request(ctx, account_doc, "GET", f"{dc.DRIVE_API}/drives", params=params)
    if not out.get("ok"):
        return out
    body = out.get("data")
    if not isinstance(body, dict):
        return dc.fail(dc.RESPONSE_UNEXPECTED)
    rows = [{"id": str(x.get("id") or ""), "title": str(x.get("name") or "Shared drive"),
             "drive_id": str(x.get("id") or ""), "created_time": str(x.get("createdTime") or "")}
            for x in body.get("drives", []) if isinstance(x, dict)]
    return {"ok": True, "drives": rows, "next_page_token": str(body.get("nextPageToken") or "")}


async def sheet_metadata(ctx, account_doc, file_id: str) -> dict:
    out = await dc.request(ctx, account_doc, "GET", f"{dc.SHEETS_API}/{file_id}",
                           params={"fields": "properties(title),sheets(properties(sheetId,title,index,gridProperties))"})
    if not out.get("ok"):
        return out
    body = out.get("data")
    if not isinstance(body, dict):
        return dc.fail(dc.RESPONSE_UNEXPECTED)
    worksheets = [str(x.get("properties", {}).get("title") or "") for x in body.get("sheets", [])
                  if isinstance(x, dict) and isinstance(x.get("properties"), dict)]
    return {"ok": True, "worksheets": worksheets}


async def read_sheet_range(ctx, account_doc, file_id: str, worksheet: str, a1_range: str,
                           max_cells: int) -> dict:
    if not worksheet.strip() or not re.fullmatch(r"[A-Za-z]+\d+(?::[A-Za-z]+\d+)?", a1_range.strip()):
        return dc.fail(dc.VALIDATION_FAILED, "Choose a worksheet and use an A1 range such as A1:H100.")
    url = f"{dc.SHEETS_API}/{file_id}/values/{dc.encoded_a1(worksheet.strip(), a1_range.strip())}"
    out = await dc.request(ctx, account_doc, "GET", url, params={"majorDimension": "ROWS"})
    if not out.get("ok"):
        return out
    body = out.get("data")
    if not isinstance(body, dict):
        return dc.fail(dc.RESPONSE_UNEXPECTED)
    values = body.get("values") or []
    if not isinstance(values, list):
        return dc.fail(dc.RESPONSE_UNEXPECTED)
    remaining = max(1, min(5000, max_cells))
    clipped: list[list] = []
    trimmed = False
    for row in values:
        row = list(row) if isinstance(row, list) else [row]
        if remaining <= 0:
            trimmed = True
            break
        if len(row) > remaining:
            clipped.append(row[:remaining]); remaining = 0; trimmed = True
        else:
            clipped.append(row); remaining -= len(row)
    cols = max((len(r) for r in clipped), default=0)
    return {"ok": True, "values": clipped, "rows": len(clipped), "columns": cols,
            "cells": sum(len(r) for r in clipped), "trimmed": trimmed,
            "a1_range": str(body.get("range") or f"{worksheet}!{a1_range}")}


async def read_content(ctx, account_doc, file_id: str, max_characters: int) -> dict:
    meta = await get_file(ctx, account_doc, file_id)
    if not meta.get("ok"):
        return meta
    item = meta["file"]
    mime = item["mime_type"]
    if mime == GSHEET:
        sheets = await sheet_metadata(ctx, account_doc, file_id)
        if not sheets.get("ok"):
            return sheets
        return {"ok": True, "file": item, "content": "", "export_format": "sheet-range-required",
                "truncated": False, "worksheets": sheets["worksheets"], "preview_supported": True}
    if mime == GDOC:
        url = f"{dc.DRIVE_API}/files/{file_id}/export"; params = {"mimeType": "text/plain"}; fmt = "text/plain"
    elif mime == GSLIDES:
        url = f"{dc.DRIVE_API}/files/{file_id}/export"; params = {"mimeType": "text/plain"}; fmt = "text/plain"
    elif mime.startswith("text/") or mime in {"application/json", "application/xml"}:
        url = f"{dc.DRIVE_API}/files/{file_id}"; params = {"alt": "media", "supportsAllDrives": "true"}; fmt = mime
    else:
        return dc.fail(dc.UNSUPPORTED_PREVIEW, "Preview is not available for this file type yet. Open it in Google Drive instead.")
    out = await dc.request(ctx, account_doc, "GET", url, params=params)
    if not out.get("ok"):
        return out
    raw = out["response"].body
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    elif isinstance(raw, str):
        text = raw
    else:
        text = str(raw)
    limit = max(200, min(100000, max_characters))
    return {"ok": True, "file": item, "content": text[:limit], "export_format": fmt,
            "truncated": len(text) > limit, "worksheets": [], "preview_supported": True}
