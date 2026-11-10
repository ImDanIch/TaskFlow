---
type: decision
status: proposed
tags: [architecture, taskflow]
relationships:
  - type: depends_on
    target: Components/Pydantic.md
  - type: related_to
    target: Concepts/TaskFlow Architecture.md
---

# ADR-001: Валідація HTTP-запитів через Pydantic

Дата: 2026-11-10. Чернетка для `Decisions/ADR-001-request-validation.md`; у KB не записана.

## Контекст

TaskFlow приймає POST і PATCH завдань. Потрібно відрізняти пропущене поле PATCH від явного null та відхиляти невідомі поля.

## Рішення

Зафіксувати наявний підхід: окремі TaskCreate/TaskUpdate у `app/schemas.py`, `extra='forbid'`, Literal для статусу й пріоритету та перевірка явного null через model_fields_set. Маршрут застосовує model_dump(exclude_unset=True). Це пропозиція документування наявної поведінки; функціональність не змінюється.

## Альтернативи

- Ручна валідація словників у маршрутах: дублює перевірки й ускладнює контракт.
- Єдина схема POST/PATCH: потребує додаткової логіки обов'язковості полів.
- Дозволити довільні поля: приховує помилки клієнтів.

## Наслідки

Позитивні: єдиний контракт валідації, HTTP 422, передбачуваний PATCH. Негативні: залежність від семантики Pydantic; зміни схем потребують перевірки сумісності. Міграції БД та авторизація цим рішенням не реалізуються.

## Перевірка

Наявні `tests/test_tasks.py`: test_task_crud, test_invalid_input, test_create_requires_title. Фактичний запуск і його результат наведено у `docs/skills-evaluation.md`.

## Джерела

MCP: `Concepts/TaskFlow Architecture.md`, `Components/Pydantic.md`. Код: `app/schemas.py`, `app/tasks.py`.
