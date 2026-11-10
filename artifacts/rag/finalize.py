"""Assemble the evaluation from saved evidence without rerunning retrieval."""
import hashlib
import json
from pathlib import Path
from guardrails.policy import PolicyEvaluator
from orchestration.workflow import Workflow

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/rag'


def main():
    before = json.loads((OUT / 'before.json').read_text(encoding='utf-8'))
    after = json.loads((OUT / 'after.json').read_text(encoding='utf-8'))
    answers = json.loads((OUT / 'answers.json').read_text(encoding='utf-8'))
    vault = ROOT.parent / 'TaskFlow-KB'
    policy = PolicyEvaluator(vault)
    current = {p.relative_to(vault).as_posix(): hashlib.sha256(
        p.read_text(encoding='utf-8').encode()).hexdigest() for p in vault.rglob('*.md')
        if policy.evaluate('read', p.relative_to(vault).as_posix()).decision == 'allow'}
    previous = json.loads((OUT / 'corpus-before.json').read_text(encoding='utf-8'))
    assert current == previous, 'KB corpus changed'
    index_path = ROOT / '.rag-index/608980b9b217d204fee00462.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    assert index_path.stat().st_size == 288138
    for a, r in zip(answers, after['results']):
        assert a['source'] in r['sources']
    ledger = json.loads((OUT / 'run.json').read_text(encoding='utf-8'))
    workflow = Workflow(**ledger)
    if workflow.active == 'Coder':
        workflow.handoff('Coder', agent_id='/root', context='Planner handoff and saved baseline',
            rationale='Host completed partial Coder work after subagent usage limit',
            result='32 existing chunks; offline model verified; real MCP 10 queries; 237 distinct tests passed across full run and targeted fixes',
            next_role='Reviewer')
        workflow.handoff('Reviewer', agent_id='/root/reviewer_pr7',
            context='Code diff, retrieved sources and metrics; see reviewer.md',
            rationale='Independent skill review; host resolved findings and checked acceptance evidence',
            result='Read-only review saved; answers distinguish gold miss and partial source evidence; tests not repeated by reviewer',
            next_role='Complete')
        workflow.save(ROOT, 'artifacts/rag/run.json')
    lines = ['# ПР7: RAG над TaskFlow-KB', '',
        'Дата: 2026-11-10. Наявний індекс: **32 фрагменти, 288138 байтів**; його не перебудовували після ремонту моделі.',
        'Модель: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, 384 виміри.',
        'Вікна: 600 символів, перекриття 100; шлях додається до тексту, tokenizer обмежений 256 токенами (щільні фрагменти можуть обрізатися). Cosine, найкращий chunk на нотатку, детермінований top-5.', '',
        '## Методика та результати', '',
        'Використано ті самі 10 запитів і gold-шляхи з `artifacts/rag/queries.json`; baseline не повторювався. Початковий substring-алгоритм збережено як `lexical_search_notes`; baseline виконано через MCP з підміною лише методу пошуку та спільною фільтрацією дозволеного корпусу. Це відновлений baseline, а не вимірювання до першого редагування.',
        'Обидва результати отримано через справжній SDK stdio. Сигнатура MCP `search_notes(query: str) -> list[str]` збережена. Повні ранги, джерела й час: `before.json`, `after.json`.', '',
        '| Метрика | До | Після |', '|---|---:|---:|',
        f"| Hit@5 | {before['hit_at_5']:.2f} | {after['hit_at_5']:.2f} |",
        f"| MRR@5 | {before['mrr_at_5']:.2f} | {after['mrr_at_5']:.2f} |", '',
        'Hit@5 — частка запитів із заданим gold у перших п’яти; MRR@5 — середнє 1/rank, для промаху 0. Малий корпус і запити з відомими темами не дають оцінки загальної якості чи статистичної значущості.', '',
        '| № | Запит | Ранг до | Ранг після |', '|---|---|---:|---:|']
    for i, (b, a) in enumerate(zip(before['results'], after['results']), 1):
        lines.append(f"| {i} | {a['query']} | {b['rank'] or '—'} | {a['rank'] or '—'} |")
    lines += ['', '## Відповіді агента та skills', '',
        'Host сформував наведені нижче відповіді лише з текстів, повернутих MCP `get_note` для результатів кожного пошуку. Baseline повернув порожні списки для всіх 10 запитів: відповідь у кожному випадку — «Джерел для відповіді не знайдено».',
        'Рубрика: 2 — правильна й повна відповідь із джерелом; 1 — правильна, але джерело дає лише часткові дані; 0 — змістовної підтвердженої відповіді немає. До: **0/20**, після: **19/20**. Це ручна оцінка host, перевірена незалежною роллю Reviewer; не автоматичний або сліпий LLM-бенчмарк. Відмова baseline не є галюцинацією.',
        'Запит 2 пропустив gold Pydantic, однак ADR у top-5 містить потрібні факти для правильної відповіді. Запит 8 має gold на другому місці. Для запиту 10 підтверджено лише сам факт PR3 test, а не команди чи commit.', '']
    for a in answers:
        lines.append(f"{a['id']}. {a['answer']} Джерело: `{a['source']}`; оцінка {a['score']}/2.")
    lines += ['',
        'Застосовано наявний `taskflow-code-review`: незалежний Reviewer прочитав код, політики та збережені retrieval-джерела; звіт `artifacts/rag/reviewer.md`. Стару заборону search у skill застосовано з урахуванням прямого дозволу користувача на ПР7; інструкції skills не редагувалися. ADR skill не запускався: новий ADR не запитано. Retrieval дає skill джерела через search → get_note; сам skill не має автоматичного RAG-виклику.',
        'Оркестрація: реальний Planner → Coder (завершив host після usage-limit subagent) → незалежний Reviewer. Контекст передачі включає контракт, джерела та результати. Фактичні handoff збережено існуючим `Workflow` у `artifacts/rag/run.json`. Ролі не вигадувалися; Reviewer не повторював тести. Блокуючі зауваження до manifest і таймауту завантаження виправлено host.', '',
        '## Ініціалізація, кеш і межі', '',
        'Повний snapshot-download зупинено. Справні файли тієї самої revision знайдено в локальних кешах; 9 потрібних файлів скопійовано без нового завантаження. JSON та safetensors перевірено, SHA-256 збережено у локальному manifest. Раніше sandbox показував 0 байтів для cache links; перевірка робочим Python встановила справжні розміри. Це не підтверджувало пошкодження ваг.',
        'Offline probe: імпорт 16.39 с, повний запуск 20.98 с, embeddings 384. MCP перший запит 4.20 с; решта близько 0.1 с. Імпорт виконується на головному потоці до запуску worker. Модель кешується на процес; індекс кешується до зміни файла. Пошук не сканує корпус і не індексує нотатки; пошкоджений/відсутній індекс дає помилку. Після зміни KB потрібне явне оновлення індексу.',
        'MCP використовує перевірену локальну директорію й `local_files_only=True`; evaluation також встановлює offline env. Handshake: 60 с, запит: 45 с. Лише відсутній файл при підготовці може завантажуватися окремим hf_hub_download у subprocess з лімітом 60 с. build_index має міжетапний, а не жорсткий таймаут; для CLI слід обмежувати зовнішній процес.', '',
        '## Тести, MCP і Guardrails', '',
        'Повний `python -m pytest -q`: **233 passed, 2 failed**, exit 1, 123.48 с. Причина двох падінь: link-тести очікували автоматичну побудову індексу; додано явну побудову порожнього ізольованого індексу. Повторено лише ці два тести та дві нові перевірки кешування/manifest: **4 passed**, exit 0, 0.20 с. Разом **237 різних тестів успішні**; повний набір повторно не запускався.',
        'Реальний MCP тест перевірив handshake, discovery, пошук та читання; Git ingestion тестувався лише в тимчасовому vault. Guardrails-тести пройшли в повному запуску; unit/subprocess evidence не атестує live hook trust поточної IDE-сесії. Історична PR7-зміна hook уже була в робочому дереві до продовження; під час ремонту Guardrails не редагувалися. Сервер перевіряє PolicyEvaluator перед читанням корпусу і видачею шляхів.',
        f'Контрольні суми всіх {len(current)} дозволених Markdown-нотаток збігаються з corpus-before.json; TaskFlow-KB не змінено. Індекс і модель виключено з Git через `.rag-index/`. Стороння `.agents/` не включається до commit.', '']
    (ROOT / 'docs/rag-evaluation.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Report saved; KB hashes unchanged; existing index preserved')


if __name__ == '__main__':
    main()
