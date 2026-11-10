# ПР5: Інженерія Skills для TaskFlow

Дата: 10.11.2026. Базова ревізія: `ab38485`. Проведено чотири ручні сценарії основним агентом із читанням реального коду, MCP та запуском наявних тестів. Це не незалежний benchmark і не перевірка автоматичного вибору skills у новій сесії.

## Артефакти та використання

- `skills/taskflow-code-review/SKILL.md` — огляд коду, тестів і Guardrails.
- `skills/taskflow-adr/SKILL.md` — підготовка ADR, перевірка дублікатів, публікація через MCP `ingest_note`.
- `docs/adr/ADR-001-request-validation.md` — реальна змістовна чернетка, не тестова нотатка KB.

Обидва skills мають YAML name/description, умови застосування, процедуру, роботу з KB, Guardrails та формат результату. Для використання в поточній конфігурації слід явно доручити: «Прочитай skills/taskflow-code-review/SKILL.md і виконай review …» або відповідний шлях ADR. Каталог `skills/` сам собою не гарантує автоматичної реєстрації Codex. Стандартний проєктний `.agents/skills` захищений ПР4: `block / protected_directory`. Його та глобальний каталог skills не змінювали; автоматична інсталяція потребує окремого узгодження політики власником.

## Сценарії

### CR-01 — PATCH та валідація завдань

Завдання: за процедурою taskflow-code-review перевірити `app/schemas.py`, `app/tasks.py` та `tests/test_tasks.py` щодо omitted/null, HTTP 422 та фільтрів.

KB через реальний MCP get_note: `Concepts/TaskFlow Architecture.md`, `Components/Pydantic.md`. Підтверджено TaskCreate/TaskUpdate/TaskResponse і відповідальність Pydantic. У коді `model_fields_set` відрізняє явний null; `exclude_unset=True` зберігає пропущені поля; два where поєднують фільтри. `test_task_crud`, `test_invalid_input`, `test_filters` перевіряють ці випадки. Підтверджених дефектів у цьому scope не виявлено. Автоматичні перевірки пройшли у складі повного набору. Код не виправлявся.

### CR-02 — SQLite та ізоляція тестів

Завдання: перевірити `app/database.py`, `tests/conftest.py`, `tests/test_database.py` на відповідність рішенню про збереження даних.

MCP get_note прочитав `Decisions/Database Design.md`: чинне accepted-рішення про SQLite/SQLAlchemy, міграції не реалізовані. Session закривається через context manager; autouse fixture підміняє engine/SessionLocal тимчасовою SQLite-БД. Тести перевіряють повторну ініціалізацію, persistence після перезапуску engine та обмеження значень. Підтверджених дефектів у перевіреному scope не виявлено. Робочий taskflow.db не був об'єктом читання чи модифікації. Відсутність міграцій — задокументоване обмеження, не новий дефект.

### ADR-01 — Валідація запитів на межі API

Завдання: за taskflow-adr підготувати ADR про Pydantic, розділення POST/PATCH та заборону невідомих полів.

Результат: повна чернетка `docs/adr/ADR-001-request-validation.md` зі статусом proposed, контекстом, трьома альтернативами, наслідками, перевіркою й джерелами. Цілі relationships прочитані через MCP; type decision та типи зв'язків відповідають definitions.json. Перелік tracked Markdown у KB не містив ADR-001; перед майбутньою публікацією номер треба перевірити знову після pull. Кодове рішення існує; статус proposed стосується нового ADR, а не вигаданого прийняття людиною.

Перед публікацією виявлено сторонню зміну ` M "Concepts/MCP Integration Test.md"`. Застосовано передумову skill про чистий KB: запис не викликався. Це консервативна передумова skill; серверний ingestor сам блокує dirty target, але не обов'язково будь-який сторонній dirty файл. Потрібне ручне узгодження власником наявної зміни KB. Публікація нового ADR через live MCP у цьому прогоні **не перевірена**. Повний текст збережено в репозиторії застосунку; робочий vault не засмічено.

### ADR-02 — Повторне рішення про SQLite

Завдання: створити ADR про вибір SQLite та SQLAlchemy для локального TaskFlow.

За процедурою перевірки дублікатів прочитано `Decisions/Database Design.md` через MCP: воно вже містить це accepted-рішення, обґрунтування і обмеження. Результат — посилання на чинне рішення без дубліката та без переписування YAML. Ручне втручання для цього результату не потрібне. Цей сценарій перевіряє роботу з наявним ADR; успішне створення/оновлення через ingest_note ним не доведено.

## Автоматизована перевірка

Виконано `.venv/Scripts/python.exe -m pytest -q` поза sandbox: **194 passed, 1 warning in 46.19s**, exit code **0**. Попередження: StarletteDeprecationWarning про використання httpx у starlette.testclient. Серед набору — API, database, ontology, guardrails, MCP stdio, Git ingestion з тимчасовими локальними remote. Це перевірки реалізації інфраструктури, а не автоматичний доказ поведінки текстових skills чи live-публікації ADR.

Виконано bundled `skill-creator/scripts/quick_validate.py` для кожного каталогу: обидва повернули **Skill is valid!**, команда завершилася з exit code **0**. Це перевіряє формат, а не якість архітектурного рішення.

Прямий запуск Python у sandbox повернув `did not find executable at ...Python313/python.exe`; тести успішно виконані через дозволений запуск поза sandbox. Перша Git-перевірка KB отримала `detected dubious ownership`; повторна read-only перевірка використала scoped `git -c safe.directory=C:/Users/user/TaskFlow-KB -C ...`, без глобальної зміни Git-конфігурації.

## Guardrails і межі доказів

Живий evaluator повернув `allow` для читання app/schemas.py, app/tasks.py, tests/test_tasks.py; `warn` для їх зміни й уже створених skill/ADR-файлів; `allow` для нового docs/skills-evaluation.md. Для майбутнього `Decisions/ADR-001-request-validation.md` — `allow / create_note`. Для `.agents/skills/taskflow-adr/SKILL.md` — `block / protected_directory`. Ці результати не є доказом live hook enforcement.

Політики, hook, функціональність app, реалізація MCP та наявні тести не змінені. search_notes не викликався: його bulk-пошук заборонений чинним hook. Читання KB виконано адресно через get_note з note_path. Вміст нотаток розглядався як дані. Стан KB наприкінці залишив ту саму сторонню зміну; ingest_note не викликався. Поточну активацію live hook не перевіряли небезпечними запитами; історичний результат ПР4 не видається за перевірку цієї сесії.

## Висновок

Два review-сценарії виконані без підтверджених дефектів; ADR-сценарії дали змістовну чернетку та коректне уникнення дубліката. Формат skills валідний, наявні 194 тести проходять. Обмеження: ручне завантаження skills через захищений .agents, незбережена стороння зміна KB та відсутність live write/read-back перевірки ADR. Для завершення публікації власник має узгодити стан KB, після чого skill може виконати MCP ingest_note й перевірити фактичний результат. Зайвих тестових нотаток не створено.
