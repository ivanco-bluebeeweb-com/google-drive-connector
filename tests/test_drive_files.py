import pytest

import drive_client as dc
import drive_files as df


@pytest.mark.asyncio
async def test_search_is_server_side_and_includes_shared_items(ctx, account):
    ctx.http.push({"files": [{"id": "f1", "name": "KSR Brief", "mimeType": df.GDOC}],
                   "nextPageToken": "next"})
    out = await df.search(ctx, account, query="KSR", kind="document", source="all", limit=25)
    assert out["ok"] is True
    assert out["files"][0]["title"] == "KSR Brief"
    assert out["next_page_token"] == "next"
    params = ctx.http.calls[0]["params"]
    assert "fullText contains 'KSR'" in params["q"]
    assert params["includeItemsFromAllDrives"] == "true"


@pytest.mark.asyncio
async def test_search_escapes_google_query_literals(ctx, account):
    ctx.http.push({"files": []})
    await df.search(ctx, account, query="Vlad's \\ brief")
    assert "Vlad\\'s \\\\ brief" in ctx.http.calls[0]["params"]["q"]


@pytest.mark.asyncio
async def test_search_rejects_unknown_source_without_http(ctx, account):
    out = await df.search(ctx, account, source="somewhere")
    assert out["code"] == dc.VALIDATION_FAILED
    assert ctx.http.calls == []


@pytest.mark.asyncio
async def test_browse_reads_only_one_folder_level(ctx, account):
    ctx.http.push({"files": [{"id": "folder", "name": "Clients", "mimeType": df.FOLDER}]})
    out = await df.browse(ctx, account, folder="root")
    assert out["files"][0]["is_folder"] is True
    assert "'root' in parents" in ctx.http.calls[0]["params"]["q"]


@pytest.mark.asyncio
async def test_shared_drives_empty_is_success(ctx, account):
    ctx.http.push({"drives": []})
    out = await df.shared_drives(ctx, account)
    assert out == {"ok": True, "drives": [], "next_page_token": ""}


@pytest.mark.asyncio
async def test_sheet_requires_exact_a1_range(ctx, account):
    out = await df.read_sheet_range(ctx, account, "sheet", "Leads", "A:H", 100)
    assert out["code"] == dc.VALIDATION_FAILED
    assert ctx.http.calls == []


@pytest.mark.asyncio
async def test_sheet_range_is_encoded_and_clipped(ctx, account):
    ctx.http.push({"range": "'Lead Data'!A1:C2", "values": [[1, 2, 3], [4, 5, 6]]})
    out = await df.read_sheet_range(ctx, account, "sheet", "Lead Data", "A1:C2", 4)
    assert out["values"] == [[1, 2, 3], [4]]
    assert out["trimmed"] is True
    assert out["cells"] == 4
    assert "%27Lead%20Data%27%21A1%3AC2" in ctx.http.calls[0]["url"]


@pytest.mark.asyncio
async def test_google_doc_preview_is_bounded(ctx, account):
    ctx.http.push({"id": "doc", "name": "Brief", "mimeType": df.GDOC})
    ctx.http.push("x" * 500)
    out = await df.read_content(ctx, account, "doc", 200)
    assert len(out["content"]) == 200
    assert out["truncated"] is True


@pytest.mark.asyncio
async def test_binary_file_is_not_downloaded_for_preview(ctx, account):
    ctx.http.push({"id": "pdf", "name": "Contract", "mimeType": "application/pdf"})
    out = await df.read_content(ctx, account, "pdf", 1000)
    assert out["code"] == dc.UNSUPPORTED_PREVIEW
    assert len(ctx.http.calls) == 1


@pytest.mark.asyncio
async def test_401_refreshes_once_and_retries(ctx, account):
    ctx.http.push({"error": "expired"}, status=401)
    ctx.http.push({"access_token": "fresh", "expires_in": 3600})
    ctx.http.push({"files": []})
    out = await df.search(ctx, account)
    assert out["ok"] is True
    assert [c["method"] for c in ctx.http.calls] == ["GET", "POST", "GET"]
    assert ctx.http.calls[-1]["headers"]["Authorization"] == "Bearer fresh"


@pytest.mark.asyncio
async def test_errors_are_structured(ctx, account):
    ctx.http.push({"error": {"message": "quota"}}, status=429)
    out = await df.search(ctx, account)
    assert out["code"] == "RATE_LIMITED"
    assert out["retryable"] is True
