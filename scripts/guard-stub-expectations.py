r"""
guard-stub-expectations.py — ловит ЗАГЛУШКУ, ОБЕЩАЮЩУЮ ДЕЙСТВИЕ (в коде и в тестах).

ЗАЧЕМ (открытая дыра контура, 2026-07-23). За сутки ЗЕЛЁНОЕ состояние дважды защитило ложь:
канон три недели держал отменяющую саму себя оговорку, а тест ждал снекбар «Демо» КАК ОЖИДАЕМОЕ
поведение — гейт 814/814 был зелёным именно потому, что проверял неверный вопрос.

РАЗЛИЧЕНИЕ (TAXO #2476 ②):
  требует ПРИЗНАНИЯ в отсутствии данных — гард честности;
  требует ОБЕЩАНИЯ будущего действия  — цемент.
Уточнение TAXO #2481 ②, снимающее двусмысленность одинаковых текстов:
  **цемент — это обещание ВМЕСТО действия; гард — объяснение ВМЕСТО кнопки.**

⚠️ ВЕРСИЯ 2 — ПО ЗАМЕЧАНИЮ TAXO #2481 ③. v1 сканировала только `*.test.ts*` и была обманываема
удалением теста: тест уходит — гард зелёный, кнопка-обманка жива. Её формулировка:
  **гард, который смотрит на свидетеля, а не на подсудимого, охраняет не продукт, а протокол.**
Замер, доказавший это: стаб-ожиданий в тестах 5, стаб-маркеров в SRC 53, из них 18 ЖИВЫХ кнопок
`onClick → notify('Демо: …')`.

КАК РАЗЛИЧАЕТ В КОДЕ — ПО СТРУКТУРЕ, НЕ ПО СМЫСЛУ (граница TAXO #2481 ④, проверена ею на всех
18 кнопках и 35 признаниях, спорных случаев нет):
  стаб-текст ВНУТРИ обработчика (onClick/onConfirm/notify/setSnack/…)  → ОБЕЩАНИЕ → нужна метка;
  стаб-текст в текстовом узле (подпись, плашка, описание)              → ПРИЗНАНИЕ → не трогаем.
Признания — это и есть то, что мы защищаем; красное на них было бы шумом, после которого гард
перестают читать.

МЕТКИ (автор называет смысл сам — гард не угадывает за него):
  // HONESTY-GUARD: экран обязан признаться, что данных нет        ← вечная, снимать нельзя
  // STUB-EXPECTED: #40 — снять вместе с живой формой              ← ДОЛГ со сроком годности

⚠️ ЧЕГО ГАРД НЕ ЗНАЕТ И НЕ УГАДЫВАЕТ: какой роут канонный, а какой стабовый. Обещание на каноне
запрещено (§10.4), на стабовом лице законно по §8 — но роутер не зона знания гарда, и эвристика
здесь вернула бы ту же ложь, от которой мы ушли. ⇒ гард требует метку от ВСЕХ обещаний, а помеченные
печатает отдельным списком «долги со сроком годности»: их читает человек и возражает, если долг
заведён там, где его быть не должно.

⚠️ ЧЕГО НЕ ЛЕЧИТ ВОВСЕ (TAXO #2476 ④, ING #2479): текст канона через гейт не проходит; и есть
третий вид — ЧЕСТНО ОПИСАННЫЙ УЩЕРБ (документация не врёт, поведение соответствует, вред есть).
Последний ловится только вопросом «зачем мы это принимаем, если выбрасываем».

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/guard-stub-expectations.py           # exit 1, если есть обещания без меток
    python <КОНТУР>/.mezosync/scripts/guard-stub-expectations.py --list    # показать всё найденное с вердиктом
"""

import argparse
import re
import sys
from pathlib import Path

# 🪤 Путь в исходники НАШЕГО портала. В чужом контуре проверка либо молчала бы (каталога
# нет — и это читается как «заглушек нет»), либо мерила наш код. Выводим от контейнера.
_own = Path(__file__).resolve().parent.parent.parent
SPA_SRC = _own / "atlas.studio" / "Src" / "Atlas.Studio.Spa" / "src"

STUB_MARKERS = re.compile(r"Демо|заглушк|подключается|появится позже|в разработке", re.IGNORECASE)

# --- тесты: ожидание стаб-текста -------------------------------------------------
EXPECTATION = re.compile(r"\b(expect|findByText|getByText|queryByText|toContain|toHaveTextContent|toBe)\b")
NEGATIVE = re.compile(r"\.not\.|toBeNull\(\)")

# --- код: обещание действия ------------------------------------------------------
# Стаб-текст внутри обработчика/уведомления = обещание вместо действия.
HANDLER = re.compile(r"\bon[A-Z]\w*\s*=|\bon[A-Z]\w*:|notify\(|setSnack\(|enqueueSnackbar\(|toast\(|alert\(")

