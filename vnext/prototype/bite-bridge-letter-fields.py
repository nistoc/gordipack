#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-bridge-letter-fields.py — приёмка этапа Э7 (карточка #681): письма между контурами судятся
по полям «от кого / кому / ответ на», а не по имени файла.

═══ ЗАЧЕМ
Проверку писем соседей переделывали четыре раза (карточки #221, #242, #665, #673): второе слово имени
значило то автора, то адресата; ответ связывался с вопросом по подстроке темы; письмо соседа в нашей
папке по папке не отличить. Э7 даёт письму шапку (scripts/bridge_letter.py) и инструмент письма
(scripts/new-bridge-letter.py); guard-all.py и чтение ленты (sync_backoff.py) читают поля.
Черновик протокола и решения Р1–Р7 — goal-gordi-core/e7/letter-fields-draft.md, README набора §2.

═══ СЛУЧАИ (номера ①–⑧ — из черновика, §6)
  разбор шапки ...... Ш1 годная вторым · Ш2 блок первым — годна, но с предупреждением · Ш3 блок за
                      третьей непустой строкой — шапки нет · Ш4 черта markdown — не шапка · Ш5 начатая
                      и негодная — причины названы · Ш6 имя нового письма
  ⑧ ................. id с папкой разрешается ровно в одно письмо, хотя имя лежит в двух папках
  инструмент ........ И1 письмо ложится в нашу исходящую, шапка годна, первая строка не несёт «контура
                      <адресат>» · И2 ответ без reply-to — отказ · И3 имя занято — отказ, файл цел ·
                      И4 поправка к чужому письму — отказ · И5 проверка письма без шапки — код 2
  ① ................. вопрос с полями и ЛЖИВЫМ именем: старое имя в общей папке («ours» по имени) — судится
                      по полям как вопрос к нам; новое имя «к нам» с полями «к третьему» — не судится
  ② ................. два ответа двух ролей на один вопрос — оба целы, проверка называет оба
  ③ ................. ответ с полями, чья тема содержит тему другого вопроса, к чужому вопросу не прилип
  ④ ................. папка второго устройства (у onto обе стороны в одной): чтение ленты берёт соседа
                      и адресата из полей, своё письмо новостью не считает
  ⑥-В3 .............. поправка (fix) считается; поправка к чужому письму — предупреждение
  Р6 ................ письмо соседа без полей ПОСЛЕ его первого письма с полями — предупреждение;
                      более раннее — нет (встречный)
  негодная шапка .... называется и судится прежними правилами
  своё / чужое ...... письмо соседа с полями в НАШЕЙ папке — не «наше по папке», просит разбора
  ⑦ ................. переход: прежний разбор адресатов (_letter_addressees) и прежний признак своего письма
                      (_our_letter_sign) читают наше новое письмо верно
НАРОЧНЫЕ ПОЛОМКИ (каждая — в копии стенда, восстанавливается после прогона):
  П1 guard-all судит письма в папках соседа по имени (шапка не читается) ..... падают ① и ①б
  П2 сличение по теме не пропускает ответы с полями .......................... падает ③
  П3 guard-all судит письма в НАШЕЙ папке по имени ............................ падает «своё / чужое»
  П4 блок первым (⑦) и П5 «контура <адресат>» в первой строке (⑦б) — на тексте письма

═══ ГРАНИЦА, НАЗВАНА ПРЯМО
⑤ (старые письма: раздел моста до и после — построчно тот же) здесь НЕ судится: старой копии
guard-all.py в установке нет. Его держат прежние приёмки моста, прошедшие без правки случаев
(bite-neighbour-asks, bite-bridge-own-letters, bite-bridge-layouts, bite-answer-overwritten), и замер
на замороженной копии мест в документе выпуска. ⑥ (первое письмо потребителя с полями) — приёмка
у соседа, не здесь. Стенд guard-all — копия базы контура (как у соседних приёмок моста); перевод
на постоянные подставные данные — этап Э6. Базу соседа проверка не открывает: на стенде у соседа
только файл-признак контура.

    python <КОНТУР>/vnext-tools/bite-bridge-letter-fields.py
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402
import mezo_target  # noqa: E402

CASES = DIFFER = 0
DAY = 86400


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def load(path: Path, name: str):
    """Модуль из файла испытуемого каталога; его соседи ищутся там же."""
    folder = str(path.parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(path: Path, first_line: str, fields: dict | None, body: str = "текст письма",
          age_days: float = 0.0, block_first: bool = False) -> Path:
    """Письмо рукой приёмки, НЕ модулем шапки: лживые имена и поломки шапки модуль бы не построил."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = ""
    if fields is not None:
        block = "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items()) + "---\n"
    text = (block + first_line + "\n" if block_first else first_line + "\n" + block) + "\n" + body + "\n"
    path.write_text(text, encoding="utf-8")
    if age_days:
        stamp = time.time() - age_days * DAY
        os.utime(path, (stamp, stamp))
    return path


def build_guard_stand(root: Path) -> dict:
    """Наш контур «atlas» (копия испытуемого каталога + копия базы) и сосед «neigh» (каталог с
    файлом-признаком и папками моста). → словарь путей."""
    ours = root / "atlas"
    shutil.copytree(mezo_target.scripts_root(), ours / ".mezosync" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    mezo_stand.snapshot_db(mezo_paths.live_db(__file__), ours / ".mezosync" / "mezosync.db")
    theirs = root / "neigh"
    (theirs / ".mezosync").mkdir(parents=True)
    marker = sqlite3.connect(theirs / ".mezosync" / "mezosync.db")
    marker.execute("PRAGMA user_version = 1")
    marker.close()
    con = sqlite3.connect(ours / ".mezosync" / "mezosync.db")
    con.execute("INSERT INTO meta (key, value) VALUES ('group_name', 'atlas') "
                "ON CONFLICT(key) DO UPDATE SET value = 'atlas'")
    con.execute("DELETE FROM cross_links")
    con.execute("INSERT INTO cross_links (source_group, target_group, target_db_path, description)"
                " VALUES ('atlas','neigh',?,'проба Э7')", (str(theirs / ".mezosync" / "mezosync.db"),))
    # роль-автор случаев инструмента — на копии есть всегда: у свежего контура из выгрузки ролей может
    # не быть (init-group.py --roles COORD), и отказ «роли нет» выдал бы себя за провал случая
    con.execute("INSERT OR IGNORE INTO roles (role) VALUES ('PROTO')")
    con.commit()
    con.close()
    bridges = ours / "atlas.archs" / ".mezosync" / "bridges"
    return {"ours": ours, "theirs": theirs,
            "guard": ours / ".mezosync" / "scripts" / "guard-all.py",
            "tool": ours / ".mezosync" / "scripts" / "new-bridge-letter.py",
            "our_box": bridges / "atlas-neigh",
            "their_out": theirs / "neigh.archs" / ".mezosync" / "bridges" / "neigh-atlas",
            "their_shared": theirs / "neigh.archs" / ".mezosync" / "bridges" / "atlas-neigh-exchange"}


def run_guard(stand: dict) -> str:
    r = subprocess.run([sys.executable, str(stand["guard"]), "--full", "--skip", "drift,память,чтение ленты"],
                       capture_output=True, text=True, encoding="utf-8", timeout=600,
                       env=mezo_stand.stand_env(stand["ours"]))
    return (r.stdout or "") + (r.stderr or "")


def run_tool(stand: dict, *args) -> tuple:
    r = subprocess.run([sys.executable, str(stand["tool"]), *args],
                       capture_output=True, text=True, encoding="utf-8", timeout=120,
                       env=mezo_stand.stand_env(stand["ours"]))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def lines_with(out: str, *needles) -> list:
    return [ln.strip() for ln in out.splitlines() if all(n in ln for n in needles)]


def waiting_names(out: str) -> list:
    """Имена вопросов из перечня «без ответа» («   · neigh: <имя> — лежит N ч»)."""
    return [ln.strip()[len("· neigh: "):].split(" — лежит")[0]
            for ln in out.splitlines() if ln.strip().startswith("· neigh: ") and " — лежит" in ln]


def patched(path: Path, old: str, new: str):
    """Нарочная поломка в копии стенда: образец обязан встретиться ровно раз. → прежний текст или None."""
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        return None
    path.write_text(text.replace(old, new), encoding="utf-8")
    return text


def main() -> int:
    ok = True
    # испытуемые названы поимённо: нет файла — «не запустилась», а общий прогон видит, что испытано
    tested = [mezo_target.script("bridge_letter.py"), mezo_target.script("new-bridge-letter.py"),
              mezo_target.script("guard-all.py"), mezo_target.script("sync_backoff.py")]
    scripts = tested[0].parent
    print(f"⚖️ испытуется: {mezo_target.label()}")
    bl = load(mezo_target.script("bridge_letter.py"), "bridge_letter")
    tmp = mezo_stand.new("bite-e7-letters-")
    try:
        # ── РАЗБОР ШАПКИ ──────────────────────────────────────────────────────────────────────
        good = ("2026-10-13 09:30 UTC · пишет PROTO контура atlas, адресат — COORD@neigh\n---\n"
                "id: atlas:atlas-neigh/ask.neigh.t.20261013-0930\nfrom: PROTO@atlas\nto: COORD@neigh\n"
                "kind: ask\ndue: 2026-10-20\n---\n\nтекст\n")
        h = bl.parse_header(good)
        ok &= case("Ш1 годная шапка вторым — поля прочитаны",
                   h.valid and h.sender == ("PROTO", "atlas") and h.to == [("COORD", "neigh")]
                   and h.kind == "ask" and h.due == "2026-10-20" and not h.notes,
                   f"{h.describe()} · предупреждений {len(h.notes)}", differ=True)
        h = bl.parse_header("---\nid: a:b/c\nfrom: X@a\nto: Y@b\nkind: status\n---\nтекст\n")
        ok &= case("Ш2 блок ПЕРВЫМ — шапка годна, но названо, что прежний разбор у соседа её не прочтёт",
                   h.valid and any("первым" in n for n in h.notes), f"предупреждения: {h.notes}", differ=True)
        h = bl.parse_header("а\nб\nв\n---\nid: a:b/c\nfrom: X@a\nto: Y@b\nkind: ask\n---\n")
        ok &= case("Ш3 блок за третьей непустой строкой — шапки нет (Р1: окно три строки)",
                   not h.found, h.describe(), differ=True)
        h = bl.parse_header("# Заголовок\n---\nобычный текст после черты\n---\n")
        ok &= case("Ш4 черта markdown в начале — не шапка (первая строка за чертой — не поле)",
                   not h.found, h.describe(), differ=True)
        h = bl.parse_header("строка\n---\nid: x\nfrom: PROTO\nto: COORD@neigh\nkind: answer\n---\n")
        ok &= case("Ш5 начатая и негодная шапка — не «годна» и не «нет»: причины названы",
                   h.found and not h.valid and len(h.problems) == 3,
                   f"причины: {h.problems}", differ=True)
        from datetime import datetime, timezone
        name = bl.letter_name("answer", "neigh", "e7-fields", datetime(2026, 10, 13, 9, 5, tzinfo=timezone.utc))
        try:
            bl.letter_name("ask", "neigh", "с.точкой", datetime(2026, 10, 13, tzinfo=timezone.utc))
            dotted = "принято"
        except ValueError:
            dotted = "отказ"
        ok &= case("Ш6 имя нового письма: вид.адресат.тема.метка; тема с точкой — отказ",
                   name == "answer.neigh.e7-fields.20261013-0905.md" and dotted == "отказ",
                   f"{name} · тема с точкой: {dotted}", differ=True)

        # ── ⑧ id С ПАПКОЙ ─────────────────────────────────────────────────────────────────────
        p8 = tmp / "p8"
        a_box, t_box = p8 / "atlas-aia", p8 / "atlas-tapas"
        for box in (a_box, t_box):
            write(box / "card.proto.md", "старое письмо", None)
        places = {a_box: "atlas", t_box: "atlas"}
        one = bl.resolve_id("atlas:atlas-tapas/card.proto", places)
        none = bl.resolve_id("aia:atlas-tapas/card.proto", places)
        ok &= case("⑧ reply-to на старое письмо, имя которого есть в двух папках, разрешается ровно в одно",
                   one == [t_box / "card.proto.md"] and none == [],
                   f"atlas:atlas-tapas/card.proto → {[p.parent.name for p in one]} · "
                   f"тот же путь у другого контура-владельца → {len(none)}", differ=True)

        # ── ИНСТРУМЕНТ ПИСЬМА ─────────────────────────────────────────────────────────────────
        st = build_guard_stand(tmp / "tool")
        st["our_box"].mkdir(parents=True)
        body = tmp / "body.md"
        body.write_text("Вопрос по полям Э7.\n", encoding="utf-8")
        code, out = run_tool(st, "--role", "PROTO", "--to", "COORD@neigh", "--kind", "ask",
                             "--topic", "e7-probe", "--file", str(body))
        made = sorted(st["our_box"].glob("ask.neigh.e7-probe.*.md"))
        first = made[0].read_text(encoding="utf-8").splitlines()[0] if made else ""
        ccode, cout = run_tool(st, "--check", str(made[0])) if made else (None, "")
        ok &= case("И1 письмо легло в нашу исходящую «atlas-neigh», шапка годна; первая строка — «контура atlas», "
                   "адресат без «контура neigh»",
                   code == 0 and len(made) == 1 and ccode == 0 and "контура atlas" in first
                   and "контура neigh" not in first,
                   f"код {code} · файлов {len(made)} · проверка шапки код {ccode} · первая строка: «{first}»",
                   differ=True)
        code, out = run_tool(st, "--role", "PROTO", "--to", "COORD@neigh", "--kind", "answer",
                             "--topic", "e7-probe2", "--file", str(body))
        ok &= case("И2 ответ без --reply-to — отказ, письма нет",
                   code == 1 and not list(st["our_box"].glob("answer.*")),
                   (lines_with(out, "НЕ записано") or [out.strip()[:120]])[0], differ=True)
        dcode, dout = run_tool(st, "--role", "PROTO", "--to", "COORD@neigh", "--kind", "status",
                               "--topic", "e7-busy", "--file", str(body), "--dry-run")
        planned = [ln.split("легло бы в ", 1)[1].strip() for ln in dout.splitlines() if "легло бы в " in ln]
        busy_ok, busy_detail = False, "холостой прогон не назвал путь"
        if planned:
            target = Path(planned[0])
            target.write_text("чужое содержимое\n", encoding="utf-8")
            code, out = run_tool(st, "--role", "PROTO", "--to", "COORD@neigh", "--kind", "status",
                                 "--topic", "e7-busy", "--file", str(body))
            if code == 0:          # минута сменилась между вызовами — имя другое; повтор один раз
                for f in st["our_box"].glob("status.neigh.e7-busy.*.md"):
                    if f != target:
                        f.unlink()
                target = sorted(st["our_box"].glob("status.neigh.e7-busy.*.md"))[-1]
                target.write_text("чужое содержимое\n", encoding="utf-8")
                code, out = run_tool(st, "--role", "PROTO", "--to", "COORD@neigh", "--kind", "status",
                                     "--topic", "e7-busy", "--file", str(body))
            busy_ok = code == 1 and target.read_text(encoding="utf-8") == "чужое содержимое\n"
            busy_detail = f"код {code} · файл цел: {target.read_text(encoding='utf-8') == 'чужое содержимое' + chr(10)}"
        ok &= case("И3 имя занято — отказ, прежний файл не перезаписан (второй ответ не стирает первый)",
                   busy_ok, busy_detail, differ=True)
        code, out = run_tool(st, "--role", "PROTO", "--to", "COORD@neigh", "--kind", "fix",
                             "--topic", "e7-fix", "--reply-to", "neigh:neigh-atlas/ask.atlas.x", "--file", str(body))
        ok &= case("И4 поправка (fix) к письму другого контура — отказ (решение В3)",
                   code == 1 and "своему письму" in out, (lines_with(out, "НЕ записано") or [out[:120]])[0],
                   differ=True)
        plain = write(st["our_box"] / "answer.neigh.old.md", "старое письмо без шапки", None)
        code, out = run_tool(st, "--check", str(plain))
        ok &= case("И5 проверка письма без шапки — код 2 и слова «судят прежние правила»",
                   code == 2 and "прежние правила" in out, out.strip()[:140], differ=True)

        # ── guard-all НА СТЕНДЕ ───────────────────────────────────────────────────────────────
        g = build_guard_stand(tmp / "g")
        ob, to_, sh = g["our_box"], g["their_out"], g["their_shared"]
        q_fields = lambda lid, to="PROTO@atlas", kind="ask", sender="COORD@neigh": {  # noqa: E731
            "id": lid, "from": sender, "to": to, "kind": kind}
        # ① лживое старое имя в общей папке (по имени — «наше письмо»), по полям — вопрос нам
        write(sh / "ask.atlas-lying-old.md", "2026-10-01 10:00 UTC · вопрос соседа",
              q_fields("neigh:atlas-neigh-exchange/ask.atlas-lying-old"), age_days=10)
        # ①б новое имя «к нам», а по полям — к третьему контуру
        write(to_ / "ask.atlas.not-for-us.20261001-1000.md", "2026-10-01 10:00 UTC · вопрос третьему",
              q_fields("neigh:neigh-atlas/ask.atlas.not-for-us.20261001-1000", to="COORD@third"), age_days=10)
        # ② два ответа двух ролей на один вопрос с полями
        q2 = "neigh:neigh-atlas/ask.atlas.two-answers.20261001-1000"
        write(to_ / "ask.atlas.two-answers.20261001-1000.md", "вопрос", q_fields(q2), age_days=10)
        write(ob / "answer.neigh.two-answers.20261002-0900.md", "ответ PROTO",
              {"id": "atlas:atlas-neigh/answer.neigh.two-answers.20261002-0900", "from": "PROTO@atlas",
               "to": "COORD@neigh", "reply-to": q2, "kind": "answer"}, age_days=9)
        write(ob / "answer.neigh.two-answers.20261002-0905.md", "ответ COORD",
              {"id": "atlas:atlas-neigh/answer.neigh.two-answers.20261002-0905", "from": "COORD@atlas",
               "to": "COORD@neigh", "reply-to": q2, "kind": "answer"}, age_days=9)
        # ③ старый вопрос «roles» без полей и вопрос «roles-core» с полями; наш ответ с полями — на второй
        write(to_ / "ask.atlas.roles.md", "старый вопрос без полей", None, age_days=11)
        q3 = "neigh:neigh-atlas/ask.atlas.roles-core.20261001-1001"
        write(to_ / "ask.atlas.roles-core.20261001-1001.md", "вопрос", q_fields(q3), age_days=10)
        write(ob / "answer.neigh.roles-core.20261002-0910.md", "ответ на roles-core",
              {"id": "atlas:atlas-neigh/answer.neigh.roles-core.20261002-0910", "from": "PROTO@atlas",
               "to": "COORD@neigh", "reply-to": q3, "kind": "answer"}, age_days=9)
        # Р6: первое письмо соседа с полями — 10 суток назад (вопросы выше); без полей — 20, 11 и 5 суток назад
        write(to_ / "status.atlas.before-fields.md", "письмо соседа до полей", None, age_days=20)
        write(to_ / "status.atlas.after-fields.md", "письмо соседа после полей", None, age_days=5)
        # В3: наша поправка к своему письму и наша поправка к письму соседа
        write(ob / "fix.neigh.own.20261003-1000.md", "поправка к своему",
              {"id": "atlas:atlas-neigh/fix.neigh.own.20261003-1000", "from": "PROTO@atlas", "to": "COORD@neigh",
               "reply-to": "atlas:atlas-neigh/answer.neigh.two-answers.20261002-0900", "kind": "fix"}, age_days=8)
        write(ob / "fix.neigh.foreign.20261003-1001.md", "поправка к чужому",
              {"id": "atlas:atlas-neigh/fix.neigh.foreign.20261003-1001", "from": "PROTO@atlas",
               "to": "COORD@neigh", "reply-to": q2, "kind": "fix"}, age_days=8)
        # негодная шапка у вопроса с новым именем «к нам»: называется и судится прежним правилом
        write(to_ / "ask.atlas.bad-header.md", "вопрос с опечаткой в шапке",
              {"id": "neigh:neigh-atlas/ask.atlas.bad-header", "from": "COORD", "to": "PROTO@atlas",
               "kind": "ask"}, age_days=10)
        # своё / чужое: письмо соседа с полями в НАШЕЙ исходящей — свежее
        write(ob / "status.neigh.dropped-in-our-box.20261013-0800.md", "письмо соседа в нашей папке",
              {"id": "atlas:atlas-neigh/status.neigh.dropped-in-our-box.20261013-0800", "from": "COORD@neigh",
               "to": "PROTO@atlas", "kind": "status"})

        out = run_guard(g)
        waiting = waiting_names(out)
        reached = bool(lines_with(out, "📨 мост: писем с полями"))
        ok &= case("предпосылка: прогон дошёл до строки счёта писем с полями",
                   reached, (lines_with(out, "📨 мост") or ["строки нет"])[0][:160])
        ok &= case("① вопрос с полями под ЛЖИВЫМ старым именем (по имени — «наше письмо») судится по полям как вопрос нам",
                   "ask.atlas-lying-old.md" in waiting, f"без ответа: {waiting}", differ=True)
        ok &= case("①б новое имя «к нам», а поля — «к третьему»: вопросом нам НЕ судится",
                   "ask.atlas.not-for-us.20261001-1000.md" not in waiting, f"без ответа: {waiting}", differ=True)
        two = lines_with(out, "«ask.atlas.two-answers.20261001-1000.md» отвечен по полю reply-to")
        ok &= case("② два ответа двух ролей на один вопрос — оба целы и оба названы",
                   bool(two) and "20261002-0900" in two[0] and "20261002-0905" in two[0],
                   two[0][:200] if two else "строки «отвечен по полю» нет", differ=True)
        ok &= case("③ ответ с полями на «roles-core» НЕ прилип к старому вопросу «roles» с похожей темой",
                   "ask.atlas.roles.md" in waiting and "ask.atlas.roles-core.20261001-1001.md" not in waiting,
                   f"без ответа: {waiting}", differ=True)
        late = lines_with(out, "писем БЕЗ полей после первого письма с полями")
        ok &= case("Р6 письмо соседа без полей ПОСЛЕ его первого письма с полями — предупреждение; более раннее — нет",
                   bool(late) and "— 1:" in late[0] and "status.atlas.after-fields.md" in late[0],
                   late[0][:200] if late else "строки предупреждения нет", differ=True)
        census = lines_with(out, "📨 мост: писем с полями")
        fixes = lines_with(out, "поправка (fix) не к своему письму", "fix.neigh.foreign")
        ok &= case("⑥-В3 поправки посчитаны (2); поправка к письму соседа — предупреждение",
                   bool(census) and "писем-поправок — 2" in census[0] and len(fixes) == 1,
                   f"{census[0][:160] if census else 'нет строки'} · предупреждений о чужой поправке {len(fixes)}",
                   differ=True)
        bad = lines_with(out, "шапка негодна", "ask.atlas.bad-header.md")
        ok &= case("негодная шапка названа, а вопрос судится прежним правилом (он среди «без ответа»)",
                   bool(bad) and "ask.atlas.bad-header.md" in waiting,
                   f"{bad[0][:160] if bad else 'не названа'} · без ответа: {'да' if 'ask.atlas.bad-header.md' in waiting else 'нет'}",
                   differ=True)
        fresh = lines_with(out, "СВЕЖИХ записок БЕЗ РАЗБОРА")
        ok &= case("письмо соседа с полями в НАШЕЙ папке — не «наше по папке»: просит разбора",
                   bool(fresh) and "status.neigh.dropped-in-our-box.20261013-0800.md" in fresh[0],
                   fresh[0][:200] if fresh else "строки «без разбора» нет", differ=True)

        # П1: шапка в папках соседа не читается — судят имена
        guard = g["guard"]
        before = patched(guard, "                head = bridge_letter.read_header(ask)\n",
                         '                head = bridge_letter.parse_header("")\n')
        if before is None:
            print("⛔ НЕ ЗАПУСТИЛАСЬ: поломку П1 некуда вложить — образец не найден ровно один раз")
            return 2
        out_p1 = run_guard(g)
        guard.write_text(before, encoding="utf-8")
        w1 = waiting_names(out_p1)
        ok &= case("П1 поломка «папки соседа — по имени»: падают ① и ①б",
                   "ask.atlas-lying-old.md" not in w1 and "ask.atlas.not-for-us.20261001-1000.md" in w1,
                   f"без ответа под поломкой: {w1}", differ=True)
        # П2: сличение по теме не пропускает ответы с полями
        before = patched(guard, "and (_topic(o) in topic or topic in _topic(o)) and _plain(o)]",
                         "and (_topic(o) in topic or topic in _topic(o))]")
        if before is None:
            print("⛔ НЕ ЗАПУСТИЛАСЬ: поломку П2 некуда вложить — образец не найден ровно один раз")
            return 2
        out_p2 = run_guard(g)
        guard.write_text(before, encoding="utf-8")
        w2 = waiting_names(out_p2)
        ok &= case("П2 поломка «тема сличается и у ответов с полями»: падает ③ (старый вопрос «roles» отвечен чужим ответом)",
                   "ask.atlas.roles.md" not in w2, f"без ответа под поломкой: {w2}", differ=True)
        # П3: шапка в НАШЕЙ папке не читается — письмо соседа снова «наше по папке»
        before = patched(guard, "            head = bridge_letter.read_header(f)\n            if head.valid:\n"
                                "                sign = (",
                         "            head = bridge_letter.parse_header(\"\")\n            if head.valid:\n"
                         "                sign = (")
        if before is None:
            print("⛔ НЕ ЗАПУСТИЛАСЬ: поломку П3 некуда вложить — образец не найден ровно один раз")
            return 2
        out_p3 = run_guard(g)
        guard.write_text(before, encoding="utf-8")
        fresh3 = lines_with(out_p3, "СВЕЖИХ записок БЕЗ РАЗБОРА", "dropped-in-our-box")
        ok &= case("П3 поломка «наша папка — по папке»: письмо соседа снова «наше» и разбора не просит",
                   not fresh3, f"строк о нём: {len(fresh3)}", differ=True)

        # ── ④ ЧТЕНИЕ ЛЕНТЫ: ПАПКА ВТОРОГО УСТРОЙСТВА ───────────────────────────────────────────
        s4 = tmp / "s4"
        ours4 = s4 / "atlas" / ".mezosync"
        ours4.mkdir(parents=True)
        nb4 = s4 / "neigh"
        (nb4 / ".mezosync").mkdir(parents=True)
        sqlite3.connect(nb4 / ".mezosync" / "mezosync.db").close()
        db4 = ours4 / "mezosync.db"
        con = sqlite3.connect(db4)
        con.executescript("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);"
                          "CREATE TABLE cross_links (source_group TEXT, target_group TEXT, target_db_path TEXT);"
                          "CREATE TABLE roles (role TEXT); CREATE TABLE messages (id INTEGER, writer_role TEXT);"
                          "INSERT INTO meta VALUES ('group_name', 'atlas');"
                          "INSERT INTO roles VALUES ('PROTO'), ('COORD');")
        con.execute("INSERT INTO cross_links VALUES ('atlas', 'neigh', ?)", (str(nb4 / ".mezosync" / "mezosync.db"),))
        con.commit()
        box4 = nb4 / "bridges" / "atlas-neigh"
        write(box4 / "2026-10-13-to-proto.md", "письмо соседа", {"id": "neigh:atlas-neigh/2026-10-13-to-proto",
              "from": "COORD@neigh", "to": "PROTO@atlas", "kind": "ask"})
        write(box4 / "answer.neigh.ours.20261013-0900.md", "наше письмо в общей папке",
              {"id": "neigh:atlas-neigh/answer.neigh.ours.20261013-0900", "from": "PROTO@atlas",
               "to": "COORD@neigh", "reply-to": "neigh:atlas-neigh/2026-10-01-x", "kind": "answer"})
        write(box4 / "2026-10-13-to-third.md", "письмо соседа третьему", {"id": "neigh:atlas-neigh/2026-10-13-to-third",
              "from": "COORD@neigh", "to": "COORD@third", "kind": "status"})
        sb = load(scripts / "sync_backoff.py", "sync_backoff_e7")
        letters = sb._bridge_letters(con, db4, "PROTO", 0)
        con.close()
        by_file = {x["file"]: x for x in letters}
        mine = by_file.get("2026-10-13-to-proto.md", {})
        third = by_file.get("2026-10-13-to-third.md", {})
        ok &= case("④ папка второго устройства: сосед и адресат — из полей; наше письмо новостью не считается",
                   mine.get("neighbour") == "neigh" and mine.get("to_me") is True
                   and "answer.neigh.ours.20261013-0900.md" not in by_file
                   and third.get("to") == ["контур third"] and third.get("to_me") is False,
                   f"писем {len(letters)}: " + " · ".join(f"{k} → {v['neighbour']} {v['to']}" for k, v in by_file.items()),
                   differ=True)

        # ── ⑦ ПЕРЕХОД: ПРЕЖНИЙ РАЗБОР ЧИТАЕТ НАШЕ НОВОЕ ПИСЬМО ───────────────────────────────────
        when = datetime(2026, 10, 13, 9, 30, tzinfo=timezone.utc)
        text = bl.compose(when, ("PROTO", "atlas"), [("COORD", "neigh")], "ask",
                          "atlas:atlas-neigh/ask.neigh.t.20261013-0930", body="текст\n")
        p7 = tmp / "p7"
        new_letter = p7 / "atlas-neigh" / "ask.neigh.t.20261013-0930.md"
        new_letter.parent.mkdir(parents=True)
        new_letter.write_text(text, encoding="utf-8")
        old_addressees = sb._letter_addressees(new_letter, {"COORD", "PROTO"})
        source = (scripts / "guard-all.py").read_text(encoding="utf-8")
        start = source.index("    def _our_letter_sign(file)")
        end = source.index("    def _is_our_letter(", start)
        old_sign_src = "\n".join(ln[4:] if ln.startswith("    ") else ln for ln in source[start:end].splitlines())

        def old_sign(own: str):
            ns = {"Path": Path, "_own_name": own}
            exec(old_sign_src, ns)  # noqa: S102 — свой же исходник, функция прежнего признака
            return ns["_our_letter_sign"]
        ok &= case("⑦ прежний разбор адресатов (_letter_addressees) находит адресата нашего нового письма",
                   old_addressees == ["COORD"], f"адресаты: {old_addressees}", differ=True)
        ok &= case("⑦б прежний признак своего письма: у соседа — «не наше», у нас — «наше» по первой строке",
                   old_sign("neigh")(new_letter) is None and old_sign("atlas")(new_letter) == "line",
                   f"у соседа: {old_sign('neigh')(new_letter)} · у нас: {old_sign('atlas')(new_letter)}", differ=True)
        lines = text.splitlines()
        block_end = lines.index("---", 2)          # закрывающая черта блока (открывающая — вторая строка)
        first_block = "\n".join(lines[1:block_end + 1] + [lines[0]] + lines[block_end + 1:]) + "\n"
        # ⚖️ папка НЕ наша исходящая: там письмо «наше по папке» при любой первой строке, и поломка
        #    признака по строке была бы не видна (первая редакция случая на этом и споткнулась)
        broken = p7 / "mixed-exchange" / "ask.neigh.block-first.md"
        broken.parent.mkdir(parents=True)
        broken.write_text(first_block, encoding="utf-8")
        lost = sb._letter_addressees(broken, {"COORD", "PROTO"})
        ok &= case("П4 поломка «блок первым»: прежний разбор теряет адресата, наш прежний признак — автора",
                   lost == [] and old_sign("atlas")(broken) is None,
                   f"адресаты: {lost} · признак у нас: {old_sign('atlas')(broken)}", differ=True)
        their_line = p7 / "atlas-neigh" / "ask.neigh.their-line.md"
        their_line.write_text(text.replace("адресат — COORD@neigh", "адресат — COORD контура neigh"), encoding="utf-8")
        ok &= case("П5 поломка «контура <адресат>» в первой строке: прежний признак соседа считает письмо СВОИМ",
                   old_sign("neigh")(their_line) == "line", f"у соседа: {old_sign('neigh')(their_line)}", differ=True)
    finally:
        mezo_stand.release(tmp)

    print()
    print(f"⚖️ испытано: {mezo_target.label()}")
    print((f"✅ ПИСЬМА С ПОЛЯМИ (Э7) — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}" if ok
           else f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
