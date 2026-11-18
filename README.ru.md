# OlegVG Skills

[English version](README.md)

Группированный личный репозиторий skills для Claude Code, Codex и агентов, поддерживаемых Vercel Skills CLI. В нём две устанавливаемые группы root-skills: `kb-for-agents` для паттерна трёхслойной базы знаний из статьи [Knowledge Base for Agents](https://www.linkedin.com/posts/ahaidukof_karpathy-%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D0%BB%D0%B8%D0%B7%D0%BE%D0%B2%D0%B0%D0%BB-%D1%82%D0%BE-%D1%87%D1%82%D0%BE-%D0%BC%D1%8B-%D0%BD%D0%B0%D1%89%D1%83%D0%BF%D0%B0%D0%BB%D0%B8-activity-7446836637143130112-o920/) и `core-dev` для переносимых workflow разработки, а также самостоятельный плагин `transcribing-audio` для Claude Code и Codex.

## Что внутри

- **Группа `kb-for-agents`** — `kb-build`, `kb-query`, `kb-check-drift`, `kb-refresh`, `kb-record-decision`, `kb-maintain`.
- **Группа `core-dev`** — `simplify-code` для безопасной чистки реализации, `mobile-test-environments` для Android/iOS и Appium и `audit-state-machines` для аудита неявных переходов состояний со ссылками на код. Инструкции для мобильных устройств загружаются по платформе. Диагностика не требует дополнительных Python-пакетов, Maestro необязателен.
- **Umbrella `olegvg-skills`** — все группы root-навыков этого репозитория.
- **Плагин `transcribing-audio` (Claude Code и Codex)** — локальный или OpenAI ASR, диаризация спикеров, таймкоды слов и возобновляемая обработка. Устанавливается отдельно, потому что содержит собственный Python runtime и зависимости.
- **Команды Claude Code** — конкретные группы предоставляют нативные команды навыков, например `/kb-for-agents:kb-build`. Umbrella также сохраняет KB-обёртки совместимости в `commands/`; у `core-dev` их нет. Skills CLI устанавливает нативные навыки без этих обёрток.
- **Шаблоны** — стартовые заготовки для индексов, саммари, решений, `_root.md`, состояния. Шаги для ручной сборки см. в [templates/README.md](templates/README.md).
- **Документация** — обоснование паттерна: [концепция](docs/concept.md), [правила навигации](docs/navigation-rules.md), [стратегия обновления](docs/refresh-strategy.md).

## Установка

Выбери один способ установки для каждого агента и workspace, чтобы не получить
дубли навыков. Root-навыки лежат в `skills/`; `transcribing-audio` устанавливается
отдельным плагином со своим Python runtime и не входит в umbrella.

### Skills CLI через Bun или Node.js

Запускай команды из нужного проекта. `install` — алиас `add`; любую команду
`bunx skills@latest install` можно выполнить как `npx skills@latest add`.

```bash
# Посмотреть удалённые или локальные навыки без установки.
bunx skills@latest install olegvg/olegvg-skills --list
bunx skills@latest install ./olegvg-skills --list

# Выбрать навыки и агентов; по умолчанию установка в текущий проект.
bunx skills@latest install olegvg/olegvg-skills --skill simplify-code --agent codex claude-code

# Установить KB-группу.
bunx skills@latest install olegvg/olegvg-skills --skill kb-build kb-query kb-refresh kb-check-drift kb-record-decision kb-maintain --agent codex

# Все root-навыки; интерактивно можно выбрать обе группы.
bunx skills@latest install olegvg/olegvg-skills --skill '*'

# Явная глобальная установка без вопросов.
bunx skills@latest install olegvg/olegvg-skills --skill simplify-code --agent codex --global --yes
```

Picker показывает `kb-for-agents` и `core-dev`; выбери обе группы для umbrella.
Устанавливается полный каталог навыка с references и локальными шаблонами.
Этот путь не устанавливает command shims из `commands/` и аудио-runtime.
Аудионавык скрыт из обычного поиска CLI: отдельно от runtime он не работает.

После публикации соответствующего тега можно закрепить версию источника:

```bash
bunx skills@latest install https://github.com/olegvg/olegvg-skills/tree/v0.8.0 --skill audit-state-machines --agent codex

# Обновить выбранную проектную установку до доступных upstream-изменений.
bunx skills@latest update simplify-code --project
```

Чтобы сохранить точную версию, повторно используй закреплённый источник.
Поддерживаемые агенты и scope обновления описаны в
[Skills CLI](https://github.com/vercel-labs/skills).

### Claude Code marketplace и локальный запуск

```bash
claude plugin marketplace add olegvg/olegvg-skills --scope project
claude plugin install kb-for-agents@olegvg-skills --scope project
claude plugin install core-dev@olegvg-skills --scope project
# Либо umbrella вместо отдельных групп.
claude plugin install olegvg-skills@olegvg-skills --scope project
# Независимый runtime-плагин ставится отдельно.
claude plugin install transcribing-audio@olegvg-skills --scope project

claude plugin marketplace update olegvg-skills
claude plugin update olegvg-skills@olegvg-skills --scope project
claude plugin update transcribing-audio@olegvg-skills --scope project
```

При установке отдельных групп обновляй соответствующую группу. После обновления
перезапусти Claude Code или выполни `/reload-plugins`. Интерактивные эквиваленты:
`/plugin marketplace add olegvg/olegvg-skills` и
`/plugin install <group>@olegvg-skills`.

Запуск checkout без установки:

```bash
claude --plugin-dir ./olegvg-skills
claude --plugin-dir ./olegvg-skills/plugins/transcribing-audio
```

KB-команды: `/kb-for-agents:kb-build` или `/olegvg-skills:kb-build`;
у `core-dev` нет command shims. Конкретные группы загружают нативные навыки;
umbrella сохраняет прежние KB shims. Аудио:
`/transcribing-audio:transcribing-audio /absolute/path/meeting.wav`.
См. [документацию Claude](https://code.claude.com/docs/en/plugins).

### Codex marketplace: удалённый, локальный, закреплённый

```bash
codex plugin marketplace add olegvg/olegvg-skills
codex plugin add olegvg-skills@olegvg-skills
codex plugin add transcribing-audio@olegvg-skills

# Подготовленный локальный checkout вместо удалённого источника.
codex plugin marketplace add ./olegvg-skills

# Либо закрепить существующий опубликованный тег удалённого marketplace.
codex plugin marketplace add olegvg/olegvg-skills --ref v0.8.0

# Обновить marketplace и кэши установленных плагинов.
codex plugin marketplace upgrade olegvg-skills
```

Выбери один источник marketplace. `marketplace upgrade` работает с Git-источниками;
для локального checkout обнови файлы и повтори `codex plugin add`, чтобы обновить
кэш плагина. После установки или обновления открой новую
сессию. Явные вызовы: `$olegvg-skills:kb-build`, `$olegvg-skills:kb-query`,
`$olegvg-skills:simplify-code`, `$transcribing-audio:transcribing-audio`.
Для установки отдельной группы в Codex используй Skills CLI с `--agent codex`.
См. [официальную документацию](https://developers.openai.com/plugins/build/plugins).

### Зависимости transcribing-audio

Отдельный аудиоплагин требует macOS или Linux, Python 3.13, `uv`, `ffmpeg` и
`ffprobe`. Для локальной диаризации нужен одобренный доступ Hugging Face через
`HF_TOKEN`. Первый запуск создаёт кэшируемую плагин-локальную `.venv`.
По умолчанию аудио остаётся локальным; OpenAI ASR требует явного согласия перед
отправкой любого фрагмента. Root-навыкам эти зависимости не нужны.

### ZIP и Claude Desktop

После публикации соответствующего релиза скачай архивы со страницы
[Releases](https://github.com/olegvg/olegvg-skills/releases).
`olegvg-skills-plugin-<version>.zip` содержит манифесты, root-навыки, команды,
документацию и независимый аудио-runtime. Распакуй и используй локальный
marketplace или `--plugin-dir`, как показано выше. Переносимый корневой
`plugin.json` использует Agent Plugins 1.0.0; манифесты Codex/Claude обеспечивают
совместимость с хостами.

Отдельные `<skill>-<version>.zip` содержат SKILL.md, все references, локальные
шаблоны/метаданные и LICENSE. Через desktop UI загружаются пять навыков:
`kb-build`, `kb-query`, `kb-refresh`, `kb-check-drift`, `simplify-code`.
Архивы `kb-record-decision` и `kb-maintain` предназначены для coding-агентов с
поддержкой планов, orchestration и необходимых соседних навыков.
`mobile-test-environments` требует хост с доступом к локальным устройствам/CLI и отдельно установленные SDK/драйверы. Аудио доступно
только вместе с полным runtime-плагином, отдельного skill-only ZIP для него нет.

В релиз входят notes, сгенерированный changelog и SHA256SUMS:

```bash
shasum -a 256 -c SHA256SUMS    # macOS; на Linux используй sha256sum
```

Локальная подготовка не публикует теги, архивы релиза или запись в каталоге.
Воспроизводимая сборка и проверки описаны в [release guide](docs/releasing.md).

## Быстрый старт

После установки `kb-for-agents` в Claude Code и выполнения `/reload-plugins` используй команды KB-навыков в сессии, открытой в корне вашего корпуса:

```
/kb-for-agents:kb-build .
/kb-for-agents:kb-query where are fees charged?
```

После того как вы внесли изменения в корпус:

```
/kb-for-agents:kb-check-drift
/kb-for-agents:kb-refresh src/billing/
```

Когда запланированная работа завершена и нужно сохранить её ключевые решения:

```
/kb-for-agents:kb-record-decision docs/plans/2026-03-19-1400/plan-billing-rewrite.md
```

После установки umbrella-плагина Codex начни новую сессию и используй эквивалентные skills:

```
$olegvg-skills:kb-build .
$olegvg-skills:kb-query where are fees charged?
$transcribing-audio:transcribing-audio /absolute/path/meeting.wav
```

Для мобильного окружения вызови `$mobile-test-environments` (или
`/core-dev:mobile-test-environments` в Claude-группе), например:
«Покажи Android-эмуляторы и виртуальные iPhone, не прерывая текущие тесты».
SDK и драйверы устанавливаются отдельно; навык не загружает их автоматически.

Для аудита неявных переходов состояний вызови `$audit-state-machines` после
установки отдельного навыка, `$olegvg-skills:audit-state-machines` в плагине Codex
или `/core-dev:audit-state-machines` в группе Claude Code. Открой сессию в корне
приложения и укажи модуль, если нужно сузить охват аудита.
Принципы проверки описаны в [обосновании скилла](docs/audit-state-machines.md).

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

## Приватность и сопровождение

См. [PRIVACY.md](PRIVACY.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md) и [release guide](docs/releasing.md).

## Лицензия

MIT. См. [LICENSE](LICENSE).
