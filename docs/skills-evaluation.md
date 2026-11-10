# ПР5: Інженерія Skills для TaskFlow

## Завершення 10.11.2026 — повний цикл успішний

Цей результат замінює висновки попередніх незавершених запусків нижче. Обидва встановлені skills виявлені каталогом поточної сесії та застосовані основним агентом. Bundled `quick_validate.py` для `.agents/skills/taskflow-adr` і `.agents/skills/taskflow-code-review` повернув `Skill is valid!`, exit code 0 для обох. Автоматичний неявний вибір у новій сесії окремо не перевірявся.

### taskflow-code-review

Scope: `app/schemas.py`, `app/tasks.py`, `tests/test_tasks.py`. Перед читанням CodePolicyEvaluator повернув allow/read_source. Перевірено POST/PATCH, omitted/null, extra-поля, HTTP 422 та поєднання фільтрів із джерелами MCP `Concepts/TaskFlow Architecture.md`, `Components/Pydantic.md`, `Decisions/Database Design.md`; PolicyEvaluator дозволив кожне читання. Підтверджених дефектів у цьому scope немає: `model_fields_set` відрізняє явний null, `exclude_unset=True` зберігає omitted, description допускає null, фільтри поєднуються через два where. Код не змінено.

### taskflow-adr: перевірка дублікатів → запис → читання

KB перед записом: чиста `main...origin/main`, 0 неопублікованих комітів; MERGE_HEAD і REBASE_HEAD відсутні. Git перевірено в користувацькому контексті після sandbox dubious ownership, без зміни safe.directory. Повний tracked-перелік Markdown-файлів не містив ADR-NNN; через MCP прочитано всі чотири наявні Decisions та архітектуру/Pydantic. Database Design описує SQLite/SQLAlchemy; три інші рішення є записами історії комітів. Еквівалентного ADR про контракт валідації немає. Адресний get_note нового шляху підтвердив відсутність файла; цей факт використано разом із перевіркою змісту, а не як єдиний доказ відсутності дубліката. Заблокований bulk search_notes не викликався.

На основі перевіреної чернетки створено `Decisions/ADR-001-request-validation.md`, статус `proposed`. Збережено контекст, альтернативи, позитивні/негативні наслідки та зв'язки depends_on до Pydantic і related_to до архітектури. Це документування наявної реалізації; прийняття рішення людиною не вигадується. PolicyEvaluator повернув allow/create_note.

MCP `ingest_note(note_path=..., content=...)` повернув **created**, `isError: false`, commit **c49bb5fb048be33c09a761bce1a071cf4061c4a7**. Ingestor виконав commit/push KB. Наступний MCP `get_note` успішний; отриманий текст програмно порівняно з переданим — **exact_readback: true**. Після запису KB чиста, `HEAD...@{upstream}` = **0/0**: публікацію підтверджено. Дублікати й тестові нотатки не створювалися; прямого запису у vault не було. Локальна попередня чернетка залишається історичним артефактом.

### Guardrails і тести

Фактична live-перевірка без секретів: `get_note(note_path='../guardrail_test_nonexistent.md')` зупинено **до MCP**: `Tool call blocked by PreToolUse hook: Invalid or ambiguous path.. Tool: mcp__taskflow_kb__get_note`. Операцію після block не повторювали іншим шляхом. Це пряме підтвердження live hook для цього виклику; успішні unit-тести окремо його не замінюють. Політики та hook не змінювалися. Для оновлення цього звіту evaluator повернув warn/update_source; повний diff переглянуто. Захищений untracked `.agents/` не змінювався й не додавався до Git.

Виконано `.venv/Scripts/python.exe -B -m pytest -q` у дозволеному користувацькому контексті: **194 passed, 1 warning in 49.31s**, exit code **0**. Попередження: StarletteDeprecationWarning про httpx у TestClient. Післязаписний `.venv/Scripts/python.exe -B -m ontology.validator C:/Users/user/TaskFlow-KB`: **13 сутностей, 33 зв'язки, 0 помилок**, exit code **0**; чотири попередження про пропущені нетипізовані/навігаційні нотатки. ПР5 завершена в перевіреному scope; звіт підготовлено до commit/push TaskFlow.

