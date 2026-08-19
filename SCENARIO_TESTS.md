# Scenario Tests (PST) — Google Drive Connector

Метод: `Docs/session-notes/SCENARIO_TESTING_STANDARD.md`.

---

## Прогон 2026-08-20 — Часть D (Deploy Verification / Idempotency / Security-SSRF / Regression grep)

**D1 (Deploy Verification):** не применялось — код приложения не менялся (только тесты), деплой не требуется.

**D2 (Idempotency):** добавлены 2 теста. `disconnect_account` уже был fail-closed (`accounts.disconnect` делает `store.get` перед удалением) — тест подтверждает: второй вызов подряд на уже отключённом аккаунте получает чистую ошибку, не падает. `pin_file` уже проверяет наличие существующей pin-записи (по email+file_id) перед созданием новой — тест подтверждает: повторный pin того же файла не создаёт дубликат записи.

**D3 (Security/SSRF):** ни одна `@chat.function` не принимает пользовательский URL для fetch — все Drive API вызовы строятся из фиксированного базового URL плюс id файла/диска, а `refresh_access_token` всегда обращается к константе `TOKEN_URL` (`oauth2.googleapis.com`). Добавлен 1 regression-тест, фиксирующий эту константу как trip-wire.

**D4 (Regression grep):** нет новых находок специфичных для этого приложения сверх `Docs/known-bug-patterns.md`.

**Итог:** 47/47 тестов зелёные (было 39). Реальных багов не найдено.

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