# --- ПРОХОД 2: структурный, БЕЗ словаря (TAXO #2486 ③) ---------------------------
# Словарь ловит только то, что НАЗВАЛО себя заглушкой; обещание себя называть не обязано.
# Замер TAXO: «обработчик → только уведомление» без сужения = 54 хита, половина — onClose(setSnack(null)),
# то есть закрытие всплывашки. Сужение до обработчиков ДЕЙСТВИЯ даёт 23 хита при 2 ложных.
ACTION_HANDLER = re.compile(r"\bon(Click|Confirm|Open\w*|Save|Submit|Apply)\s*=")
ONLY_NOTIFY = re.compile(r"(notify|setSnack|enqueueSnackbar|toast|alert)\s*\(")
# Закрытие всплывашки — служебный жест, а не подмена действия.
CLEARING = re.compile(r"(setSnack|notify)\s*\(\s*(null|undefined|''|\"\")\s*\)")
# «есть иное действие» — уведомление СОПРОВОЖДАЕТ, а не ПОДМЕНЯЕТ (отсечка TAXO):
OTHER_ACTION = re.compile(
    r"navigate\(|\bto=|component=\{?RouterLink|href=|window\.(open|location)|location\.|"
    r"mutate|refetch|\bawait\b|\bset(?!Snack\s*\(\s*null)[A-Z]\w*\s*\(|dispatch\(|onClose\(|\.then\("
)

MARK_HONESTY = re.compile(r"HONESTY-GUARD")
MARK_DEBT = re.compile(r"STUB-EXPECTED:\s*#\d+")

CONTEXT = 3


def verdict_for(lines, i):
    near = "\n".join(lines[max(0, i - CONTEXT): i + CONTEXT + 1])
    if MARK_HONESTY.search(near):
        return "honesty"
    if MARK_DEBT.search(near):
        return "debt"
    return "UNMARKED"


def scan():
    if not SPA_SRC.exists():
        return None, []
    findings = []
    for path in sorted(SPA_SRC.rglob("*.ts*")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        is_test = ".test." in path.name
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith(("//", "*", "/*")):
                continue
            if not STUB_MARKERS.search(line):
                continue

            if is_test:
                if not EXPECTATION.search(line) or NEGATIVE.search(line):
                    continue
                kind = "тест"
            else:
                # обещание = стаб-текст в обработчике; иначе это признание (текстовый узел)
                window = " ".join(lines[max(0, i - 1): i + 2])
                if not HANDLER.search(window):
                    continue
                kind = "код"

            findings.append((path, i + 1, kind, line.strip()[:100], verdict_for(lines, i)))

        # ── проход 2: структурный, без словаря ───────────────────────────────
        if is_test:
            continue
        for i, line in enumerate(lines):
            if not ACTION_HANDLER.search(line) or line.lstrip().startswith("//"):
                continue
            body = " ".join(lines[i: i + 3])          # обработчик обычно 1–3 строки
            if not ONLY_NOTIFY.search(body):
                continue
            if CLEARING.search(body):                 # setSnack(null) — закрытие всплывашки, не жест
                continue
            # Элемент осматриваем ЦЕЛИКОМ (±4 строки): `to=` и `component={RouterLink}` часто стоят
            # выше обработчика — окно только вниз объявляло живую ссылку цементом (ложное #2486 ③).
            element = " ".join(lines[max(0, i - 4): i + 4])
            if OTHER_ACTION.search(element):          # уведомление сопровождает действие — не цемент
                continue
            if any(f[0] == path and f[1] == i + 1 for f in findings):   # уже поймал словарь
                continue
            findings.append((path, i + 1, "код·структура", line.strip()[:100], verdict_for(lines, i)))
    return True, findings


def rel(path):
    try:
        return path.relative_to(SPA_SRC)
    except ValueError:
        return path


def main():
    ap = argparse.ArgumentParser(description="Гард: заглушка, обещающая действие.")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    exists, findings = scan()
    if exists is None:
        print("⏭️ SPA недоступна (нет atlas.studio) — проверка пропущена, НЕ зелёная")
        sys.exit(0)

    unmarked = [f for f in findings if f[4] == "UNMARKED"]
    debts = [f for f in findings if f[4] == "debt"]
    guards = [f for f in findings if f[4] == "honesty"]

    if args.list:
        for path, ln, kind, text, v in findings:
            mark = {"honesty": "🛡️ гард", "debt": "⏳ долг", "UNMARKED": "⛔ без метки"}[v]
            print(f"{mark:14} [{kind}] {rel(path)}:{ln}  {text}")
        print(f"\nвсего: {len(findings)} · без метки: {len(unmarked)} · "
              f"долгов: {len(debts)} · гардов честности: {len(guards)}")

    # Долги печатаем ВСЕГДА: метка не должна означать «забыли навсегда».
    if debts and not args.list:
        print(f"⏳ долгов со сроком годности: {len(debts)} — "
              + ", ".join(f"{rel(p)}:{ln}" for p, ln, _, _, _ in debts[:6]))

    if unmarked:
        print(f"⛔ обещаний заглушки БЕЗ метки: {len(unmarked)}")
        for path, ln, kind, text, _ in unmarked[:12]:
            print(f"   [{kind}] {rel(path)}:{ln}  {text}")
        print("   Назови смысл подписью рядом (±3 строки) — гард не угадывает за автора:")
        print("     // HONESTY-GUARD: экран обязан признаться, что данных нет")
        print("     // STUB-EXPECTED: #<задача> — снять вместе с <чем>")
        sys.exit(1)

    print(f"✅ обещаний заглушки {len(findings)}, все подписаны "
          f"(долгов {len(debts)}, гардов {len(guards)})")
    sys.exit(0)


if __name__ == "__main__":
    main()
