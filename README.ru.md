# OlegVG Skills

[English version](README.md)

Группированный личный репозиторий skills для Claude Code, Codex и агентов, поддерживаемых Vercel Skills CLI. В нём две устанавливаемые группы root-skills: `kb-for-agents` для паттерна трёхслойной базы знаний из статьи [Knowledge Base for Agents](https://www.linkedin.com/posts/ahaidukof_karpathy-%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D0%BB%D0%B8%D0%B7%D0%BE%D0%B2%D0%B0%D0%BB-%D1%82%D0%BE-%D1%87%D1%82%D0%BE-%D0%BC%D1%8B-%D0%BD%D0%B0%D1%89%D1%83%D0%BF%D0%B0%D0%BB%D0%B8-activity-7446836637143130112-o920/) и `core-dev` для переносимых workflow разработки, а также самостоятельный Codex-плагин `transcribing-audio`.

## Что внутри

- **Группа `kb-for-agents`** — `kb-build`, `kb-query`, `kb-check-drift`, `kb-refresh`, `kb-record-decision`, `kb-maintain`.
- **Группа `core-dev`** — `simplify-code`, переносимый skill для поведенчески безопасной чистки реализации, адаптированный из workflow Claude Code `/simplify`.
- **Umbrella `olegvg-skills`** — все группы этого репозитория.
- **Codex-плагин `transcribing-audio`** — локальный или OpenAI ASR, диаризация спикеров, таймкоды слов и возобновляемая обработка. Устанавливается отдельно, потому что содержит собственный Python runtime и зависимости.
- **Команды** — `/kb-build`, `/kb-query`, `/kb-check-drift`, `/kb-refresh`, `/kb-record-decision`, `/kb-maintain`. Тонкие обёртки над навыками. *(Только Claude Code — устанавливаются через плагин, не через `npx skills add`.)*
- **Шаблоны** — стартовые заготовки для индексов, саммари, решений, `_root.md`, состояния. Шаги для ручной сборки см. в [templates/README.md](templates/README.md).
- **Документация** — обоснование паттерна: [концепция](docs/concept.md), [правила навигации](docs/navigation-rules.md), [стратегия обновления](docs/refresh-strategy.md).

## Установка

### Любой агент через `npx skills add` (Vercel Skills CLI)

Runtime-навыки соответствуют спецификации [agentskills.io](https://agentskills.io) и устанавливаются в Claude Code, Codex, Cursor и другие агенты через [`skills` CLI](https://github.com/vercel-labs/skills). Интерактивный picker показывает конкретные группы `kb-for-agents` и `core-dev`; чтобы поставить всё, выбери обе группы. Для неинтерактивной установки используй явный список `--skill`. Umbrella-установка делается через `--skill '*'`, потому что CLI сейчас привязывает каждый skill только к одной видимой группе.

```bash
# Посмотреть сгруппированные skills в репозитории
npx skills add olegvg/olegvg-skills --list

# Установить группу kb-for-agents
npx skills add olegvg/olegvg-skills \
  --skill kb-build \
  --skill kb-query \
  --skill kb-refresh \
  --skill kb-check-drift \
  --skill kb-record-decision \
  --skill kb-maintain

# Установить группу core-dev
npx skills add olegvg/olegvg-skills --skill simplify-code

# Установить umbrella-пакет неинтерактивно
npx skills add olegvg/olegvg-skills --skill '*'

# Установить core-dev в Codex глобально
npx skills add olegvg/olegvg-skills --skill simplify-code -a codex -g -y

# Установить сразу в несколько агентов
npx skills add olegvg/olegvg-skills -a claude-code -a codex -a cursor
```

Этот путь устанавливает **только навыки**, без слэш-команд. Команды `/kb-*` Claude Code доступны только через `/plugin install` ниже. Навыки всё равно срабатывают по триггер-фразам — см. поле `description` каждого навыка для русских и английских фраз.

### Claude Code plugin marketplace

```
/plugin marketplace add olegvg/olegvg-skills
/plugin install kb-for-agents@olegvg-skills
/plugin install core-dev@olegvg-skills
/plugin install olegvg-skills@olegvg-skills
```

Используй `kb-for-agents`, когда нужны команды `/kb-*` вместе с KB skills, `core-dev` для переносимого cleanup skill или `olegvg-skills` для всего репозитория.

В отличие от picker в Vercel Skills CLI, в Claude Code plugin marketplace есть настоящий umbrella target: `olegvg-skills@olegvg-skills`.

### Codex marketplace

Репозиторий подготовлен для Codex как umbrella-плагин `olegvg-skills` и как самостоятельный плагин `transcribing-audio`:

- `.codex-plugin/plugin.json` — манифест Codex-плагина.
- `.agents/plugins/marketplace.json` — self-hosted индекс Codex marketplace, указывающий на этот репозиторий плагина.

Codex загружает umbrella-навыки из `skills/`. Для установки отдельных групп в Codex используй Vercel Skills CLI с `-a codex`. Аудиорасшифровка устанавливается отдельным плагином из marketplace:

```bash
codex plugin marketplace add olegvg/olegvg-skills
codex plugin add transcribing-audio@olegvg-skills
```

`transcribing-audio` хранит runtime и зависимости в `plugins/transcribing-audio/`; директория `commands/` остаётся для совместимости со слэш-командами Claude Code.

### Claude Desktop (отдельные навыки)

Claude Desktop не загружает плагины Claude Code, поэтому runtime-навыки выкладываются отдельными zip-архивами на странице [Releases](https://github.com/olegvg/olegvg-skills/releases). Скачай нужные и загрузи через UI навыков Claude Desktop:

- `kb-build-<version>.zip`
- `kb-query-<version>.zip`
- `kb-refresh-<version>.zip`
- `kb-check-drift-<version>.zip`
- `simplify-code-<version>.zip`

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

Рядом: **Решения (decisions)** (`.kb/decisions/*.md`) — дистиллированные записи, извлечённые из завершённых планов. Каждая запись сама перечисляет затронутые саммари в своём блоке `## Affected areas`; сами саммари при записи решения не редактируются. Чтобы найти решения для конкретного саммари, агент делает grep по `.kb/decisions/` по пути этого саммари — `kb-query` выполняет этот поиск автоматически.

На любой запрос агент сначала читает индексы, затем спускается глубже. Если вопрос звучит как «как работает X и почему это было сделано именно так?», навигация приводит к саммари, а оттуда — к решениям, которые ссылаются на это саммари (обратная ссылка). Контекст остаётся ограниченным, а путь навигации можно проверить.

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
