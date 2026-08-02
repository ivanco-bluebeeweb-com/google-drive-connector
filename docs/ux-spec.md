# Google Drive Connector — UX Specification

**Status:** approved for MVP design
**Decision date:** 2026-08-02
**Scope:** read-only Google Drive context connector for Imperal / Webbee

## Product intent

Google Drive Connector gives Webbee grounded access to files the connected Google account can already reach. It is not a generic file manager: its primary job is to let a user and Webbee find working context, understand where it lives, and read a selected document safely.

The MVP is read-only. It must never create, edit, move, delete, download in bulk, or change sharing for Drive files.

## UX principles

1. **Access is explicit.** The connector may only read files available to the connected Google account.
2. **Context is opt-in.** General use of Drive files in Webbee answers is disabled until the user explicitly enables it.
3. **Search is global and server-side.** Results must cover the selected account's accessible Drive, not only the rows currently loaded in the UI.
4. **No silent bulk reading.** Opening or asking about a specific file reads that file; the connector does not crawl all documents in the background.
5. **Original source remains one click away.** Every file detail view links to Google Drive.
6. **Multiple accounts stay distinct.** A user can connect personal and work accounts, then select an active account.

## Information architecture

- Connect Google Drive
- Drive Home
  - Search files
  - Browse folders
  - Shared drives
  - Recently changed
  - Pinned files
  - Context permission
- Search results
- Folder browser
- Shared drives
- File details and preview
- Accounts and access

## Screens

### 1. Connect Google Drive

**Shown when:** no account is connected.

**Contents**
- Title: `Connect Google Drive`
- Short explanation: Imperal can search and read only files that the selected Google account can already access.
- Primary action: `Connect Google account`
- After OAuth, show connected account name and email.
- Explain available sources: My Drive, files shared with the account, and Shared drives available to it.

**Flow**
`Open app → Connect Google account → Google OAuth → return to Drive Home`

### 2. Drive Home

**Purpose:** a useful starting point, not a copy of the Google Drive interface.

**Contents**
- Active connected account and connection health.
- Primary entry points:
  - `Search files`
  - `Browse folders`
  - `Shared drives`
- `Recently changed`: 10–20 files ordered by modification time.
- `Pinned`: user-selected files that matter repeatedly to their work with Webbee.
- Quick type filters: Documents, Spreadsheets, Presentations, PDFs, Images.
- Visible `Use Drive as context` switch with a concise explanation.

**Pinned behavior**
- A user may pin or unpin a file from File Details and from list row actions.
- Pins are stored per Imperal user, not written back to Google Drive.
- The Pinned section may be empty; show an honest empty state and point to pinning from file details.

**Context switch behavior**
- Default: **off**.
- When off: Webbee only uses a Drive file after the user explicitly asks about, opens, or references that file.
- When on: Webbee may use metadata and content from files available through the active account as supporting context when relevant.
- The UI must state that enabling the switch does not grant new Google permissions and does not trigger a full background scan.
- The switch is account-specific and must be visible on Drive Home and Accounts & Access.

### 3. Search Results

**Purpose:** locate a file without knowing its folder.

**Contents**
- Search input.
- Filters:
  - source: My Drive / Shared drives / all accessible files;
  - file type: Google Docs, Sheets, Slides, PDF, Office documents, images, folders;
  - modification period;
  - owner, only if safely and reliably provided by Google.
- Paginated result list. Each row shows:
  - file type icon;
  - name;
  - parent path when available;
  - owner or Shared drive label;
  - modification time;
  - size when applicable;
  - `Details` action.

**Flow**
`Drive Home → Search → Results → File Details`

A folder result opens Folder Browser rather than File Details.

### 4. Folder Browser

**Purpose:** discover files through client/project structure.

**Contents**
- Breadcrumbs, for example: `My Drive / Clients / KSR / SEO`.
- Parent-folder navigation.
- Folders first, then files.
- Same compact file metadata as Search Results.
- Account and source context always visible.

**Flow**
`Drive Home → Browse folders → folder → nested folder → File Details`

Do not build a full expandable tree of every Drive folder in MVP.

### 5. Shared Drives

**Purpose:** clearly distinguish organisational/client drives from My Drive.

**Contents**
- Searchable list of Shared drives available to the active Google account.
- Name and minimal metadata.
- Opening a Shared drive starts Folder Browser at its root.

**Empty state**
`No shared drives are available to this account.`

This is informational, not an error.

### 6. File Details and Preview

**Purpose:** the primary grounded-context card.

