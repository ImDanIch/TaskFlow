# Coder: фактичний результат

Роль: окремий subagent `/root/coder`, запущений після Planner.

Вхідний handoff: необов'язкова пагінація `GET /tasks`, `offset >= 0` (default 0), `limit` optional 1..100 (default None); зберегти фільтри, порядок id та повний список без параметрів. Allowlist: `app/tasks.py`, `tests/test_tasks.py`; окремо дозволено цей звіт.

## Реалізація й обґрунтування

У `app/tasks.py` додано FastAPI `Query`-обмеження параметрів. SQLAlchemy offset застосовується після status/priority, limit — лише якщо задано. `order_by(Task.id)` збережено. Необов'язковий limit зберігає попередній контракт. Нових залежностей, змін моделі чи БД немає.

Додано 18 випадків тестування: повний список, limit, offset, комбінація, допустимі межі 1/100, порожній/вичерпаний список, недопустимі та дробові параметри, обидва фільтри перед пагінацією. Неалфавітний порядок назв у fixture перевіряє саме порядок id.

## Реальні перевірки

- Перед читанням двох цільових файлів `CodePolicyEvaluator`: `allow/read_source`.
- Перед редагуванням: `warn/update_source`; виконано diff review та релевантні тести.
- Команда `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/test_tasks.py -q` поза sandbox: exit **0**, **53 passed, 1 warning in 6.79s**.
- Попередження: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` Залежності не змінювались.
- `git diff --check`: без помилок whitespace; Git повідомив лише очікувану конвертацію LF → CRLF.
- `git diff -- app/tasks.py tests/test_tasks.py` переглянуто: лише пагінація та її тести.
- Policy перед записом цього звіту: `allow/create_source`.
- MCP Coder не викликав: архітектурний контекст і контракт уже передані Planner. KB не змінював. Live hook activation не перевіряв.

## Handoff Coder → Reviewer

Перевірити код і нові тести, сумісність GET без параметрів, 422 для неправильних значень, порядок filters → offset → limit, незмінний id order. Незалежно запустити tasks tests і повний suite разом із батьківськими orchestration tests; перевірити Guardrails та відсутність сторонніх змін. Ризик: offset pagination не гарантує snapshot consistency при паралельних змінах. Coder не робив commit/push.

## Доопрацювання після Reviewer

Отриманий реальний finding P2: `offset=9223372036854775808` спричиняє SQLite integer overflow та HTTP 500. Початковий контракт визначав лише нижню межу; Python допускає довільно великі integers, SQLite bind — signed 64-bit.

Coder обмежив Query верхньою межею `2**63 - 1` (9223372036854775807). Надмірні значення тепер відхиляються валідацією з 422 до SQL. Додано три regression-випадки: максимальний допустимий offset повертає 200/[]; `2**63` і `10**100` повертають 422.

Перед читанням `app/tasks.py`, `tests/test_tasks.py`, цього звіту evaluator повернув `allow/read_source`; перед записом кожного — `warn/update_source`. Diff переглянуто, `git diff --check` без whitespace-помилок (наявне повідомлення LF → CRLF).

Повторна команда `.venv/Scripts/python.exe -X utf8 -B -m pytest tests/test_tasks.py -q`: exit **0**, **56 passed, 1 warning in 4.87s**. Попередження Starlette/HTTPX те саме. Історичні результати вище збережено.

Повторний handoff Coder → Reviewer: перевірити верхню межу offset, regression-випадки та повний suite; P2 передано як виправлений, остаточне прийняття належить Reviewer. Commit/push не виконував.
