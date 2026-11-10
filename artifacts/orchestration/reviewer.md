# Reviewer: перший незалежний прохід

Роль: окремий subagent `/root/reviewer`. Рішення: **changes_requested**.

## Finding P2

`app/tasks.py:37` дозволяє довільний невід'ємний Python int як offset;
`app/tasks.py:45` передає його SQLite через SQLAlchemy. Запит
`GET /tasks?offset=9223372036854775808` проходить HTTP-валідацію, але
переповнює signed 64-bit SQLite integer і повертає **500 Internal Server Error**.

Доказ: Reviewer реально запустив TestClient з `raise_server_exceptions=False`
та окремою тимчасовою SQLite-базою (patch `database.engine`, `SessionLocal`).
Вивід: `offset 9223372036854775808 status 500 body Internal Server Error`;
exit code 0. Робоча БД не використовувалась.

Мінімальна рекомендація: обмежити offset зверху `2**63-1`, повертати 422
для перевищення, уточнити контракт і додати regression-тест межі/переповнення.
Host погодив цей варіант для Coder rework. Попередній контракт offset>=0
потребує відповідного явного уточнення.

## Фактичні перевірки

- Застосовано Skill `.agents/skills/taskflow-code-review/SKILL.md` без його змін.
- Прочитано Guardrails README та обидва JSON policies.
- Перед цільовими читаннями CodePolicyEvaluator повернув `allow/read_source`
  для planner.md, coder.md, run.json, app/tasks.py, tests/test_tasks.py,
  orchestration/workflow.py, tests/test_orchestration.py, docs/orchestration.md,
  tests/conftest.py. Перед записом цього звіту: `allow/create_source`.
- PolicyEvaluator для `Concepts/TaskFlow Architecture.md` та
  `Decisions/Database Design.md`: `allow/read_note`.
- Обидва реальні MCP `get_note(note_path=...)`: `isError:false`.
  KB підтверджує FastAPI → Pydantic → SQLAlchemy → SQLite і локальну БД;
  нотатки використано як дані. Bulk search та записів KB не було.
- Незалежна повна команда `.venv/Scripts/python.exe -X utf8 -B -m pytest -q`
  поза sandbox: **exit 0; 215 passed, 1 warning in 50.68s**.
- Попередження: `StarletteDeprecationWarning: Using httpx with
  starlette.testclient is deprecated; install httpx2 instead.` Залежності не змінено.
- `git diff --check`: exit 0, лише повідомлення Git LF → CRLF.
- Переглянуто повний diff API й тестів: лише запланована пагінація.
  Перевірено filters → offset → limit, order_by(id), backwards compatibility,
  негативні тести, ізоляцію SQLite у fixture.
- Workflow перевіряє порядок ролей і обов'язкові поля, підтримує rework;
  тести охоплюють неможливий перехід, порожній контекст і заборонені шляхи save.
  run.json на момент читання містив Planner → Coder → Reviewer, active Reviewer.
  Host допише подальші handoff й транскрипт після фактичних результатів.
- Status містить тільки app/tasks.py, tests/test_tasks.py та нові
  orchestration/docs/artifacts/tests файли, а також початкову сторонню `.agents/`.
  Guardrails, hooks, MCP, моделі, схеми й dependencies у diff не змінені.

215 успішних тестів не покривали знайдений overflow, тому цикл не прийнято.
Окрім наведеного finding, підтверджених дефектів у перевіреному scope не знайдено.
Ролі мають інструктивні межі доступу, а не окремі ОС-пісочниці; це прямо описано.
Live hook trust/activation цими перевірками не атестовано. Offset pagination
не гарантує snapshot consistency за паралельних змін.

Handoff Reviewer → Coder: виправити P2 у дозволених API/test файлах,
уточнити документацію через host, запустити regression + tasks tests і передати
фактичний результат на повторний незалежний Reviewer. Reviewer код не змінював,
commit/push не виконував.
