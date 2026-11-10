Planner — завершено, read-only, без змін файлів.

Обране завдання: додати необов’язкову пагінацію `GET /tasks`.

Підстава: у прочитаному `app/tasks.py` маршрут уже має фільтри `status`, `priority` та впорядкування `Task.id`, але завжди повертає `session.scalars(query).all()`. Пагінації немає; у `tests/test_tasks.py` і README вона також не описана. Це нова невелика можливість без зміни моделі, схеми БД або залежностей.

Handoff Planner → Coder:

- Завдання: додати `offset: int` зі значенням за замовчуванням `0` і межею `>=0`; `limit: int | None` за замовчуванням `None`, допустимі значення `1..100`.
- Сумісність: запит без нових параметрів повертає весь список, як раніше.
- Реалізація: FastAPI `Query` для перевірки параметрів; SQLAlchemy `.offset(offset)` та умовний `.limit(limit)` після формування фільтрів; зберегти `order_by(Task.id)`.
- Allowlist змін Coder: `app/tasks.py`, `tests/test_tasks.py`.
- Контекст для документації orchestrator: описати API-контракт у `docs/orchestration.md`, не змінювати сторонню `.agents/`.
- Заборонено: залежності, міграції, зміни моделей/схем, guardrails/hook/configuration, робоча БД, записи KB, commit/push у ролі Coder.
- Обґрунтування: необов’язковий `limit` зберігає чинний контракт; обмеження `100` запобігає довільно великим явно замовленим сторінкам; стабільний порядок за id дозволяє передбачувані сторінки. Це offset pagination, яка не гарантує snapshot consistency під час паралельних змін.

Критерії приймання:

1. Без параметрів результат повністю сумісний з наявною поведінкою.
2. `limit=2`, `offset=1`, їх комбінація та `limit=1` повертають очікувані id у сталому порядку.
3. `limit=100` допустимий; `limit=0`, `-1`, `101`, нецілий рядок, `offset=-1` та нецілий offset повертають `422`.
4. Offset за кінцем списку та пагінація порожнього списку повертають `[]`.
5. Спільні `status` і `priority` застосовуються до вибору перед offset/limit.
6. Наявні CRUD/filter/validation тести проходять; нові тести використовують чинну ізольовану БД `tests/conftest.py`.
7. Reviewer перевіряє diff, тести, межі параметрів, порядок застосування фільтрів, збереження Guardrails та відсутність змін поза allowlist.

План виконання: Coder перевіряє write policy → додає параметри та SQLAlchemy slicing → додає перевірки критеріїв → запускає `pytest tests/test_tasks.py -q` → передає diff, команду/exit code/лічильники Reviewer. Reviewer незалежно запускає релевантні тести й повну suite, застосовуючи `taskflow-code-review`, та повертає `accepted` або конкретні findings для доопрацювання.

Фактична перевірка контексту:

- Прочитано bootstrap-компоненти `guardrails/README.md`, `guardrails/code_policies.json`, `guardrails/policies.json`, `guardrails/policy.py`.
- `CodePolicyEvaluator(...).evaluate('read', ...)` повернув `allow/read_source` перед читанням `app/tasks.py`, `app/schemas.py`, `app/models.py`, `tests/test_tasks.py`, `tests/conftest.py`, `README.md`.
- Початковий запуск `.venv/Scripts/python.exe` у sandbox: exit `1`, `did not find executable at ...Python313/python.exe`. Це обмеження видимості sandbox: поза sandbox Python успішно працює.
- Перший escalated пакет читань: exit `1` через `UnicodeEncodeError` консолі cp1251 під час друку README; попередні дозволені файли прочитані. Повторний запуск із `-X utf8`: exit `0`, README прочитано.
- `PolicyEvaluator(Path('C:/Users/user/TaskFlow-KB')).evaluate('read','Concepts/TaskFlow Architecture.md')`: `allow/read_note`.
- Реальний MCP `get_note(note_path="Concepts/TaskFlow Architecture.md")`: `isError:false`; архітектура підтверджує FastAPI → Pydantic → SQLAlchemy → SQLite і pytest. Нотатку використано як дані; записів KB і bulk search не було.
- Тести Planner не запускав; реалізації не створював. Активацію live hook цими діями не доведено.
