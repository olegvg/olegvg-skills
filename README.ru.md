# OlegVG Skills

[English version](README.md)

Набор навыков для Claude Code, Codex и других агентов с поддержкой Vercel
Skills CLI. Помогает в новой сессии разобраться в проекте, проверить последствия
изменений и подтвердить результат на нужном мобильном устройстве. Для встреч
и интервью есть отдельный плагин, который делает расшифровки с метками спикеров.

## Какой навык выбрать

### KB for Agents

Группа `kb-for-agents` полезна, когда в разных сессиях приходится заново
разбираться, где реализовано поведение, как связаны модули и почему команда
приняла конкретное решение. Один раз собери карту проекта, затем обновляй
затронутые темы по истории Git.

| Навык | Когда использовать | Что получишь |
| --- | --- | --- |
| `kb-build` | Нужно разобраться в новом репозитории или архиве заметок. | Локальную `.kb/` с короткими индексами, саммари по темам и ссылками на первоисточники. |
| `kb-query` | Нужно найти реализацию, проследить поведение или понять причину выбора. | Ответ по нужным саммари, связанным решениям и файлам проекта. |
| `kb-check-drift` | Изменения уже в Git и нужно понять, где документация могла устареть. | Отчёт с подозрительными темами, битыми ссылками и поводами записать решения. |
| `kb-refresh` | Известно, какие изменения нужно отразить в базе. | Обновлённые саммари и индексы выбранных областей, отчёт и новая отметка актуальности по умолчанию. |
| `kb-record-decision` | В завершённом плане есть решение, к которому команда будет возвращаться. | Запись с причинами выбора, альтернативами, последствиями и связью с нужными саммари. |
| `kb-maintain` | Хочется оценить состояние базы и выполнить согласованные обновления за один проход. | Предложение по обслуживанию, пакетное обновление выбранных путей и итог по записям решений. |

[Сквозной сценарий KB](docs/kb-workflow.md) показывает все шесть навыков на
одном проекте. Формат базы описан в [трёхслойной модели](docs/concept.md) и
[шаблонах ручной сборки](templates/README.md).

### Core Dev

| Навык | Когда использовать | Что получишь |
| --- | --- | --- |
| [`deep-code-review`](docs/deep-code-review.md) | Нужно проверить, сохранил ли PR важный контракт, или провести аудит конкретного модуля. | Замечания с воспроизводимым сценарием, ссылками на код и пробелами покрытия. Десять методов охватывают контракты, данные, доступ, состояния, сбои и совместимость версий. |
| [`simplify-code`](skills/simplify-code/SKILL.md) | Рабочий diff дублирует существующие функции, усложняет ветвление или добавляет лишнюю работу. | Небольшие проверенные правки с сохранением задуманного поведения. |
| [`mobile-test-environments`](skills/mobile-test-environments/SKILL.md) | Поведение нужно проверить в Android/iOS, на реальном устройстве или в сессии Appium. | Инвентаризацию, настройку выбранного окружения, результаты проверки и точечную очистку ресурсов. |

Umbrella-плагин `olegvg-skills` включает обе группы. Например, перед слиянием
проверь рискованный diff, упрости безопасные участки и проверь нужный сценарий
на устройстве. После слияния обнови затронутые темы KB. Группы можно
устанавливать и использовать независимо.

### Расшифровка аудио

[Плагин `transcribing-audio`](plugins/transcribing-audio/skills/transcribing-audio/SKILL.md)
помогает искать и цитировать сказанное на встрече или подготовить субтитры.
Он распознаёт речь локально или через OpenAI, локально размечает спикеров,
сохраняет таймкоды слов и поддерживает возобновление. Плагин устанавливается
отдельно в Claude Code или Codex и включает собственный рантайм.

## Установка

Выбери один способ установки для каждого агента и workspace, чтобы не получить
дубли навыков. Root-навыки лежат в `skills/`; `transcribing-audio` устанавливается
отдельным плагином со своим Python runtime и не входит в umbrella.

### Skills CLI через Bun или Node.js

Запускай команды из нужного проекта. Используй Bun или Node.js 22.20+
с `npx`. Для Node.js замени `bunx` на `npx` в примерах ниже.

```bash
# Посмотреть удалённые или локальные навыки без установки.
bunx skills@latest add olegvg/olegvg-skills --list
bunx skills@latest add ./olegvg-skills --list

# Выбрать навыки и агентов; по умолчанию установка в текущий проект.
bunx skills@latest add olegvg/olegvg-skills --skill simplify-code --agent codex claude-code

# Установить KB-группу.
bunx skills@latest add olegvg/olegvg-skills --skill kb-build kb-query kb-refresh kb-check-drift kb-record-decision kb-maintain --agent codex

# Все root-навыки; интерактивно можно выбрать обе группы.
bunx skills@latest add olegvg/olegvg-skills --skill '*'

# Явная глобальная установка без вопросов.
bunx skills@latest add olegvg/olegvg-skills --skill simplify-code --agent codex --global --yes
```

