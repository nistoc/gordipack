# -*- coding: utf-8 -*-
"""Приёмка стены контура gordi — этап Э1, карточка 779.

Судит ДЕВЯТЬ критериев карточки. Семь из них машина проверяет сама, два остаются
человеку и названы в выводе прямо, а не умолчанием:
  ⑥ полный рабочий отрезок роли через стену — доказывается работой роли, не этим файлом;
  ⑨ приёмку подписывает роль, которая службу НЕ писала.

Две нарочные поломки (критерий ⑧) делаются КОПИЯМИ договора в черновом каталоге:
живые файлы приёмка не трогает.

Вызов:
    python check-wall.py --contours <манифест> [--exe <путь к gordi-wall.exe>] [--out <каталог проб>]

Исход: 0 — все машинные критерии прошли; 1 — хоть один провалился; 2 — проверять было нечем.
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.dirname(HERE)
CONTRACT = os.path.join(SERVICE, "contract", "gordi-contract.json")
DEFAULT_EXE = os.path.join(SERVICE, "GordiWall", "bin", "Debug", "net10.0", "gordi-wall.exe")

# Записанный ожидаемый состав договора. Меняется РУКОЙ, когда договор меняют нарочно:
# иначе «перечень вызовов тот же» нечем подтвердить — отпечаток пересчитается вместе с подменой.
EXPECTED_TOOL_COUNT = 12
EXPECTED_TOOLS_FINGERPRINT = "247dbfb31eaf"
TOOL_COUNT_RANGE = (8, 12)

CONTOUR_LIVE = "atlas"
CONTOUR_STAND = "atlas-stand"


class Verdict(object):
    """Итог одного критерия. Исход назван словом, а не кодом: код у приёмки один."""

    def __init__(self):
        self.rows = []

    def add(self, key, ok, title, detail):
        self.rows.append((key, bool(ok), title, detail))

    def failed(self):
        return [r for r in self.rows if not r[1]]

    def print_all(self):
        for key, ok, title, detail in self.rows:
            mark = "✅" if ok else "🔴"
            print("%s %s %s" % (mark, key, title))
            for line in detail.splitlines():
                print("      %s" % line)


class Wall(object):
    """Служба, поднятая по стандартному вводу-выводу. Один разговор — один экземпляр."""

    def __init__(self, exe, contract, contours, env_extra=None, read_only=False):
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        if env_extra:
            env.update(env_extra)
        argv = [exe, "serve", "--contract", contract, "--contours", contours]
        if read_only:
            argv.append("--read-only")
        self.p = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, encoding="utf-8", errors="replace", bufsize=1)
        self.next_id = 1
        self._send({"jsonrpc": "2.0", "id": self._id(), "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "check-wall", "version": "1"}}})
        self.init = self._recv()
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _id(self):
        v = self.next_id
        self.next_id += 1
        return v

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def _recv(self):
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError("служба закрыла вывод, не ответив. Поток ошибок: %s" % self.stderr_tail())
        return json.loads(line)

    def list_tools(self):
        self._send({"jsonrpc": "2.0", "id": self._id(), "method": "tools/list"})
        return self._recv()["result"]["tools"]

    def call(self, name, args):
        """Возвращает (структурный ответ, текст роли). Отказ службы — тоже ответ, не исключение."""
        self._send({"jsonrpc": "2.0", "id": self._id(), "method": "tools/call",
                    "params": {"name": name, "arguments": args}})
        answer = self._recv()
        if "error" in answer:
            return {"outcome": "ОШИБКА ПРОТОКОЛА", "error": answer["error"].get("message", "")}, ""
        res = answer["result"]
        text = ""
        for item in res.get("content") or []:
            if item.get("type") == "text":
                text += item.get("text") or ""
        return res.get("structuredContent") or {}, text

    def stderr_tail(self):
        try:
            self.p.stderr.flush()
        except Exception:
            pass
        return ""

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def read_json(path):
    return json.loads(io.open(path, encoding="utf-8").read())


def write_json(path, data):
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(data, ensure_ascii=False, indent=2))


def run_mode(exe, contract, contours, argv):
    """Однократный вызов мимо службы. Отдаёт код выхода, вывод и поток ошибок целиком."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    p = subprocess.run([exe, "run"] + argv + ["--contract", contract, "--contours", contours],
                       capture_output=True, encoding="utf-8", errors="replace", env=env, timeout=180)
    return p.returncode, p.stdout, p.stderr


