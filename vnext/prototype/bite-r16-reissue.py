"""
bite-r16-reissue.py — укус на дефект: ПЕРЕВЫДАННЫЙ БАТЧ ПОДТВЕРЖДАЕТ БОЛЬШЕ, ЧЕМ ПОКАЗАЛ.

═══ ЧТО ПРОИЗОШЛО СО МНОЙ 2026-08-06 18:26 UTC ═══
    вызов 1: read-messages.py --limit 40  → «40 нот, #3070…#3109», токен fea89a-…
    вызов 2: read-messages.py --limit 12  → «12 нот, #3070…#3081», ТОТ ЖЕ токен
                                            и приписка «--limit здесь ни при чём»
    ack по этому токену                   → отметка прочитанного 3069 → 3109
⇒ показано 12 записок, подтверждено 40. Двадцать восемь объявлены прочитанными,
  не будучи показанными НИ РАЗУ.

═══ ПОЧЕМУ ЭТО НЕ «САМ ВИНОВАТ» ═══
Роль обязана дочитать вывод целиком и подтвердить — я так и сделал. Вывод сам сказал
«12 нот, #3070…#3081» и сам предложил команду ack. Обе половины токена были на месте.
Никакого способа заметить расхождение из вывода НЕ БЫЛО: он честно называл 12 и молчал
про то, что подтвердит 40.

═══ ГДЕ ИМЕННО (read-messages.py, ветка R16) ═══
    rows   = выборка с новым LIMIT               ← уже усечена до 12
    kept   = [r for r in rows if r.id <= prev_last_id]   ← фильтр ТОЛЬКО СВЕРХУ
    token  = прежний (несёт prev_last_id = 3109)
    ack    → SELECT last_id FROM read_batches WHERE token=?   ← берёт 3109, не показанное

Комментарий в коде объясняет фильтр так:
    «Иначе ack сдвинул бы курсор на prev_last, а на экране было бы БОЛЬШЕ —
     роль подтвердила бы не то, что прочитала.»
Защита построена ровно от обратного случая. От «на экране МЕНЬШЕ» её нет: LIMIT режет
снизу, а фильтр смотрит сверху, и они не встречаются.

📌 Класс — мой собственный, из свода §7.3: «механизм есть и не делает того, что о нём
думают». Здесь в самой дорогой форме: механизм СОЗДАН ПРОТИВ ЭТОГО КЛАССА (R16 заводился,
чтобы роль не подтверждала непрочитанное) и допускает его же в другую сторону.

Укус зовёт НАСТОЯЩИЙ скрипт на КОПИИ живой базы, а не воспроизводит его логику своими
руками: реконструкция проверяла бы моё понимание кода, а не код.

Запуск:
    python <абсолютный путь>/bite-r16-reissue.py
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
SANDBOX = Path.home() / ".mezosync-sandbox" / "bite-r16.db"
READER = mezo_target.script("read-messages.py")
ROLE = "PROTO"
START_CURSOR = 3069


def prepare() -> None:
    """Копия живой базы + курсор на известную точку. Живая база НЕ ТРОГАЕТСЯ ВОВСЕ."""
    SANDBOX.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, SANDBOX)
    con = sqlite3.connect(SANDBOX)
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?",
                (START_CURSOR, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()


def call_reader(*extra) -> str:
    out = subprocess.run([sys.executable, str(READER), "--db", str(SANDBOX),
                          "--role", ROLE, *extra],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def cursor_now() -> int:
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    v = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                    (ROLE,)).fetchone()[0]
    con.close()
    return v


def parse_batch_header(text: str):
    """«[begin-of-batch] 12 нот, #3070…#3081» → (12, 3070, 3081)."""
    m = re.search(r"\[begin-of-batch\]\s+(\d+)\s+нот[^#]*#(\d+)\D+#(\d+)", text)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def parse_token(text: str):
    """Половинки: первая — в первой строке, вторая — в предложенной команде ack."""
    first = re.search(r"ПЕРВАЯ половина ([0-9a-f]{6})", text)
    second = re.search(r"--ack\s+<первая>-([0-9a-f]{6})", text)
    return (first.group(1), second.group(1)) if (first and second) else None


def shown_ids(text: str):
    return [int(x) for x in re.findall(r"^--- #(\d+) \[", text, re.M)]


