# Scenario Tests (PST) — Google Drive Connector

Метод: `Docs/session-notes/SCENARIO_TESTING_STANDARD.md`.

---

## Прогон 2026-08-19

**Существующее покрытие до PST:** 31 тест в 5 файлах. Хорошее покрытие
account-резолюции, token-refresh и HTTP-уровня (`drive_files.py`)
напрямую. Аудит по точному имени `@chat.function` нашёл **8 функций,
никогда не вызывавшихся на уровне `handlers.py`** (даже если их
внутренние `drive_files.py`-хелперы уже тестировались косвенно):

`browse_folder`, `check_access`, `get_file`, `list_pinned_files`,
`list_shared_drives`, `read_file`, `search_files`, `switch_account`.

Также при осмотре директории приложения был найден файл
`client_secret_*.json` с настоящим Google OAuth client secret. Проверка
показала: файл явно в `.gitignore` (`client_secret_*.json`), НЕ отслеживается
git (`git ls-files` не находит его) — это осознанно исключённый
локальный dev-артефакт, не утечка. Зафиксировано здесь для полноты
пост-аудита, действий не требуется.

**Новый файл:** `tests/test_pst_scenarios.py` — 13 сценариев на уровне
`@chat.function`, закрывающих все 8 пробелов: happy path для каждого,
error (unsupported preview type в `read_file`), blocked (нет
подключённого аккаунта / имя аккаунта не найдено), adversarial (неизвестный
`file_type` в `search_files` не делает ни одного HTTP-вызова), recovery
(истёкший токен прозрачно обновляется внутри `get_file`), и полный
пользовательский сценарий pin → list_pinned_files → unpin →
list_pinned_files, плюс switch_account, реально проверяющий переключение
`is_active` между двумя аккаунтами.

### Результат

44/44 тестов зелёные (31 существующих + 13 новых). **Реальных багов в
приложении не найдено.**

---
