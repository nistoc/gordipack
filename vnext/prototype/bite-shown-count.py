"""
bite-shown-count.py — приёмка на правку ② : журнал выдач помнит, СКОЛЬКО ПОКАЗАЛ, и не врёт об этом.

═══ ЗАЧЕМ ПОЛЕ ═══
06.08 читалка показала мне 12 записок и отметила прочитанными 40. Расхождение существовало
ТОЛЬКО в моих глазах: `read_batches` хранил `token · role · last_id · issued_at` — сколько
было ПОКАЗАНО, там не было. Замер @opssre (#3123): проверить остальные роли нечем, и после
починки читалки мы не узнали бы, помогла ли она.

Слово владельца: 2026-08-07 10:00 UTC, «даю слово: ① и ② делаем». Рука — координатора.
Сделано им 10:21 UTC: колонки `shown_max` (сколько показано) и `acked_at` (вместо стирания).

═══ 🪤 ПОЧЕМУ ЭТОТ ФАЙЛ ПЕРЕПИСАН 2026-08-07 10:29 UTC — МОЯ ОШИБКА, НЕ ЕГО ═══
Первая версия требовала, чтобы РАСХОЖДЕНИЕ ПРОЯВИЛОСЬ: `shown_max < last_id`. Но координатор
починил ПРИЧИНУ (дефект перевыдачи, приёмка bite-r16-reissue.py) — и с этой минуты расхождения
не возникает вовсе: при перевыдаче `last_id` приводится к фактически показанному.
⇒ Укус требовал симптома от вылеченного организма и краснел на ВЕРНОЙ правке.
   Вердикт «ПОЛЕ ЕСТЬ, НО НЕ СПАСАЕТ» был ложным обвинением — поймано чтением его кода,
   а не доверием своему же выводу.

📌 Класс — мой собственный, названный мною же часом раньше в bite-r16-reissue.py:
   **красное, ставшее привычным, не читается.** Записал правило в один укус и тут же
   нарушил в соседнем. Проверка, вечно красная на исправном коде, ОПАСНЕЕ отсутствующей.

═══ ЧТО ПРОВЕРЯЕТСЯ ТЕПЕРЬ (свойства, а не симптом) ═══
    ① ПРАВДИВОСТЬ. `shown_max` равен НАИБОЛЬШЕМУ НОМЕРУ, РЕАЛЬНО НАПЕЧАТАННОМУ на экране.
       Сверка идёт с ВЫВОДОМ читалки, а не с соседним полем той же строки: поле, сверяемое
       с полем, доказывает лишь их согласие между собой, но не связь с действительностью.
    ② СОГЛАСОВАННОСТЬ. `last_id` (что подтвердится по токену) НЕ БОЛЬШЕ показанного.
       Это ровно то свойство, ради которого всё делалось: подтвердить непоказанное нельзя.
    ③ УЛИКА ПЕРЕЖИВАЕТ СОБЫТИЕ. Строка не стирается при подтверждении, а помечается
       (`acked_at`). Прежде она исчезала ровно в тот момент, когда расхождение и возникает —
       улика короче события, четвёртый экземпляр класса за сутки.
    ④ РАЗЛИЧАЮЩИЙ СЛУЧАЙ. Если подменить `shown_max` неверным числом — укус ОБЯЗАН покраснеть.
       Без этого он зелен и когда поле правдиво, и когда его никто не смотрит.

═══ ИМЯ КОЛОНКИ НЕ ЗАШИТО ═══
Как назвать поле — решает координатор. Укус ищет по смыслу и печатает, что нашёл: укус,
требующий конкретного имени, красил бы верную правку. (Найденное сегодня имя — `shown_max`.)

Запуск:  python <абсолютный путь>/bite-shown-count.py
Выход:   0 — все свойства держатся · 1 — поля ещё нет · 2 — поле есть, но свойство нарушено
"""

import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_db()
SANDBOX = Path.home() / ".mezosync-sandbox" / "bite-shown.db"
READER = mezo_target.script("read-messages.py")
ROLE = "PROTO"
START = 3069           # точка, с которой воспроизводится мой случай 06.08

# 🪤 ИМЯ ЗАШИТО НАМЕРЕННО — слово владельца 2026-08-07 13:26 UTC: «убери этот выбор колонки».
#    Прежде здесь стоял список кандидатов и бралась первая подошедшая: пока имя выбирал
#    координатор, это казалось вежливостью. Имя выбрано — `shown_max`, и вежливость стала
#    угадыванием. Цена угадывания замерена в тот же день: в соседнем скрипте «возьму
#    какую-нибудь колонку» молча подставило колонку адресата, сравнение строк оказалось
#    всегда истинным, и запрос напечатал 1808 записок за сутки при 1806 всего.
#    ⇒ Скрипт, не нашедший ТОЧНОГО имени, обязан падать. Падение видно, подмена — нет.
SHOWN_COL = "shown_max"


