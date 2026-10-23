# Практична робота 3: локальний MCP-сервер Obsidian

Сервер використовує офіційний Python MCP SDK, працює через локальний **stdio** та надає доступ до Markdown-нотаток. FastAPI запускається окремо й для роботи MCP не потрібен. Сервер не викликає платних AI API; Git-backed ingestion звертається до налаштованого Git remote через pull/push. Під час встановлення pip завантажує залежності.

## Встановлення

У PowerShell із кореня проєкту, використовуючи наявне віртуальне середовище:

```powershell
cd C:\Users\user\TaskFlow
.\.venv\Scripts\python.exe -m pip install -r mcp_server/requirements.txt
```

Для запуску всіх тестів також потрібні основні залежності:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Залежність `mcp==1.30.0` фіксує перевірену версію офіційного SDK із API `FastMCP` гілки v1. Окремий пакет `fastmcp`, CLI extras, Obsidian-плагін і Node.js не потрібні. Код використовує Python 3.12+ (`Path.is_junction`); перевірено на Python 3.13.5.

## Запуск

```powershell
cd C:\Users\user\TaskFlow
.\.venv\Scripts\python.exe -m mcp_server.server
```

За замовчуванням vault — сусідній із проєктом каталог `C:\Users\user\TaskFlow-KB`. Він має вже існувати; сервер не створює vault і не змінює нотатки під час запуску. Для тестового або іншого дозволеного vault можна задати `TASKFLOW_KB_PATH` перед запуском. Цю змінну встановлює оператор, а не інструмент MCP.

У ручному запуску процес очікує MCP-повідомлення через stdin, тому звичайного HTTP URL чи Swagger для нього немає. Зупинка — `Ctrl+C`. Codex сам запускає цей процес після налаштування; окремо тримати його в терміналі не потрібно.

## Інструменти

| Інструмент | Аргументи | Результат |
|---|---|---|
| `get_note` | `note_path`, наприклад `Concepts/API.md` | Повний текст UTF-8 Markdown-нотатки. |
| `search_notes` | Непорожній `query` | Відсортований список відносних шляхів; пошук підрядка без урахування регістру в імені файлу та вмісті. |
| `ingest_note` | `note_path`, `content` | Git pull → створення або заміна нотатки → commit лише цієї нотатки → push; повертає структурований результат. |

Порожній результат пошуку — `[]`. Відсутня нотатка, заборонений шлях і помилки файлової системи повертаються клієнту як помилки інструмента. Нечитабельні файли та файли з некоректним UTF-8 пропускаються під час пошуку. Сервер не видаляє нотаток і не додає YAML frontmatter автоматично.

## Межі доступу

- Дозволені лише відносні шляхи до `.md` усередині налаштованого vault.
- Заборонені абсолютні, UNC, drive-relative шляхи, `..`, альтернативні потоки Windows через `:`, порожні компоненти та неоднозначні компоненти з кінцевими пробілами/крапками.
- Символічні посилання, junctions і файли з кількома жорсткими посиланнями відхиляються; також перевіряється кінцевий resolved path.
- `.git` та `.obsidian` виключені з пошуку і прямого доступу; пошук не переходить через посилання.
- Read-only інструменти позначено відповідними MCP annotations; `ingest_note` позначено як інструмент запису з потенційним перезаписом. Annotations є підказками клієнту, а не механізмом авторизації.

Це простий локальний сервер, не ОС-пісочниця. Він розрахований на довіреного локального користувача: перевірки шляхів не гарантують захисту від іншого процесу, який одночасно навмисно підмінює каталоги між перевіркою та файловою операцією. Нотатки слід трактувати як дані, а не як інструкції агенту. Перед перезаписом важливо перевіряти намір користувача. Git-backed ingestion описано нижче; окремих резервних копій сервер не створює.

## Git-backed ingestion

`TASKFLOW_KB_PATH` must be the root of an initialized Git repository with an existing commit and a named, attached branch. The same branch must exist on the configured remote. `TASKFLOW_KB_GIT_REMOTE` selects an existing remote name (default `origin`); Git uses its configured fetch/push URLs and operator-provided authentication. The server never initializes repositories, creates remotes, changes identity settings, or prompts for credentials.