def main():
    ap = argparse.ArgumentParser(description="приёмка стены контура gordi (этап Э1, карточка 779)")
    ap.add_argument("--contours", required=True, help="боевой манифест контуров этой машины")
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--contract", default=CONTRACT)
    ap.add_argument("--out", default=None, help="каталог для копий договора и манифеста (по умолчанию — временный)")
    args = ap.parse_args()

    if not os.path.exists(args.exe):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: сборки нет — %s" % args.exe)
        print("   собрать: dotnet build %s" % os.path.join(SERVICE, "GordiWall"))
        return 2
    if not os.path.exists(args.contract):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: договора нет — %s" % args.contract)
        return 2
    if not os.path.exists(args.contours):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: манифеста нет — %s" % args.contours)
        return 2

    work = args.out or tempfile.mkdtemp(prefix="check-wall-")
    if not os.path.isdir(work):
        os.makedirs(work)

    manifest = read_json(args.contours)
    stand = [c for c in manifest.get("contours", []) if c.get("id") == CONTOUR_STAND]
    if not stand:
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: в манифесте нет контура «%s» — пишущие пробы некуда вести." % CONTOUR_STAND)
        print("   Живую базу приёмка не пишет НАМЕРЕННО.")
        return 2
    if not os.path.exists(stand[0]["storage"]):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: копии базы нет — %s" % stand[0]["storage"])
        return 2

    v = Verdict()
    contract_doc = read_json(args.contract)

    # ─────────────────────────────────────── ① перечень вызовов из ОДНОГО файла
    code, out, err = run_mode(args.exe, args.contract, args.contours, ["contour_info", "--contour", CONTOUR_LIVE])
    tools_out = subprocess.run([args.exe, "tools", "--contract", args.contract, "--contours", args.contours],
                               capture_output=True, encoding="utf-8", errors="replace", timeout=120).stdout
    printed_count = None
    printed_fp = None
    for line in tools_out.splitlines():
        if line.startswith("вызовов "):
            printed_count = int(line.split()[-1])
        if line.startswith("отпечаток перечня"):
            printed_fp = line.split()[-1]

    w = Wall(args.exe, args.contract, args.contours)
    listed = w.list_tools()
    in_contract = len(contract_doc["tools"])
    ok1 = (printed_count == in_contract == len(listed) == EXPECTED_TOOL_COUNT
           and printed_fp == EXPECTED_TOOLS_FINGERPRINT
           and TOOL_COUNT_RANGE[0] <= in_contract <= TOOL_COUNT_RANGE[1])
    v.add("①", ok1, "перечень вызовов берётся из ОДНОГО файла договора",
          "в файле договора %d · служба объявила %d · перечень напечатал %s · ожидалось %d (предел %d–%d)\n"
          "отпечаток перечня %s · ожидался %s"
          % (in_contract, len(listed), printed_count, EXPECTED_TOOL_COUNT,
             TOOL_COUNT_RANGE[0], TOOL_COUNT_RANGE[1], printed_fp, EXPECTED_TOOLS_FINGERPRINT))

    # ─────────────────────────────────────── ⑤ вызов с ВЕРНЫМ контуром обязан пройти
    s5, t5 = w.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    ok5 = s5.get("outcome") == "passed" and len(t5) > 500 and s5.get("truncated") is False
    v.add("⑤", ok5, "встречный случай: вызов с верным контуром ПРОХОДИТ",
          "исход %s · усечено %s · знаков в ответе %d"
          % (s5.get("outcome"), s5.get("truncated"), len(t5)))

    # ─────────────────────────────────────── ③ контур приходит В ВЫЗОВЕ, без него — отказ
    s3a, t3a = w.call("memory_read", {"role": "PROTO", "section": "identity"})
    s3b, t3b = w.call("memory_read", {"contour": "atlas-typo", "role": "PROTO"})
    ok3 = (s3a.get("outcome") == "refused" and "contour" in (s3a.get("error") or "")
           and s3b.get("outcome") == "refused" and "atlas-typo" in (s3b.get("error") or ""))
    v.add("③", ok3, "контур передаётся В ВЫЗОВЕ; без него и с неизвестным именем — отказ",
          "без контура: %s — %s\nнеизвестный контур: %s — %s"
          % (s3a.get("outcome"), (s3a.get("error") or "")[:120],
             s3b.get("outcome"), (s3b.get("error") or "")[:120]))

    # ─────────────────────────────────────── ④ подмена переменных среды НЕ меняет поведение
    w_env = Wall(args.exe, args.contract, args.contours, env_extra={
        "MEZO_CONTAINER": "C:/нет-такого-контура",
        "MEZO_DB": "C:/нет-такой-базы/mezosync.db",
        "MEZO_ROLE": "COORD",
    })
    s4, t4 = w_env.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    w_env.close()
    ok4 = s4.get("outcome") == "passed" and t4 == t5
    v.add("④", ok4, "встречный случай: подмена MEZO_* НЕ меняет ответ",
          "исход %s · текст совпал со вызовом без подмены: %s (знаков %d против %d)"
          % (s4.get("outcome"), "ДА" if t4 == t5 else "НЕТ", len(t4), len(t5)))

    # ─────────────────────────────────────── ② типизированный исход и признак усечения
    # (а) расхождение состояния: версия раздела заведомо не та
    s2a, t2a = w.call("memory_save", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "state",
                                      "body": "проба приёмки стены — записана НЕ должна быть",
                                      "expect_version": 1})
    # (б) усечение: тот же вызов на манифесте с низким пределом знаков
    low = dict(manifest)
    low["limits"] = {"timeout_seconds": 120, "max_output_chars": 2000}
    low_path = os.path.join(work, "contours-low-limit.json")
    write_json(low_path, low)
    w_low = Wall(args.exe, args.contract, low_path)
    s2b, t2b = w_low.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    w_low.close()
    # (в) тело не на месте: копия договора с несуществующим файлом инструмента
    gone = json.loads(json.dumps(contract_doc))
    for t in gone["tools"]:
        if t["name"] == "rules_get":
            t["exec"]["script"] = "нет-такого-инструмента.py"
    gone_path = os.path.join(work, "contract-missing-body.json")
    write_json(gone_path, gone)
    w_gone = Wall(args.exe, gone_path, args.contours)
    s2c, t2c = w_gone.call("rules_get", {"contour": CONTOUR_LIVE, "list": True})
    w_gone.close()

    ok2 = (s2a.get("outcome") == "mismatch" and s2a.get("child_exit") not in (None, 0)
           and s2b.get("truncated") is True and "предел знаков" in (s2b.get("truncate_reason") or "")
           and s2c.get("outcome") == "not_started" and s2c.get("child_exit") is None)
    v.add("②", ok2, "исход — из закрытого перечня, усечение названо, код выхода НЕ договор",
          "расхождение состояния: исход %s, код тела %s\n"
          "усечение: признак %s, причина «%s», знаков %d\n"
          "тела нет на месте: исход %s, код тела %s (кода нет вовсе — судить по нему было бы нечем)"
          % (s2a.get("outcome"), s2a.get("child_exit"),
             s2b.get("truncated"), s2b.get("truncate_reason"), len(t2b),
             s2c.get("outcome"), s2c.get("child_exit")))

    # ─────────────────────────────────────── ⑦ режим только-чтение мимо службы
    code7r, out7r, err7r = run_mode(args.exe, args.contract, args.contours,
                                    ["memory_read", "--contour", CONTOUR_LIVE, "--role", "PROTO", "--section", "identity"])
    code7w, out7w, err7w = run_mode(args.exe, args.contract, args.contours,
                                    ["feed_write", "--contour", CONTOUR_STAND, "--role", "PROTO",
                                     "--to", "COORD", "--body", "проба приёмки"])
    w_ro = Wall(args.exe, args.contract, args.contours, read_only=True)
    s7, t7 = w_ro.call("feed_write", {"contour": CONTOUR_STAND, "role": "PROTO", "to": "COORD", "body": "проба"})
    w_ro.close()
    ok7 = ("МИМО службы" in err7r and code7r == 0 and "исход: прошло" in out7r
           and code7w == 4 and "отказ" in out7w
           and s7.get("outcome") == "refused")
    v.add("⑦", ok7, "мимо службы можно ЧИТАТЬ, и об этом сказано вслух; запись мимо службы — отказ",
          "чтение мимо службы: код %d, предупреждение в потоке ошибок: %s\n"
          "запись мимо службы: код %d, исход в тексте: %s\n"
          "служба в режиме только-чтение на запись: %s"
          % (code7r, "ДА" if "МИМО службы" in err7r else "НЕТ",
             code7w, out7w.splitlines()[0] if out7w else "(пусто)",
             s7.get("outcome")))

    # ─────────────────────────────────────── ⑧ две нарочные поломки
    # Поломка А: из копии договора убран один вызов ⇒ обязан провалиться РОВНО критерий ①
    broken_a = json.loads(json.dumps(contract_doc))
    broken_a["tools"] = [t for t in broken_a["tools"] if t["name"] != "owner_words_find"]
    path_a = os.path.join(work, "contract-broken-a.json")
    write_json(path_a, broken_a)
    tools_a = subprocess.run([args.exe, "tools", "--contract", path_a, "--contours", args.contours],
                             capture_output=True, encoding="utf-8", errors="replace", timeout=120).stdout
    fp_a = None
    count_a = None
    for line in tools_a.splitlines():
        if line.startswith("вызовов "):
            count_a = int(line.split()[-1])
        if line.startswith("отпечаток перечня"):
            fp_a = line.split()[-1]
    w_a = Wall(args.exe, path_a, args.contours)
    s_a, t_a = w_a.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    w_a.close()
    a_breaks_1 = (fp_a != EXPECTED_TOOLS_FINGERPRINT or count_a != EXPECTED_TOOL_COUNT)
    a_keeps_5 = s_a.get("outcome") == "passed"

    # Поломка Б: в копии договора стёрты признаки расхождения ⇒ обязан провалиться РОВНО критерий ②
    broken_b = json.loads(json.dumps(contract_doc))
    for t in broken_b["tools"]:
        if t["name"] == "memory_save":
            t["exec"]["mismatch_when"] = []
    path_b = os.path.join(work, "contract-broken-b.json")
    write_json(path_b, broken_b)
    w_b = Wall(args.exe, path_b, args.contours)
    s_b, t_b = w_b.call("memory_save", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "state",
                                        "body": "проба приёмки стены", "expect_version": 1})
    s_b5, t_b5 = w_b.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    w_b.close()
    b_breaks_2 = s_b.get("outcome") != "mismatch"
    b_keeps_5 = s_b5.get("outcome") == "passed"

    ok8 = a_breaks_1 and a_keeps_5 and b_breaks_2 and b_keeps_5
    v.add("⑧", ok8, "две нарочные поломки валят РОВНО свой критерий",
          "А (из договора убран один вызов): критерий ① провалился: %s (вызовов %s, отпечаток %s) · критерий ⑤ цел: %s\n"
          "Б (стёрты признаки расхождения): критерий ② провалился: %s (исход стал «%s» вместо «mismatch») · критерий ⑤ цел: %s"
          % ("ДА" if a_breaks_1 else "НЕТ", count_a, fp_a, "ДА" if a_keeps_5 else "НЕТ",
             "ДА" if b_breaks_2 else "НЕТ", s_b.get("outcome"), "ДА" if b_keeps_5 else "НЕТ"))

    w.close()

    # ─────────────────────────────────────── вывод
    print("── ПРИЁМКА СТЕНЫ КОНТУРА GORDI · этап Э1 · карточка 779")
    print("   сборка ... %s" % args.exe)
    print("   договор .. %s" % args.contract)
    print("   манифест . %s" % args.contours)
    print("   копии для поломок ... %s" % work)
    print("")
    v.print_all()
    print("")
    print("⚖️ ЭТИ ДВА КРИТЕРИЯ МАШИНА НЕ СУДИТ — говорю прямо, чтобы зелёное не прочлось шире:")
    print("   ⑥ полный рабочий отрезок роли через стену — доказывается работой роли (записка · память · карточка),")
    print("      а не этим файлом. Прогон приёмки отрезком НЕ является.")
    print("   ⑨ подпись приёмки ставит роль, которая службу НЕ писала. Свой прогон за чужую руку не считается.")
    print("")
    bad = v.failed()
    if bad:
        print("🔴 ПРОВАЛИЛОСЬ %d из %d: %s" % (len(bad), len(v.rows), " · ".join(r[0] for r in bad)))
        return 1
    print("✅ ВСЕ МАШИННЫЕ КРИТЕРИИ ПРОШЛИ: %d из %d (⑥ и ⑨ — за человеком)" % (len(v.rows), len(v.rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