## Поточний запуск 10.11.2026 — discovery підтверджено, публікацію заблоковано

Цей розділ уточнює історичні результати нижче. Автоматичне виявлення обох skills **підтверджене каталогом доступних skills поточної сесії**: `taskflow-code-review` і `taskflow-adr` зареєстровані з шляхами `C:/Users/user/TaskFlow/.agents/skills/<name>/SKILL.md`, описами та коренем `r9`. Це пряме свідчення discovery, а не висновок із наявності файлів. Окрему нову сесію та неявний вибір без назви skill не перевіряли. `.agents` не змінювали.

### Реальне виконання taskflow-code-review

Застосовано процедуру виявленого skill до `app/schemas.py`, `app/tasks.py`, `tests/test_tasks.py`: PATCH omitted/null, HTTP 422, заборона extra-полів і поєднання фільтрів. `CodePolicyEvaluator` перед читанням повернув `allow / read_source` для кожного файла. `PolicyEvaluator` повернув `allow / read_note` для трьох джерел KB; реальні MCP `get_note(note_path=...)` для `Concepts/TaskFlow Architecture.md`, `Components/Pydantic.md`, `Decisions/Database Design.md` повернули текст та `isError: false`.

Підтверджених дефектів у цьому scope не виявлено: `model_fields_set` перевіряє явний null обов'язкових полів, `exclude_unset=True` зберігає omitted, description допускає null; два `where` поєднують фільтри. Наявні CRUD, invalid-input і filter тести перевіряють ці контракти. Код не змінено. Це виконання текстової процедури основним агентом, а не запуск окремої програми або незалежний benchmark.

### Реальне виконання taskflow-adr і стоп перед записом

Режим: публікація ADR про Pydantic-валідацію; застосовано процедуру skill, прочитано архітектурні джерела через MCP і звірено наявну чернетку `docs/adr/ADR-001-request-validation.md` з кодом. Чернетка залишається `proposed`, без змін; остаточний номер і перевірку дублікатів треба повторити перед майбутньою публікацією. Чинне `Database Design.md` описує інше питання — SQLite/SQLAlchemy.

Початкова перевірка Git у sandbox повернула `detected dubious ownership`. Повторна read-only перевірка у дозволеному користувацькому контексті без зміни `safe.directory` успішна: гілка `main...origin/main`, `git rev-list --count '@{upstream}..HEAD'` = **0**, але `git status --short` показав **` M "Concepts/MCP Integration Test.md"`**. Чистий стан KB не підтверджений. За прямою умовою користувача і пунктом 6 `.agents/skills/taskflow-adr/SKILL.md` запис зупинено. Немає підстав вважати цю зміну узгодженою; власник має її перевірити та зберегти або врегулювати самостійно.

`ingest_note` не викликався; створення ADR, commit/push KB, read-back нового ADR та післязаписна перевірка онтології **не виконані**. Наявні успішні MCP-читання не зараховуються як повний цикл запису/читання. Stash/reset, виправлення індексу, запис напряму у vault, зміни Guardrails або обхід hook не застосовувалися. Live hook telemetry цього запуску не підтверджена.

### Перевірка та публікація

Для звіту evaluator повернув `warn / update_source`; зміни доповнюють попередній незакомічений звіт, не видаляючи його. Виконано `.venv/Scripts/python.exe -B -m pytest -q` у дозволеному користувацькому контексті: **194 passed, 1 warning in 51.31s**, exit code **0**. Попередження — `StarletteDeprecationWarning` про httpx у TestClient. `git diff --check` успішний; Git попереджає про майбутню заміну LF на CRLF. Умова користувача «якщо все успішно» не виконана через dirty KB і відсутній write/read-back. Тому commit і push TaskFlow не виконуються; наявний untracked `.agents/` не додається до індексу.

