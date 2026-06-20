---
type: ops
status: active
related: [[402-database-schema]]
created: 2026-05-28
updated: 2026-06-20
---
# Пайплайн обработки данных

> `pipeline.py` — единственный способ обновить данные в БД.

---

## Для LLM

`pipeline.py fetch` обновляет `option_chain_snapshot` и `option_greeks_history` — это основной источник данных для анализа. `pipeline.py monitor` записывает рекомендации в `recommendations` — LLM читает их для обратной связи.

Все данные для принятия решений — в `hedge_model.db` (см. [[402-database-schema]]).

---

*Создана: 2026-05-28 | Обновлено: 2026-06-20*
