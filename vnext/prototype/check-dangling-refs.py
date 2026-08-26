"""
check-dangling-refs.py — ССЫЛКА, КОТОРУЮ НЕЛЬЗЯ РАЗРЕШИТЬ СНАРУЖИ.

═══ ПРАВИЛО ═══
`task-discipline` п.②-тер, слово владельца 2026-08-07 13:01 UTC:
    «разрешимую ссылку тоже делай обязательной, предупреждением»
Писать «карточка #N» или «записка #N». Голый «#N» неразличим В ПРИНЦИПЕ: номера записок
и карточек — ОДНО пространство, пересечение 62 из 62 (замер карточки #63). Читающий не может
понять, куда его послали, даже если очень захочет.

═══ ПОЧЕМУ ПРЕДУПРЕЖДЕНИЕ, А НЕ ОТКАЗ ═══
Выбор владельца, и он верен: отказ по регулярному выражению бил бы по законному тексту
(«миграция #038», перечисления, цитаты), а цена ошибки здесь мала — потерянная минута
читателя, не испорченные данные.
⛔ НО предупреждение обязано НАЗЫВАТЬ МЕСТА. «Есть неразрешимые ссылки» без перечня — то же
   молчание: его перестанут читать через неделю, и оно замолчит уже по-настоящему.
   Это записано в самом правиле и здесь исполняется буквально: строка, колонка, окрестность.

═══ 🪤 ОТКУДА ВЗЯЛСЯ ЭТОТ ФАЙЛ ═══
Та же проверка уже была написана внутри `measure-card-selfcontained.py` — и СОВРАЛА: в список
поясняющих слов попала сама решётка «#», из-за чего каждый голый «#3120» считался пояснённым
сам собою. Замер печатал «0 голых ссылок в 0 карточках» и НЕ МОГ напечатать иного ни при каких
данных. **Ложный ноль опаснее ошибки: он читается как чистота и закрывает вопрос.**
⇒ Логика вынесена СЮДА и живёт в одном месте. Две копии одного правила расходятся молча —
   а разошедшись, обе выглядят исправными.

Запуск:
    python check-dangling-refs.py --file нота.md          # перед записью
    python check-dangling-refs.py --text "…"              # быстрая проверка
    python check-dangling-refs.py --scan-cards            # размер беды в карточках
    python check-dangling-refs.py --scan-messages [--last 300]
Выход: 0 — предупреждение напечатано, но это НЕ отказ (умолчание правила)
       1 — с флагом --strict, если находки есть (для проверок и замеров)
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_db()

# Ссылка вида «#123». Отсекаем «##» и хвост слова, чтобы не ловить якоря и цвета.
REF = re.compile(r"(?<![\w#])#(\d{1,5})\b")

# Слово, ДЕЛАЮЩЕЕ ссылку разрешимой. Требуется НЕПОСРЕДСТВЕННО перед номером.
# ⛔ Сюда НЕЛЬЗЯ вносить саму решётку — именно это и породило ложный ноль (см. шапку).
# ⛔ Токен роли (COORD, TAXO…) поясняющим НЕ считается: «TAXO #2625» не отвечает на вопрос
#    «записка это или карточка», а лишь называет автора.
# ⚡ 10.08 06:36 UTC (#63): добавлены трек/инвариант/тест — ЗАМЕРОМ, не вкусом.
# Оговорка охвата из карточки оказалась ПРАВДОЙ: tracks (1…7), invariants (1…12),
# backlog_tests (1…2) сидят в ТОЙ ЖЕ полосе номеров, что и карточки, и в нотах уже
# живут 12 употреблений «тип #N» для них — форма честная, а список её не знал
# и предупреждал бы на правильном. Слово-тип и есть лекарство #63: оно снимает
# неоднозначность, которую величина номера снять не может.
EXPLAIN = re.compile(
    r"(?:карточк\w*|задач\w*|запис\w*|нот[аеуы]|бэклог\w*|шаг\w*|миграци\w*|коммит\w*"
    r"|релиз\w*|верси\w*|пункт\w*|строк\w*|порт\w*|тикет\w*|трек\w*|инвариант\w*"
    r"|тест\w*|issue|PR|MR)\s+#?\d{1,5}",
    re.I)


# УПОМИНАНИЕ, А НЕ УПОТРЕБЛЕНИЕ. Ссылка внутри «кавычек-ёлочек» или `обратных кавычек` —
# это ПРИМЕР ссылки, а не ссылка: «голый «#3120» считался пояснённым» никого никуда не шлёт.
# 📌 Общий принцип открыт карточкой #57: детектор, не отличающий употребление от упоминания,
#    даёт ложный цвет. Здесь он ложно-КРАСНЫЙ, и это не мелочь — предупреждение живёт
#    ровно до тех пор, пока не начало шуметь. Зашумевшее перестают читать, и тогда оно
#    молчит уже по-настоящему.
QUOTED = re.compile(r"«[^»]{0,80}»|`[^`]{0,80}`")


def find(text: str) -> list:
    """[(строка, колонка, «#N», окрестность)] — только НЕразрешимые и НЕ цитированные."""
    ok_at = {m.end() - len(re.search(r"#?\d{1,5}$", m.group(0)).group(0))
             for m in EXPLAIN.finditer(text)}
    quoted = [(m.start(), m.end()) for m in QUOTED.finditer(text)]
    out = []
    for m in REF.finditer(text):
        if m.start() in ok_at or m.start() + 1 in ok_at:
            continue
        if any(a < m.start() < b for a, b in quoted):
            continue
        line = text.count("\n", 0, m.start()) + 1
        col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
        lo, hi = max(0, m.start() - 45), min(len(text), m.end() + 45)
        around = text[lo:hi].replace("\n", " ⏎ ").strip()
        out.append((line, col, m.group(0), around))
    return out


def report(text: str, where: str, quiet: bool = False) -> int:
    hits = find(text)
    if not hits:
        if not quiet:
            print(f"✅ {where}: неразрешимых ссылок нет")
        return 0
    print(f"⚠️  {where}: неразрешимых ссылок — {len(hits)}")
    print("   «#N» неразличим: номера записок и карточек — одно пространство.")
    print("   Напиши «карточка #N» или «записка #N» — одно слово, и ссылку можно открыть.\n")
    for line, col, ref, around in hits:
        print(f"   строка {line}, позиция {col} — {ref}")
        print(f"      …{around}…")
    # ⚰️ Здесь стояло «чинится оно только СЕЙЧАС» — ложь по построению: строка печатается,
    # когда нота УЖЕ записана, и никакого «сейчас» у читающего нет (карточка #249).
    # Обещание невозможного учит не верить предупреждению целиком. И дата у слова
    # владельца обязана быть полной: «13:01 UTC» без числа читается как сегодняшнее —
    # автор этой правки сам так прочёл 26.08.
    print("\n   📌 Это ПРЕДУПРЕЖДЕНИЕ, а не отказ (слово владельца 07.08 13:01 UTC).")
    print("      Записанное задним числом НЕ переписывается — эти ссылки читатель со стороны")
    print("      уже не откроет. Лекарство только в СЛЕДУЮЩИХ нотах: слово-тип вплотную")
    print("      к номеру («карточка #N», «записка #N»). Проверить файл ДО отправки:")
    print(f"      python {Path(__file__).resolve().as_posix()} --file <нота.md>")
    return len(hits)


def scan(kind: str, last: int) -> int:
    con = sqlite3.connect(f"file:{LIVE.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    con.row_factory = sqlite3.Row
    if kind == "cards":
        rows = con.execute("SELECT id, role, title || char(10) || COALESCE(body_md,'') t "
                           "FROM backlog ORDER BY id DESC LIMIT ?", (last,)).fetchall()
        # 🪤 Падеж не украшение: строка печатается «неразрешимые ссылки в …», и форма
        #    «в карточек» — кривая надпись в инструменте, который ищет кривые надписи.
        what = "карточках"
    else:
        rows = con.execute("SELECT id, writer_role role, body_md t FROM messages "
                           "ORDER BY id DESC LIMIT ?", (last,)).fetchall()
        what = "записках"
    con.close()

    total, dirty, worst = 0, 0, []
    for r in rows:
        n = len(find(r["t"] or ""))
        total += n
        if n:
            dirty += 1
            worst.append((n, r["id"], r["role"]))
    print(f"ЗАМЕР: неразрешимые ссылки в {what}")
    print(f"  просмотрено ......... {len(rows)}")
    print(f"  с неразрешимыми ..... {dirty} ({round(dirty / max(1, len(rows)) * 100)}%)")
    print(f"  ссылок всего ........ {total}")
    if worst:
        worst.sort(reverse=True)
        print("  худшие:")
        for n, i, role in worst[:8]:
            print(f"    #{i:<5} {role:8} {n} шт.")
    print("\n📌 По правилу ③ старое задним числом НЕ переписываем. Это число — не долг к уплате,")
    print("   а цена уже пропущенного: столько ссылок читатель со стороны открыть не сможет")
    print("   никогда. Смысл предупреждения — чтобы завтра оно не выросло.")
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description="ссылки, неразрешимые вне породившего чата")
    ap.add_argument("--file", help="проверить файл (перед записью ноты или карточки)")
    ap.add_argument("--text", help="проверить строку")
    ap.add_argument("--scan-cards", action="store_true", help="замер по карточкам бэклога")
    ap.add_argument("--scan-messages", action="store_true", help="замер по ленте записок")
    ap.add_argument("--last", type=int, default=100, help="сколько последних брать при замере")
    ap.add_argument("--strict", action="store_true",
                    help="вернуть 1 при находках (для проверок; в обычной работе НЕ нужен — "
                         "правило требует предупреждения, а не отказа)")
    ap.add_argument("--quiet", action="store_true", help="молчать, если находок нет")
    args = ap.parse_args()

    if args.scan_cards or args.scan_messages:
        n = scan("cards" if args.scan_cards else "messages", args.last)
    elif args.file:
        p = Path(args.file)
        n = report(p.read_text(encoding="utf-8", errors="replace"), p.name, args.quiet)
    elif args.text is not None:
        n = report(args.text, "текст", args.quiet)
    else:
        ap.print_help()
        return 2
    return 1 if (args.strict and n) else 0


if __name__ == "__main__":
    sys.exit(main())
