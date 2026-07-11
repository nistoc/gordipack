# hooks/ — впрыск времени в контекст агента

Реализует универсальное правило [`timestamp-in-replies`](../rules/universal.sql):
каждый ответ агента начинается и заканчивается текущими локальными датой+временем,
чтобы владелец мог синхронизировать во времени чтение ответов разных агентов.

## Зачем hook, а не «просто попроси агента ставить время»

Агент **не знает** реального времени — модель не имеет часов. Единственный надёжный
источник — впрыск через hook. Два события:

| Hook | Впрыскивает | Когда |
|------|-------------|-------|
| `UserPromptSubmit` | `CURRENT_LOCAL_TIME=<yyyy-MM-dd HH:mm:ss K>` | в начале каждого хода |
| `PreToolUse` | `STEP_TIME=<HH:mm:ss>` | перед каждым вызовом инструмента (свежее!) |

Без hook агент выдумает время — и метки будут врать. Именно поэтому правило
`timestamp-in-replies` ссылается на этот файл: правило без скрипта не работает.

## Установка

1. Открой `~/.claude/settings.json` (создай, если нет).
2. Слей ключи `hooks.UserPromptSubmit` и `hooks.PreToolUse` из
   [`time-injection.json`](./time-injection.json) в свой `hooks`-блок
   (если у тебя уже есть массивы под этими событиями — **добавь**, не затирай).
3. Перезапусти чат. Проверь: в начале ответа агент печатает `🕐 <дата время>`.

## Платформа

Команды написаны под **PowerShell** (`"shell": "powershell"`, Windows/Claude Desktop).
На macOS/Linux замени `command` на date-эквивалент, например:

```bash
printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"CURRENT_LOCAL_TIME=%s. Print this exact time at the START of your reply, and print the current time again at the END."}}' "$(date '+%Y-%m-%d %H:%M:%S %z')"
```

## Замечание про Claude Desktop (Windows)

Встроенный UI-бейдж `showMessageTimestamps` на Claude Desktop для Windows **не
рендерится** — поэтому время печатается прямо в тексте ответа. На других клиентах
бейдж может дублировать метку; это не мешает.