def prepare() -> None:
    """Копия живой базы. Живая НЕ ТРОГАЕТСЯ — у перископа и приёмок один закон."""
    SANDBOX.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, SANDBOX)
    con = sqlite3.connect(SANDBOX)
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (START, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()


def columns() -> list:
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    cols = [r[1] for r in con.execute("PRAGMA table_info(read_batches)")]
    con.close()
    return cols


def shown_column(cols: list):
    """Точное имя или ничего. Никакого «возьму похожее» — см. ловушку у SHOWN_COL."""
    return SHOWN_COL if SHOWN_COL in cols else None


def call_reader(*extra) -> str:
    out = subprocess.run([sys.executable, str(READER), "--db", str(SANDBOX),
                          "--role", ROLE, *extra],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def batch_row():
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM read_batches WHERE role=? ORDER BY rowid DESC LIMIT 1",
                      (ROLE,)).fetchone()
    con.close()
    return dict(row) if row else None


def shown_ids(text: str) -> list:
    """Номера, РЕАЛЬНО напечатанные на экране, — единственный источник правды об этом."""
    return [int(x) for x in re.findall(r"^--- #(\d+) \[", text, re.M)]


def parse_token(text: str):
    a = re.search(r"ПЕРВАЯ половина ([0-9a-f]{6})", text)
    b = re.search(r"--ack\s+<первая>-([0-9a-f]{6})", text)
    return (a.group(1), b.group(1)) if (a and b) else None


def check(name: str, col: str, out: str) -> bool:
    """Сверить поле с ЭКРАНОМ. Возвращает True, если поле сказало правду."""
    ids, row = shown_ids(out), batch_row()
    top = max(ids)
    truthful = row.get(col) == top
    consistent = row["last_id"] <= top
    print(f"   {name}: на экране {len(ids)} нот, старшая #{top}")
    print(f"      поле «показано» = {row.get(col)}   "
          f"{'✅ правда' if truthful else '🔴 ВРЁТ (на экране было #%d)' % top}")
    print(f"      подтвердится до = {row['last_id']}   "
          f"{'✅ не больше показанного' if consistent else '🔴 БОЛЬШЕ ПОКАЗАННОГО'}")
    return truthful and consistent


def main() -> int:
    print("ПРИЁМКА ②: журнал выдач помнит, сколько показал, и не врёт об этом")
    print(f"копия базы ..... {SANDBOX}\n")
    prepare()

    cols = columns()
    col = shown_column(cols)
    print(f"колонки журнала выдач: {cols}")
    if not col:
        print("колонка «показано» .... 🔴 НЕ НАЙДЕНА (искал среди "
              f"{', '.join(CANDIDATES[:5])} …)")
        print("\nИТОГ: ⏳ правки ещё нет — сверять нечего")
        return 1
    print(f"колонка «показано» .... найдена: {col!r}\n")

    # ── ① обычная выдача: поле обязано совпасть с экраном
    print("① ОБЫЧНАЯ ВЫДАЧА")
    plain_ok = check("обычная", col, call_reader("--limit", "12"))

    # ── ② перевыдача с УМЕНЬШЕННЫМ лимитом: мой случай 06.08, самый острый
    print("\n② ПЕРЕВЫДАЧА С УМЕНЬШЕННЫМ ЛИМИТОМ (мой случай 06.08)")
    prepare()
    call_reader("--limit", "40")
    small = call_reader("--limit", "12")
    reissue_ok = check("перевыдача", col, small)

    # ── ③ улика переживает подтверждение
    token = parse_token(small)
    survives = False
    if token:
        call_reader("--ack", f"{token[0]}-{token[1]}")
        after = batch_row()
        survives = after is not None
        marked = bool(after and after.get("acked_at"))
        print(f"\n③ ПОСЛЕ ПОДТВЕРЖДЕНИЯ строка журнала: "
              f"{'ЖИВА ✅' if survives else 'СТЁРТА 🔴'}"
              f"{' · помечена подтверждённой ✅' if marked else ''}")
        if not survives:
            print("   ⇒ улика исчезает в тот же миг, когда расхождение возникает")

    # ── ④ РАЗЛИЧАЮЩИЙ СЛУЧАЙ: подменяем поле — укус ОБЯЗАН покраснеть.
    #     Без него «зелено» означало бы лишь, что укус не смотрит.
    print("\n④ РАЗЛИЧАЮЩИЙ СЛУЧАЙ: портим поле в копии — проверка обязана заметить")
    prepare()
    out = call_reader("--limit", "12")
    con = sqlite3.connect(SANDBOX)
    con.execute(f"UPDATE read_batches SET {col} = {col} + 7 WHERE role=?", (ROLE,))
    con.commit()
    con.close()
    caught = not check("порченая", col, out)
    print(f"   {'✅ заметила — значит смотрит на экран, а не на соседнее поле' if caught else '🔴 НЕ ЗАМЕТИЛА — проверка слепая'}")

    # ── ИТОГ ────────────────────────────────────────────────────────────
    print("\nСВОЙСТВА: ① поле правдиво при обычной выдаче")
    print("          ② поле правдиво при перевыдаче, подтвердится не больше показанного")
    print("          ③ улика переживает подтверждение")
    print("          ④ порча поля обнаруживается")
    if not (plain_ok and reissue_ok and survives and caught):
        print(f"\nИТОГ: 🔴 СВОЙСТВО НАРУШЕНО — обычная={plain_ok} · перевыдача={reissue_ok} · "
              f"улика={survives} · различающий={caught}")
        return 2
    print("\nИТОГ: ✅ ВСЕ СВОЙСТВА ДЕРЖАТСЯ — поле говорит правду о том, что было на экране,")
    print("      подтверждается не больше показанного, улика живёт после подтверждения")
    return 0


if __name__ == "__main__":
    sys.exit(main())