Picker показывает `kb-for-agents` и `core-dev`; выбери обе группы для umbrella.
Skills CLI помещает полный каталог навыка с руководствами и шаблонами в
`.agents/skills/` и создаёт ссылки для агентов с отдельными каталогами skills.
Так устанавливаются переносимые навыки. Для обёрток совместимости Claude
или аудио-runtime используй установку плагина ниже.

После публикации соответствующего тега можно закрепить версию источника:

```bash
bunx skills@latest add https://github.com/olegvg/olegvg-skills/tree/v0.10.0 --skill deep-code-review --agent codex

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
codex plugin marketplace add olegvg/olegvg-skills --ref v0.10.0

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
`ffprobe`. Для локальной диаризации в обоих режимах нужен `HF_TOKEN`.
Для OpenAI ASR также нужны `OPENAI_API_KEY` и явное согласие на отправку аудио.
Передай учётные данные через `--env-file` или dotenv-файл плагина. При первом
запуске может создаваться локальная `.venv` внутри плагина. См.
[настройку рантайма](plugins/transcribing-audio/skills/transcribing-audio/references/runtime-and-backends.md).

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
`mobile-test-environments` требует доступа к устройствам и локальным CLI.
`deep-code-review` требует coding-агента с доступом к проверяемому diff или
участкам кода. Для аудио установи полный плагин, как описано выше.

В релиз входят notes, сгенерированный changelog и SHA256SUMS:

```bash
shasum -a 256 -c SHA256SUMS    # macOS; на Linux используй sha256sum
```

Локальная подготовка не публикует теги, архивы релиза или запись в каталоге.
Воспроизводимая сборка и проверки описаны в [release guide](docs/releasing.md).

## Быстрый старт

### Разберись в проекте и поддерживай базу актуальной

Открой сессию в корне корпуса. В Claude Code с группой `kb-for-agents` собери
базу и задай вопрос о проекте.

~~~text
/kb-for-agents:kb-build .
/kb-for-agents:kb-query Где планируются повторные попытки возврата?
~~~

После коммита проверь, где возник дрейф, и обнови затронутые разделы.
Если в завершённом плане есть важное решение, укажи путь к этому плану.

~~~text
/kb-for-agents:kb-check-drift
/kb-for-agents:kb-refresh src/billing/ src/workers/
/kb-for-agents:kb-record-decision planning/refund-retry.md
~~~

`/kb-for-agents:kb-maintain` предложит, что обновить, и выполнит выбранные
действия. В umbrella-плагине Codex используй имена
`$olegvg-skills:kb-build`, `$olegvg-skills:kb-query` и так далее. Входные
данные, результаты и варианты запуска разобраны в [сценарии KB](docs/kb-workflow.md).

### Проверь diff, упрости код или запусти мобильную проверку

| Задача | Пример запроса |
| --- | --- |
| Проверить повторы в PR | «Используй `deep-code-review` для ревью PR относительно main. Проверь, что произойдёт при повторе задачи после успешного ответа провайдера». |
| Упростить рабочий diff | «Используй `simplify-code` для этого diff. Сохрани поведение и запусти целевые тесты». |
| Проверить сценарий на устройстве | «Используй `mobile-test-environments`, найди запущенный Android-эмулятор и проверь форму с открытой экранной клавиатурой». |

При отдельной установке достаточно назвать навык. В плагинах можно вызвать
его по полному имени, например `/core-dev:deep-code-review` в Claude Code
или `$olegvg-skills:deep-code-review` в Codex. Все методы и примеры их
совместного применения описаны в [руководстве по ревью](docs/deep-code-review.md#methods-and-references).

### Расшифруй запись

После установки отдельного плагина используй
`/transcribing-audio:transcribing-audio /absolute/path/meeting.wav` в Claude Code
или `$transcribing-audio:transcribing-audio /absolute/path/meeting.wav` в Codex.
Выбери режим распознавания и способ задать число спикеров.

## Требования

- Агент с поддержкой skills. Выше описана установка в Claude Code, Codex и
  другие среды через Skills CLI.
- Для навыков KB нужен корпус. `kb-refresh` и `kb-check-drift` требуют историю
  Git. Сборка и поиск работают и для корпуса без Git.

## Приватность и сопровождение

См. [PRIVACY.md](PRIVACY.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md) и [release guide](docs/releasing.md).

## Лицензия

MIT. См. [LICENSE](LICENSE).