def main() -> int:
    print("ПРИЁМКА: перевыданный батч подтверждает больше, чем показал")
    print(f"копия базы ..... {SANDBOX}")
    print(f"отметка прочитанного старт ... #{START_CURSOR}\n")
    prepare()

    # ── ① большой батч, НЕ подтверждаем (ровно то, что делает роль, когда вывод длинный)
    big = call_reader("--limit", "40")
    big_hdr, big_ids = parse_batch_header(big), shown_ids(big)
    print(f"① --limit 40 → заголовок {big_hdr}, показано записок {len(big_ids)}")

    # ── ② тот же ридер с МЕНЬШИМ лимитом: R16 перевыдаёт батч
    small = call_reader("--limit", "12")
    small_hdr, small_ids = parse_batch_header(small), shown_ids(small)
    token = parse_token(small)
    print(f"② --limit 12 → заголовок {small_hdr}, показано записок {len(small_ids)}")
    print(f"   перевыдача объявлена: {'ДА' if 'ПЕРЕВЫДАН' in small else 'нет'}")

    # ── ③ подтверждаем ТО, ЧТО ПОКАЗАНО — честно, целиком, обеими половинами
    ack_out = call_reader("--ack", f"{token[0]}-{token[1]}")
    after = cursor_now()
    print(f"③ ack {token[0]}-{token[1]} → {ack_out.strip()}")

    # ── ПРОВЕРКА СВОЙСТВА ──────────────────────────────────────────────────
    top_shown = max(small_ids)
    print("\nСВОЙСТВО: отметка прочитанного после подтверждения не должна уйти выше ПОКАЗАННОГО")
    print(f"   показано до .......... #{top_shown}")
    print(f"   отметка встала на ...... #{after}")
    lost = after - top_shown
    ok = after <= top_shown
    print(f"   {'✅ свойство держится' if ok else '❌ СВОЙСТВО НАРУШЕНО'}"
          f"{'' if ok else f': {lost} записок подтверждены не будучи показанными'}")

    # ── РАЗЛИЧАЮЩИЙ СЛУЧАЙ ─────────────────────────────────────────────────
    # Без него укус зелен и когда механизм исправен, и когда он вообще ничего не делает.
    # Тот же сценарий БЕЗ уменьшения лимита обязан дать курсор ровно на показанном.
    print("\nРАЗЛИЧАЮЩИЙ СЛУЧАЙ: тот же путь, но лимит НЕ уменьшается")
    prepare()
    a = call_reader("--limit", "12")
    tok_a = parse_token(a)
    ids_a = shown_ids(a)
    call_reader("--ack", f"{tok_a[0]}-{tok_a[1]}")
    after_a = cursor_now()
    same_ok = after_a == max(ids_a)
    print(f"   показано до #{max(ids_a)} · отметка #{after_a} · "
          f"{'✅ совпадает' if same_ok else '❌ расходится'}")
    print("   (если бы и здесь расходилось — приёмка ловила бы не перевыдачу, а что-то другое)")

    # ── СМЫСЛ ВЫХОДА ПЕРЕВЁРНУТ ПОСЛЕ ПОЧИНКИ 2026-08-07 10:05 UTC ────────
    # Пока дефект был жив, укус считал успехом ЕГО ВОСПРОИЗВЕДЕНИЕ: он доказывал,
    # что дефект есть. Координатор починил (`read-messages.py`, ack по batch_max) —
    # и с этой минуты укус меняет роль: он ПРОВЕРКА ПРОТИВ ВОЗВРАТА.
    # 🪤 Не перевернуть смысл значило бы оставить проверку, которая вечно красная
    #    на исправном коде. Такую перестают звать через неделю — и она молчит уже
    #    по-настоящему, когда дефект вернётся. Красное, ставшее привычным, не читается.
    if not (ok and same_ok):
        print(f"\nИТОГ: 🔴 ДЕФЕКТ ВЕРНУЛСЯ — свойство {'держится' if ok else 'НАРУШЕНО'} · "
              f"различающий случай {'прошёл' if same_ok else 'ПРОВАЛЕН'}")
        return 1
    print("\nИТОГ: ✅ СВОЙСТВО ДЕРЖИТСЯ — отметка не уходит выше показанного,")
    print("      различающий случай прошёл (значит приёмка мерит перевыдачу, а не что-то ещё)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