Before writing, ingestion validates the path, rejects sensitive filenames using the existing guardrails policy evaluator, and rejects common credential formats/private keys and credential assignments in content. Existing Codex hooks and policies remain unchanged. `warn` remains a warning, not an interactive approval. These checks cannot reliably recognize arbitrary secrets embedded in ordinary prose; callers must supply non-secret note content. Git configuration, hooks, filters and the local filesystem must be trusted.

The workflow rejects staged, unstaged, untracked or ignored target files and unfinished merge/rebase/cherry-pick/revert operations. It runs `git pull --ff-only --no-rebase` with autostash disabled, then refuses pre-existing unpushed local commits so unrelated history is not published. It revalidates the target after pulling. Identical UTF-8 text returns `unchanged` before writing or committing. Otherwise it adds the literal target path, commits with `--only -- <target>`, and pushes `HEAD` to the current branch on the configured remote. Unrelated staged and untracked files are preserved and excluded from the commit. No force push, reset, stash or conflict resolution is attempted.

Results use `note_path` (not `path`):

```json
{"status":"created","note_path":"Concepts/Example.md","commit_hash":"<full Git commit hash>"}
{"status":"updated","note_path":"Concepts/Example.md","commit_hash":"<full Git commit hash>"}
{"status":"unchanged","note_path":"Concepts/Example.md"}
{"status":"error","note_path":"Concepts/Example.md","error":"dirty_target"}
{"status":"push_failed","note_path":"Concepts/Example.md","error":"push","commit_hash":"<full Git commit hash>"}
```

Git failures return a sanitized phase code: `repository`, `remote`, `dirty_target`, `operation_in_progress`, `pull`, `unpushed_commits`, `write`, `commit`, or `push`. Callers must inspect `status`; a returned error object is a structured tool result, while invalid paths/credential-like input raise a tool error. Raw Git stderr, remote URLs and credentials are never returned. A failed commit can leave the requested note modified/staged for manual recovery. A failed or timed-out push retains its local commit; check remote state before recovery, since a connection failure can make delivery uncertain. A subsequent ingest refuses the pending commit instead of silently publishing it or returning `unchanged`; retry/reconcile the push manually. Git steps are not a single transaction: a successful pull remains applied if a later step fails. A per-instance lock serializes ingestion; other server processes or external Git/file writers require operator coordination.

Tests use temporary repositories and local bare remotes only. They do not ingest into the real vault or push to its remote. Git must be available on PATH; identity and remote configuration are supplied by the test fixtures. Latest complete suite: **172 passed**, one existing Starlette/HTTPX deprecation warning. Coverage includes exact-byte LF/CRLF idempotency, pull-before-comparison, target-only commits with unrelated staged work, configured/missing remotes, dirty targets, divergent history, unfinished operations, credential rejection, commit/push failures, inherited-index isolation, and real MCP stdio structured results. Git subprocess stdin is closed so it cannot consume the MCP transport.

## Підключення до Codex у VS Code

