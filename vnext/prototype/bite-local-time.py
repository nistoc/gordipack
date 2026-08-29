# -*- coding: utf-8 -*-
"""Приёмка карточки #384: показ «<час> UTC (<час> местное)» модулем local_time.py.

Судит МОДУЛЬ (единственное место конвертации) различающими и встречными случаями;
живой показ пятью инструментами проверяется отдельным живым вызовом (см. тело карточки).
Зона в опытах ①–④ подставляется ПАРАМЕТРОМ — это и есть обратный ход «подменённая зона
меняет скобки»; зона host OS судится случаем ⑤ без подмены.
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / ".mezosync" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from local_time import utc_to_local  # noqa: E402

try:
    from zoneinfo import ZoneInfo
    MADRID = ZoneInfo("Europe/Madrid")
    TOKYO = ZoneInfo("Asia/Tokyo")
except Exception:  # noqa: BLE001
    print("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: нет базы часовых зон (zoneinfo/tzdata) — "
          "случаи лето/зима и подмены зоны судить нечем")
    sys.exit(1)

ok = red = 0


def case(name, got, want, why):
    global ok, red
    if got == want:
        ok += 1
        print(f"✅ {name}")
        print(f"   {why}")
    else:
        red += 1
        print(f"🔴 {name}")
        print(f"   ждал: {want!r}")
        print(f"   получил: {got!r}")
        print(f"   {why}")


# ① лето/зима ОДНОЙ зоны: смещение обязано считаться на ДАТУ ЗАПИСИ, не хардкодом
case("① летняя дата, зона Мадрид → +2",
     utc_to_local("2026-08-15 12:00:00", tz=MADRID),
     "2026-08-15 12:00:00 UTC (14:00 местное)",
     "хардкод +02:00 прошёл бы этот случай — его валит ②")
case("② зимняя дата, ТА ЖЕ зона → +1",
     utc_to_local("2026-01-15 12:00:00", tz=MADRID),
     "2026-01-15 12:00:00 UTC (13:00 местное)",
     "смещение взято на дату записи: зимой час другой — хардкод соврал бы молча")

# ③ обратный ход: подменённая зона МЕНЯЕТ скобки
case("③ та же метка, зона Токио → скобки другие",
     utc_to_local("2026-08-15 12:00:00", tz=TOKYO),
     "2026-08-15 12:00:00 UTC (21:00 местное)",
     "скобки зависят от зоны ⇒ правка действительно считает, а не приписывает строку")

# ④ перенос суток: местный час без даты соврал бы «раньше полуночи»
case("④ 23:30 UTC, Мадрид летом → следующие сутки названы датой",
     utc_to_local("2026-08-15 23:30:00", tz=MADRID),
     "2026-08-15 23:30:00 UTC (16.08 01:30 местное)",
     "01:30 без даты читалось бы как час ТОЙ ЖЕ ночи до записи")

# ⑤ зона host OS (боевой путь, tz не подставлен): формат цел, скобки есть
got5 = utc_to_local("2026-08-15 12:00:00")
if got5.startswith("2026-08-15 12:00:00 UTC (") and got5.endswith(" местное)"):
    ok += 1
    print("✅ ⑤ зона host OS: «<как было> UTC (<час> местное)» — формат цел")
    print(f"   на этой машине: {got5!r} — час в скобках дал host OS, не хардкод")
else:
    red += 1
    print(f"🔴 ⑤ зона host OS: формат сломан — получил {got5!r}")

# ⑥ встречные на честность краёв: пусто и мусор скобками НЕ обрастают
case("⑥ пустая метка → «—»", utc_to_local(""), "—",
     "пустоту не превращаем в час")
case("⑥-бис мусор → «<как было> UTC» БЕЗ скобок", utc_to_local("вчера"), "вчера UTC",
     "лгать скобками хуже, чем не показать местное")

# ⑦ конвертация не расползлась: astimezone в коде инструментов — ТОЛЬКО в local_time.py
r = subprocess.run([sys.executable, str(SCRIPTS / "guard-utc.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode == 0 and "Разрешено поимённо (local_time.py" in r.stdout:
    ok += 1
    print("✅ ⑦ guard-utc: чисто, разрешение НАЗВАНО вслух (не молчаливый пропуск)")
elif r.returncode == 0:
    red += 1
    print("🔴 ⑦ guard-utc зелёный, но строки «Разрешено поимённо» НЕТ — "
          "разрешение стало молчаливым, это класс «исключающий фильтр опаснее отсутствия»")
else:
    red += 1
    print("🔴 ⑦ guard-utc красный — конвертация есть где-то КРОМЕ local_time.py:")
    print("   " + (r.stdout or r.stderr).strip()[-400:])

# ⑧ пять инструментов зовут ОБЩИЙ модуль, своих конвертаций не держат
FIVE = ["read-messages.py", "backlog.py", "read-broadcasts.py", "stats.py", "check-errors.py"]
bad = []
for name in FIVE:
    body = (SCRIPTS / name).read_text(encoding="utf-8", errors="replace")
    if "from local_time import" not in body:
        bad.append(f"{name}: не зовёт local_time")
    if "astimezone" in body:
        bad.append(f"{name}: своя конвертация — расползание")
if bad:
    red += 1
    print("🔴 ⑧ пять инструментов: " + " · ".join(bad))
else:
    ok += 1
    print("✅ ⑧ все пять зовут общий модуль, своей конвертации ни у одного")

print(f"\n{'🔴 НЕ ПРИНЯТ' if red else '✅ ПРИНЯТ'} — зелёных {ok} · красных {red}")
sys.exit(1 if red else 0)