**Contents**
- Name, type, and visual file icon.
- Clickable parent path.
- Owner or Shared drive.
- Created time, modified time, and size if Google provides it.
- `Open in Google Drive` action.
- `Ask Webbee about this file` action; opens/continues chat with a grounded reference to this exact file.
- `Pin` / `Unpin` action.
- Preview appropriate to format:
  - Google Docs: extracted text;
  - Google Sheets: worksheet selector plus range selector;
  - Google Slides: slide structure and extracted text;
  - PDF, DOCX, XLSX, PPTX, TXT, CSV: extracted readable content or a clear unsupported message;
  - images: thumbnail/metadata and original Drive link in MVP.

#### Google Sheets range selection

The Sheet preview must not silently dump a whole spreadsheet.

**Controls**
- Worksheet selector.
- Explicit A1-notation range input, e.g. `Leads!A1:H100`.
- Default when first opened: a clearly labelled small preview range chosen by the connector, never presented as the entire sheet.
- `Load range` action.

**Validation and states**
- Reject malformed A1 ranges with a clear message.
- Show a practical cell/row limit before loading and explain when a requested range is trimmed.
- Preserve the selected worksheet and range while the file-detail session remains open.

**Flows**
`Any list → File Details → Preview`

`File Details → Ask Webbee about this file → chat with exact-file context`

`File Details → Open in Google Drive`

### 7. Accounts and Access

**Purpose:** make Drive access diagnosable and manageable.

**Contents**
- Connected Google accounts.
- Active-account indication and switching.
- Human-readable permissions summary: search and read files available to that account.
- Last successful access check.
- Per-account `Use Drive as context` switch.
- Actions:
  - `Re-check access`
  - `Switch active account`
  - `Connect another account`
  - `Disconnect`

**Disconnect confirmation**
Explain that Imperal will no longer access Google Drive through this account. It does not delete files or change any Google Drive permission.

## Core user flows

### A. First setup
`Open Drive Connector → Connect Google account → OAuth → Drive Home`

### B. Find a client agreement
`Chat: “Find the KSR agreement” → global Drive search → candidate files → File Details → preview or open in Google Drive`

### C. Locate a file's project folder
`Search result → File Details → parent path → Folder Browser`

### D. Read a bounded spreadsheet section
`Search or browse → spreadsheet File Details → select worksheet → enter range (e.g. Leads!A1:H100) → Load range → Ask Webbee about this file/range`

### E. Make a recurring source easy to reach
`File Details → Pin → Drive Home → Pinned → File Details`

### F. Enable broad contextual help
`Drive Home or Accounts & Access → turn on Use Drive as context → confirm transparent explanation → switch enabled for active account`

### G. A needed file is absent
`Drive Home → Accounts & Access → Re-check access`

If it remains absent, explain only the grounded rule: Imperal can see files already accessible to the connected Google account. The user may need to share the file or folder with that account in Google Drive.

### H. Multiple accounts
`Accounts & Access → Connect another account → OAuth → select active account → Drive Home`

## Chat surface

The connector must support natural-language flows equivalent to the panels:
- connect/list/switch Google accounts;
- search accessible files and folders;
- browse a folder or Shared drive;
- inspect a file;
- read a selected document;
- read a selected Google Sheets worksheet and A1 range;
- pin/unpin/list pinned files;
- show or change the account-specific context switch;
- explain currently available access.

Chat responses must keep file references grounded to a specific Drive file ID and account context. They must not claim that a file was searched, read, or unavailable unless the corresponding Drive API action occurred.

## MVP exclusions

- Create, upload, edit, move, delete, or rename files.
- Change file sharing or permissions.
- Bulk downloading or background crawling of an entire Drive.
- Full semantic/vector indexing of all accessible documents.
- Mandatory image understanding beyond metadata and a thumbnail/link.
- Full Google Drive parity such as comments, revisions, starred items, and offline files.

## Acceptance criteria before implementation is complete

1. A new user can connect and disconnect a Google account through the agreed flow.
2. Search works across all accessible files for the selected account, not only the current UI page.
3. Folder navigation and Shared drives lead to a selected file's details.
4. File Details presents truthful metadata and a link to the original Drive item.
5. Spreadsheet previews require worksheet and explicit A1-range selection; outputs are bounded.
6. Pinning is visible on Drive Home and does not write to Google Drive.
7. Context permission is off by default, per account, explicit, reversible, and does not imply bulk indexing.
8. Missing access has a calm, actionable explanation without invented causes.
9. No mutation endpoint is exposed in the MVP.
