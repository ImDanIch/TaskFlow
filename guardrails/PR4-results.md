# Завершення ПР4: онтологія та guardrails

Дата перевірки: 10.11.2026.

## Онтологія

Використано наявні `ontology/definitions.json` і read-only валідатор. Типи сутностей: `concept`, `component`, `decision`, `glossary`. Типи зв'язків: `uses`, `depends_on`, `implements`, `related_to`.

Переглянуто наявні нотатки TaskFlow-KB: `Concepts/TaskFlow Architecture.md` використовує FastAPI, Pydantic, SQLAlchemy, SQLite і реалізує REST API; `Components/FastAPI.md` використовує Pydantic; `Components/SQLAlchemy.md` використовує SQLite; `Decisions/Database Design.md` залежить від SQLite і SQLAlchemy. Wikilinks у тексті інтерпретуються як `related_to`. Формат прикладу наведено в `ontology/README.md`. Нотатки не змінювалися.

Команда `.venv/Scripts/python.exe -m ontology.validator C:/Users/user/TaskFlow-KB` завершилася з кодом **0**:

```text
WARNING: README.md: skipped non-entity note
WARNING: TaskFlow MOC.md: skipped non-entity note
WARNING: Concepts/Git Ingestion Verification.md: skipped non-entity note
WARNING: Concepts/PR3 Ingestion Test.md: skipped non-entity note
Entities: 12; relationships: 31; errors: 0
```

## Дев'ять сценаріїв vault / PreToolUse

`tests/test_guardrails.py::test_hook_nine_scenarios` виконує справжній адаптер окремим subprocess зі stdin JSON і тимчасовим `TASKFLOW_KB_PATH`. Наявні нотатки створюються лише у pytest `tmp_path`; перевіряється незмінність їхніх байтів. Це перевірка процесу адаптера, а не доказ завантаження hook конкретною сесією Codex.

| № | Інструмент / шлях | Результат |
|---|---|---|
| 1 | `get_note`, `Existing.md` | allow |
| 2 | `ingest_note`, новий `New.md` | allow |
| 3 | `get_note`, `Nested/Existing.md` | allow |
| 4 | `ingest_note`, наявний `Existing.md` | warn |
| 5 | `ingest_note`, наявний `Nested/Existing.md` | warn |
| 6 | `ingest_note`, наявний `Decision.md` | warn |
| 7 | `get_note`, `../outside.md` | block |
| 8 | `get_note`, `.env` | block |
| 9 | `ingest_note`, `.git/Note.md` | block |

Для `allow` немає заборони, для `warn` повертається `additionalContext` з WARNING, для `block` — `permissionDecision: deny`. У цих дев'яти сценаріях операції MCP не запускаються.

## Правила для коду

Додано `CodePolicyEvaluator` і `code_policies.json` зі спільними перевірками шляхів. Матриця `test_code_policy_matrix` містить 13 сценаріїв на тимчасовому проєкті: 3 allow (читання Python і README, новий тест), 3 warn (зміна наявного Python, README і тесту), 7 block (видалення, вихід за корінь, `.env`, `.git`, `.codex`, БД, виконання). Перевіряється відсутність файлових змін. Це evaluator; shell-команди й редагування коду автоматично ним не перехоплюються.

## Реальне блокування перед MCP

У поточній сесії викликано `mcp__taskflow_kb__get_note` з аргументом `note_path: ../TaskFlow-PR4-isolated-nonexistent/Blocked.md`. Це неіснуючий тестовий шлях; реальні секретні файли не запитувалися. Інструментальна система повернула:

```text
Tool call blocked by PreToolUse hook: Invalid or ambiguous path.. Tool: mcp__taskflow_kb__get_note
```

Це відмова **PreToolUse до виконання MCP**, а не помилка файлового читання сервера. Конфігурацію `.codex/hooks.json` і адаптер не змінювали. Поточний hook обмежений MCP TaskFlow-KB та блокує також bulk `search_notes`; попередні успішні перевірки пошуку в документації описують роботу сервера на іншому етапі.

## Тести та межі

Команда `.venv/Scripts/python.exe -m pytest -q`, код завершення **0**:

```text
194 passed, 1 warning in 45.46s
```

Попередження: `StarletteDeprecationWarning` про інтеграцію HTTPX із TestClient. Python 3.13.5 доступний поза пісочницею; тести й валідатор запущено з дозволом на такий запуск після помилки доступу всередині пісочниці. Тести використовують тимчасові SQLite-бази, vault і локальні bare Git remote; робоча БД і vault не змінювалися.

`warn` не є інтерактивним погодженням. Hook не є ОС-пісочницею і не захищає довільні інструменти. Секрети в довільному тексті не розпізнаються цим path evaluator. Історичні результати 147/150/172 тестів та 9 сутностей не є результатами цього запуску.