## Повторна перевірка завершеності 10.11.2026

Базова ревізія: `a5683b8`. ПР5 **не завершена**. Попередні ручні сценарії нижче не доводять автоматичного виявлення чи запуску skills у Codex.

За [офіційною документацією Build skills](https://learn.chatgpt.com/docs/build-skills), проєктне discovery використовує `.agents/skills`. Каталог `skills/` не є стандартним місцем локального discovery; `[[skills.config]]` документований для керування знайденими skills, а не довільної реєстрації шляхів.

Фактичний `CodePolicyEvaluator(Path.cwd()).evaluate('write', path)` повернув **block / protected_directory** для обох `.agents/skills/taskflow-adr/SKILL.md` і `.agents/skills/taskflow-code-review/SKILL.md`: `Git, agent configuration and environment directories are protected.` Причина — `.agents` у `excluded_directories` файла `guardrails/code_policies.json`. Після block запис не виконувався.

Безпечне запропоноване виправлення: власник поза агентною сесією переглядає два наявні SKILL.md і встановлює їх звичайними файлами у `.agents/skills/<name>/SKILL.md`, залишаючи заборону агентного доступу до `.agents`. Не використовувати symlink/junction, зміну policy чи альтернативний запис після block. Потім перевірити обидва skills у селекторі Codex, за потреби перезапустити Codex. Встановлення не виконано.

Обох TaskFlow skills немає в поточному каталозі доступних skills. `Get-Command codex` не знайшов команду, `where.exe codex` повідомив `Could not find files for the given pattern(s)`. Це обмеження PATH цієї сесії, а не доказ відсутності інсталяції. Новий процес для discovery не запускався. Реальний запуск обох skills та implicit invocation **не підтверджені**; ручне читання SKILL.md не зараховано як успіх.

### MCP та передумови ADR

Фактичний `PolicyEvaluator` повернув `allow / read_note` для `Concepts/TaskFlow Architecture.md`. MCP `get_note(note_path='Concepts/TaskFlow Architecture.md')` повернув текст, structuredContent та `isError: false`. Це підтверджує читання через підключений MCP; поточну активацію live hook telemetry не підтверджено. Заблокований hook інструмент `search_notes` не викликався.

KB: гілка `main`, комітів понад upstream — `0`. Повторні `git status --short` показали ` M "Concepts/MCP Integration Test.md"`. `git diff --stat` і `--numstat` не показали змістовних змін, але Git видав попередження LF/CRLF. Можлива причина — нормалізація рядків або стан індексу; чисте дерево не підтверджене. Reset/stash/commit чужої зміни та запис індексу не виконувалися.

Застосовано пункт 6 [taskflow-adr](../skills/taskflow-adr/SKILL.md): «Якщо KB має сторонні незбережені зміни, залиш чернетку». Це передумова skill, не відмова MCP або Guardrails. Власник має перевірити й узгодити файл. Наявну чернетку `docs/adr/ADR-001-request-validation.md` збережено без змін. Нової нотатки чи дубліката не створено; `ingest_note` не викликався, читання новоствореного ADR неможливе. Повний цикл **не перевірений**. Перед майбутнім записом повторно перевірити еквівалентні рішення та номер ADR.

### Публікація змін цього прогону

Повторно виконано `.venv/Scripts/python.exe -B -m pytest -q` поза sandbox: **194 passed, 1 warning in 47.90s**, exit code **0**. Попередження — `StarletteDeprecationWarning` про httpx у TestClient. Запуск у sandbox перед цим завершився помилкою пошуку базового `Python313/python.exe`, exit code **1**; це помилка середовища, не провал тестів. Тести інфраструктури не доводять запуск skills або live-запис ADR.

Умова «після успішної перевірки» не виконана: discovery, реальний запуск skills і повний цикл ADR непідтверджені. Commit/push не виконувалися в жодному репозиторії. Змінено лише цей звіт; політики, `.agents`, hook і KB не змінено.

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
