#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ОДНА команда живости перископа — ТРИ исхода, сквозной путь до данных.

ПОВОД (карточка #167, замер 2026-08-10 15:11 UTC). Перископ был жив НАПОЛОВИНУ: клиент
рисовал страницу, служба не слушала никто, PID-файл называл мёртвые номера — и снаружи
ВСЁ выглядело работающим. Класс: половина механизма, оставшаяся живой, выглядит живым
механизмом; открытый порт «работает» ровно в меру того, что он открытый порт.

ИСХОДЫ (и коды выхода — зелёного на половине НЕ бывает):
  0 — ЖИВ ЦЕЛИКОМ: клиент отвечает И данные доходят СКВОЗЬ клиентский прокси
      (клиент → прокси → служба → база), а не «порт открыт»;
  2 — ЖИВА ТОЛЬКО ОБОЛОЧКА: страница открывается, данных за ней нет;
  3 — МЁРТВ: клиент не отвечает (если служба при этом жива — сказано строкой).

PID-файлы НЕ ПИШУТСЯ и НЕ ЧИТАЮТСЯ как источник правды: писателя у них в коде нет,
мёртвый номер в файле выдаёт себя за живой. Живость спрашивается у СИСТЕМЫ (HTTP),
а лежащий рядом .pid с мёртвым номером эта команда называет лжецом отдельной строкой.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

CLIENT = "http://localhost:5173"
API = "http://localhost:5177"
RUN_DIR = Path(__file__).resolve().parent / ".run"
TIMEOUT = 4


def http(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return r.status, r.read(4096).decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def pid_alive(pid: int) -> bool:
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                       capture_output=True, text=True)
    return str(pid) in (r.stdout or "")


def main() -> int:
    c_st, _ = http(CLIENT + "/")
    p_st, p_body = http(CLIENT + "/api/health")     # СКВОЗНОЙ путь: через прокси клиента
    if p_st != 200:
        # Один повтор: первый запрос сквозь прокси после подъёма греется дольше таймаута,
        # и без повтора команда звала бы РАБОЧИЙ перископ полумёртвым (поймано прогоном 14.08).
        p_st, p_body = http(CLIENT + "/api/health")
    a_st, _ = http(API + "/api/health")             # служба напрямую — для диагноза

    # PID-файлы: не источник правды, но лежащий лжец называется вслух.
    for pf in sorted(RUN_DIR.glob("*.pid")) if RUN_DIR.exists() else []:
        for line in pf.read_text(encoding="utf-8", errors="replace").splitlines():
            head = line.split("#")[0].strip()
            if "=" in head:
                num = head.split("=")[1].strip()
                if num.isdigit() and not pid_alive(int(num)):
                    print(f"⚠️  {pf.name}: номер {num} МЁРТВ — файл лжёт, источник правды HTTP ниже")

    data_ok = p_st == 200 and '"' in p_body and "Error" not in p_body[:200]
    if data_ok:
        try:
            j = json.loads(p_body)
            detail = f"readOnly={j.get('readOnly')}"
        except Exception:
            detail = "ответ не JSON — данными не считается"
            data_ok = False
    if c_st == 200 and data_ok:
        print(f"✅ ЖИВ ЦЕЛИКОМ: клиент {CLIENT} отвечает, данные идут СКВОЗЬ прокси ({detail})")
        return 0
    if c_st == 200:
        print(f"🔴 ЖИВА ТОЛЬКО ОБОЛОЧКА: страница открывается, но /api/health через прокси — {p_body[:80]}")
        print(f"   служба напрямую: {'отвечает ' + str(a_st) if a_st else 'НЕ отвечает'} — "
              f"{'прокси смотрит мимо' if a_st == 200 else 'подними: dotnet run --project src/Gordi.Periscope.Api -- --db <путь>'}")
        return 2
    print(f"⚫ МЁРТВ: клиент {CLIENT} не отвечает"
          + (f" (служба при этом ЖИВА на {API} — лица нет)" if a_st == 200 else " (служба тоже молчит)"))
    return 3


if __name__ == "__main__":
    sys.exit(main())
