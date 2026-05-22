# kb-for-agents

[English version](README.md)

Плагин для Claude Code и Codex, оформляющий паттерн трёхслойной базы знаний в виде устанавливаемых навыков и слэш-команд. Направьте его на кодовую базу или архив заметок — и получите рабочий процесс с прогрессивным раскрытием информации, описанный в статье [Knowledge Base for Agents](https://www.linkedin.com/posts/ahaidukof_karpathy-%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D0%BB%D0%B8%D0%B7%D0%BE%D0%B2%D0%B0%D0%BB-%D1%82%D0%BE-%D1%87%D1%82%D0%BE-%D0%BC%D1%8B-%D0%BD%D0%B0%D1%89%D1%83%D0%BF%D0%B0%D0%BB%D0%B8-activity-7446836637143130112-o920/).

## Что внутри

- **Навыки (skills)** — `kb-build`, `kb-query`, `kb-check-drift`, `kb-refresh`, `kb-record-decision`, `kb-maintain`. Паттерн, закреплённый в коде.
- **Команды** — `/kb-build`, `/kb-query`, `/kb-check-drift`, `/kb-refresh`, `/kb-record-decision`, `/kb-maintain`. Тонкие обёртки над навыками.
- **Шаблоны** — стартовые заготовки для индексов, саммари, решений, `_root.md`, состояния. Шаги для ручной сборки см. в [templates/README.md](templates/README.md).
- **Документация** — обоснование паттерна: [концепция](docs/concept.md), [правила навигации](docs/navigation-rules.md), [стратегия обновления](docs/refresh-strategy.md).

## Установка

### Claude Code (плагин целиком)

```
/plugin marketplace add olegvg/kb-for-agents
/plugin install kb-for-agents@kb-for-agents
```

Ставит все навыки и слэш-команды.

### Codex marketplace

Репозиторий также подготовлен для Codex:

- `.codex-plugin/plugin.json` — манифест Codex-плагина.
- `.agents/plugins/marketplace.json` — self-hosted индекс Codex marketplace, указывающий на этот репозиторий плагина.

Codex загружает навыки из `skills/`. Директория `commands/` остаётся для совместимости со слэш-командами Claude Code.

### Claude Desktop (отдельные навыки)

Claude Desktop не загружает плагины Claude Code, поэтому runtime-навыки выкладываются отдельными zip-архивами на странице [Releases](https://github.com/olegvg/kb-for-agents/releases). Скачай нужные и загрузи через UI навыков Claude Desktop:

- `kb-build-<version>.zip`
- `kb-query-<version>.zip`
- `kb-refresh-<version>.zip`
- `kb-check-drift-<version>.zip`

К каждому релизу приложен `SHA256SUMS` — проверка через `sha256sum -c SHA256SUMS`.

`kb-record-decision` и `kb-maintain` — только для Claude Code: запись решений опирается на формат plan-документов и orchestration.

## Быстрый старт

В любой сессии Claude Code, открытой в корне вашего корпуса:

```
/kb-build .
/kb-query where are fees charged?
```

После того как вы внесли изменения в корпус:

```
/kb-check-drift
/kb-refresh src/billing/
```

Когда запланированная работа завершена и нужно сохранить её ключевые решения:

```
/kb-record-decision docs/plans/2026-03-19-1400/plan-billing-rewrite.md
```

## Как это работает

Плагин создаёт директорию `.kb/` **внутри вашего корпуса** (не внутри плагина). У неё три слоя плюс хранилище решений:

1. **Источники (sources)** — сам корпус. Не дублируется.
2. **Саммари (summaries)** (`.kb/summaries/<area>/*.md`) — проза по темам, по одному файлу на тему.
3. **Индексы (indexes)** (`.kb/indexes/*.md`) — навигация, ≤300 токенов на файл. Точка входа — `.kb/indexes/_root.md`.

Рядом: **Решения (decisions)** (`.kb/decisions/*.md`) — дистиллированные записи, извлечённые из завершённых планов. На них ссылаются саммари, которых они касаются, через секции `## Key decisions`; отдельной верхнеуровневой областью они не выносятся.

На любой запрос агент сначала читает индексы, затем спускается глубже. Если вопрос звучит как «как работает X и почему это было сделано именно так?», навигация приводит к саммари, а оттуда — по ссылкам на связанные решения. Контекст остаётся ограниченным, а путь навигации можно проверить.

Полное обоснование — в [docs/concept.md](docs/concept.md).

## Что это

Стартовый набор: навыки, команды, шаблоны, концептуальная документация. Паттерн, оформленный так, чтобы применять его без повторного чтения статьи.

## Что это не

Это не RAG-библиотека и не универсальный фреймворк для агентов.

## Требования

- Claude Code или Codex с поддержкой skills.
- Корпус, который вы хотите задокументировать. Корпус с git-историей настоятельно рекомендуется — `/kb-refresh` и `/kb-check-drift` оба зависят от git-истории.

## Лицензия

MIT. См. [LICENSE](LICENSE).