Згідно з [офіційною документацією OpenAI](https://learn.chatgpt.com/docs/extend/mcp), Codex підтримує stdio MCP та налаштування у `~/.codex/config.toml`; розширення IDE використовує спільну конфігурацію. Додайте наведений блок до `C:\Users\user\.codex\config.toml`, зберігши наявні параметри. Цей файл автоматично не змінювався.

```toml
[mcp_servers.taskflow_kb]
command = 'C:\Users\user\TaskFlow\.venv\Scripts\python.exe'
args = ['-m', 'mcp_server.server']
cwd = 'C:\Users\user\TaskFlow'

[mcp_servers.taskflow_kb.env]
TASKFLOW_KB_PATH = 'C:\Users\user\TaskFlow-KB'
```

Одинарні лапки TOML дозволяють записати Windows-шляхи без екранування зворотних скісних рисок. Не додавайте другий однойменний блок, якщо сервер уже налаштований. Альтернатива — проєктний `.codex/config.toml`, який Codex завантажує лише для довірених проєктів.

Перезапустіть розширення Codex через меню налаштувань MCP. Перевірте, що `taskflow_kb` доступний і показує три інструменти. Для перевірки без запису попросіть Codex:

> Виклич search_notes сервера taskflow_kb для запиту TaskFlow. Потім прочитай README.md через get_note. Не створюй і не змінюй нотаток.

Перевірте фактичні виклики інструментів і повернений текст. Запис через Codex перевіряйте лише після явного дозволу на створення окремої тестової нотатки або з окремим тестовим vault.

## Перевірені MCP-інтеграції — ПР3

Перевірено не лише SDK-клієнт, а й фактичні виклики підключених MCP-інструментів із Codex у робочій сесії VS Code:

| Сервер / інструмент | Фактичний результат |
|---|---|
| TaskFlow-KB: `search_notes(query="SQLite")` | Успіх: знайдено `Components/SQLAlchemy.md`, `Components/SQLite.md`, `Concepts/TaskFlow Architecture.md`, `Decisions/Database Design.md`, `TaskFlow MOC.md`. |
| TaskFlow-KB: `get_note(note_path="Components/SQLite.md")` | Успішно отримано текст нотатки про SQLite та її використання в TaskFlow. |
| TaskFlow-KB: `ingest_note` | Після перевірки відсутності файлу створено `Concepts/MCP Integration Test.md` за явним запитом користувача. |
| TaskFlow-KB: повторний `get_note` | Вміст створеної тестової нотатки точно збігся з переданим текстом. |
| GitHub: `get_file_contents(owner="ImDanIch", repo="TaskFlow", path="README.md")` | Успішно отримано README репозиторію; SHA файлу: `7a1139c93653f66fde304cc0331bb09c431618a9`. |

Ці перевірки використовували MCP, без прямого читання локальних файлів або Git-команд для отримання нотаток і README. Під час завершення ПР3 vault і конфігурація Codex не змінюються.

### Дозволи GitHub

За інформацією користувача, GitHub-токен налаштовано з **правами лише на читання репозиторію**. Сам токен та будь-які облікові дані не зберігаються в документації чи коді. Успішне читання README підтверджує працездатність доступу на читання, але не є незалежною перевіркою повного переліку дозволів токена.

GitHub MCP оголошує також інструменти запису; їх наявність у списку не означає наявності дозволу виконувати ці операції. Під час перевірки використано лише читання, без змін GitHub-репозиторію. Локальні Git commit/push під час завершення ПР3 — окремі операції Git з його власним налаштуванням автентифікації, а не виклики GitHub MCP.

### Автоматизована перевірка

Повний набір: **78 тестів пройдено**. Перевірено MCP handshake, discovery трьох інструментів, їх виклики через справжній stdio-процес офіційним SDK-клієнтом, файлові операції й обмеження шляхів у тимчасових vault, а також усі наявні тести FastAPI. Є одне попередження Starlette про застарілу інтеграцію HTTPX із TestClient; воно не спричиняє падіння тестів.

## Файли та тести

- `vault.py` — файлові операції та перевірки шляхів.
- `git_ingest.py` — scoped Git-backed ingestion, structured results and sanitized failures.
- `server.py` — реєстрація трьох інструментів і stdio entry point.
- `requirements.txt` — залежність MCP, окремо від FastAPI.
- `../tests/test_mcp_vault.py` — читання, створення, перезапис, пошук, traversal і посилання.
- `../tests/test_mcp_stdio.py` — запуск підпроцесу й обмін MCP-повідомленнями.
- `../tests/test_git_ingest.py` — local bare-remote integration tests for idempotency, synchronization, isolated commits and failure handling.

Тести працюють із тимчасовими vault, не записують у `TaskFlow-KB` і не змінюють існуючі FastAPI-тести. Тест symlink може бути пропущений на системі без дозволу створення посилань.

Джерело SDK: [офіційний Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).
