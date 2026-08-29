# Google Drive Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на `POST_CONNECT_EXPERIENCE.md` этого приложения.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(account) + `ui.Divider` + `ui.Tree`(folder hierarchy — реальная вложенная структура Drive) + `ui.Button`("App settings") | `Tree` — единственный примитив, точно отражающий вложенную структуру папок Google Drive. |
| Folder/File Browser (center, `center_overlay=True`) | `ui.Stats`(Files/Folders/Storage used) + `ui.DataTable`(icon via `ui.Image` в ячейке по mime-type, name, owner, modified, size; sortable, selectable=True, bulk_actions=[Move, Delete, Share]) | `DataTable` с bulk_actions — стандартный способ работать со списком файлов, включая массовые операции. |
| File Detail | Back-button + `ui.KeyValue`(owner/modified/size/shared with) + `ui.List`(permissions: person, role) + `ui.Row`(Button "Open in Drive", "Download", "Move", "Rename") | `KeyValue` для метаданных, `List` для списка доступов. |
| Share Dialog | `ui.Dialog`(title="Настроить доступ", content=`ui.Stack`([`ui.Input`(type="email", param_name="email"), `ui.Select`(role, options=[viewer,commenter,editor])]), confirm_label="Поделиться") | Выдача доступа к файлу — значимое действие с явным подтверждением получателя и роли. |
| Delete Confirmation | `ui.Dialog`(title="Удалить файл?", content=`ui.Text`("Файл будет перемещён в корзину Google Drive."), confirm_label="Удалить") | Удаление — потенциально деструктивное действие (даже если через корзину), обязателен `Dialog`. |
| Search Results | `ui.Input`(param_name="query", placeholder="Найти файл или папку...", on_submit=Call) + `ui.DataTable`(результаты: name, path, modified; sortable) | Простой Input с submit + табличные результаты поиска. |
| Recent Activity Feed | `ui.T
... [3 chars elided from this argument for history replay -- the tool received the FULL value] ...
imeline`(events: edited/shared/commented, по времени) | `Timeline` — хронологический журнал активности по файлам, естественная репрезентация. |
| Shared Drives List (если Workspace) | `ui.DataTable`(name, members count, storage used; sortable) | Табличный обзор общих дисков организации. |
| App Settings | `ui.Accordion`([Connections+Disconnect, Default Folder Select, Sync Preferences]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__gdrive_sidebar` рендерит account + `Tree`
   иерархии папок; `auto_action` открывает Folder/File Browser для корневой
   папки ("My Drive").
2. Клик в `Tree` на папку → `ui.Call(folder_id=...)` → Folder/File Browser
   на том же center handler для выбранной папки.
3. File Browser: клик на строку файла → `ui.Call(file_id=...)` → File Detail;
   selectable+bulk_actions на нескольких строках → "Delete" → `Dialog`
   подтверждения → `ui.Call` → `trash_files` → `refresh_panels`.
4. File Detail: "Share" → `Dialog`(email+role) → `ui.Call` → `add_permission`
   → `refresh_panels` (обратимо, но всё равно с явным подтверждением
   получателя, т.к. расшаривает контент вовне).
5. Поиск (сайдбар или верх Browser) → `Input`(on_submit) → Search Results
   на том же center handler.
6. "App settings" (нижняя кнопка сайдбара) → отдельный center handler
   `panels_settings.py`; "Disconnect" — единственное деструктивное действие,
   обёрнуто в `Dialog`.

## 3. Экраны/карточки (конкретно)

- **Screen: Folder/File Browser** — Stats(3) + DataTable(icon/name/owner/modified/size, selectable+bulk_actions).
- **Screen: File Detail** — KeyValue(metadata) + List(permissions) + Row(actions).
- **Screen: Share Dialog** — Dialog(email input + role select).
- **Screen: Search Results** — Input(query) + DataTable(name/path/modified).
- **Screen: Recent Activity** — Timeline(events).
- **Screen: Shared Drives List** — DataTable(name/members/storage).
- **Screen: App Settings** — Accordion(Connections, Default Folder, Sync Preferences).
