#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА: команда, берущая предмет ПО ПОЛОЖЕНИЮ, не захватывает чужое (карточка #218 ②③).

🩸 ОПЛАЧЕНО ДВАЖДЫ: `git add -A` унёс 4 файла соседней роли (29.07) · правка последнего
коммита пришлась на коммит другой роли, легший между двумя попытками (18.08, 26 секунд).

⚖️ ПРИЗНАК НЕ «АВТОР HEAD НЕ ТЫ» — под одним именем коммитят все роли (замер @TAXO #3675),
и такая проверка смолчала бы ровно в том случае, ради которого заводится. Здесь проверяется,
что механизм различает СОСТАВОМ и ВОЗРАСТОМ, а не именем.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① правка СВОЕГО последнего коммита — проходит                             (прогон «своя»)
  ② правка ПОСЛЕ чужого коммита — отказ, называющий ЧТО в нём               РАЗЛИЧАЮЩИЙ
  ③ отказ ② НЕ ссылается на автора (все роли под одним именем)              РАЗЛИЧАЮЩИЙ
  ④ смена ещё не коммитила — отказ «НЕ ЗНАЮ», отличный от «чужой»           РАЗЛИЧАЮЩИЙ
  ⑤ «всё вокруг» при чужих незаписанных файлах — отказ, файлы ПОИМЁННО      РАЗЛИЧАЮЩИЙ
  ⑥ ВСТРЕЧНЫЙ: те же файлы, но записанные ЭТОЙ сменой — проходит            РАЗЛИЧАЮЩИЙ
  ⑦ ВСТРЕЧНЫЙ: чистое дерево — «всё вокруг» проходит                        РАЗЛИЧАЮЩИЙ
  ⑧ поимённое добавление не трогается никогда                               РАЗЛИЧАЮЩИЙ
  ⑨ репозиторий ВНЕ контура — не наш предмет, молчим                        РАЗЛИЧАЮЩИЙ
  ⑩ `git stash list` (безвредный) не путается со `stash` (забирает всё)     РАЗЛИЧАЮЩИЙ
  ⑪ слово выключения гасит, опечатка в нём — НЕ гасит                       РАЗЛИЧАЮЩИЙ

⛔ Живого контура не касается: хранилища и журнал смены — во временном каталоге.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import time

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

МЕХАНИЗМ = pathlib.Path(__file__).resolve().parent / "hook-shared-repo-guard.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def git(корень, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Один Общий", GIT_AUTHOR_EMAIL="one@shared",
               GIT_COMMITTER_NAME="Один Общий", GIT_COMMITTER_EMAIL="one@shared")
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    return subprocess.run(["git", "-C", str(корень), *args], capture_output=True,
                          text=True, encoding="utf-8", timeout=120, env=env)


def зов(режим: str, данные: dict, env_extra: dict | None = None) -> dict:
    r = subprocess.run([sys.executable, str(МЕХАНИЗМ), режим],
                       input=json.dumps(данные, ensure_ascii=False), capture_output=True,
                       text=True, encoding="utf-8", timeout=120,
                       env=dict(os.environ, **(env_extra or {})))
    out = (r.stdout or "").strip()
    return json.loads(out).get("hookSpecificOutput", {}) if out else {}


def отказ(о: dict) -> bool:
    return о.get("permissionDecision") == "deny"


def причина(о: dict) -> str:
    return о.get("permissionDecisionReason", "")


def контур(tmp: pathlib.Path, с_контейнером=True) -> tuple:
    """→ (контейнер, репозиторий). Репозиторий — общий: в нём коммитят разные роли."""
    контейнер = tmp / "контур"
    if с_контейнером:
        (контейнер / ".mezosync").mkdir(parents=True)
        sqlite3.connect(контейнер / ".mezosync" / "mezosync.db").close()
    репо = контейнер / "общий.archs"
    репо.mkdir(parents=True)
    git(репо, "init", "-q")
    (репо / "начало.md").write_text("старт", encoding="utf-8")
    git(репо, "add", "начало.md")
    git(репо, "commit", "-q", "-m", "первый", when="2026-08-20T10:00:00+0000")
    return контейнер, репо


def main() -> int:
    ok = True
    if not МЕХАНИЗМ.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет механизма — {МЕХАНИЗМ}")
    tmp = mezo_stand.new("bite-shared-repo-")
    try:
        # ① ПРАВКА СВОЕГО. Прогон «своя сторона» из критерия ③.
        контейнер, репо = контур(tmp / "a")
        sid = "смена-1"
        общ = {"session_id": sid, "cwd": str(репо), "tool_name": "Bash"}
        (репо / "моё.md").write_text("моя работа", encoding="utf-8")
        git(репо, "add", "моё.md")
        git(репо, "commit", "-q", "-m", "мой коммит", when="2026-08-20T11:00:00+0000")
        зов("--record", {**общ, "tool_input": {"command": "git commit -m 'мой коммит'"}})
        о = зов("--judge", {**общ, "tool_input": {"command": "git commit --amend -m 'правлю своё'"}})
        ok &= case("① правка СВОЕГО последнего коммита — проходит",
                   not отказ(о),
                   "механизм, запрещающий законную правку своей же работы, будет выключен "
                   "первым — и вместе с ним уйдёт защита от чужого")

        # ② ПРАВКА ПОСЛЕ ЧУЖОГО. Ровно случай 18.08.
        (репо / "чужое.md").write_text("работа другой роли", encoding="utf-8")
        git(репо, "add", "чужое.md")
        git(репо, "commit", "-q", "-m", "коммит другой роли",
            when="2026-08-20T11:00:26+0000")
        о = зов("--judge", {**общ, "tool_input": {"command": "git commit --amend --no-edit"}})
        ok &= case("② правка ПОСЛЕ чужого коммита — отказ, называющий ЧТО в нём",
                   отказ(о) and "чужое.md" in причина(о) and "УЖЕ НЕ ТВОЙ" in причина(о),
                   "26 секунд между двумя вызовами — и «последний» перестал означать «мой»",
                   differ=True)

        # ③ ОТКАЗ НЕ ПО АВТОРУ. 🪤 Первая заявка на этот механизм звучала «автор HEAD не ты»
        #    и была снята замером: под одним именем коммитят ВСЕ роли. Здесь оба коммита
        #    сделаны одним автором нарочно — и механизм всё равно различил.
        ok &= case("③ отказ НЕ ссылается на автора (все роли под одним именем)",
                   "автор" not in причина(о).lower().replace("не по автору", "")
                   and "HEAD сдвинулся" in причина(о),
                   "оба коммита в стенде сделаны ОДНИМ автором — различить можно только "
                   "составом и сдвигом, и механизм различил именно так", differ=True)

        # ④ «НЕ ЗНАЮ» ≠ «ЧУЖОЙ». Смена ещё не коммитила: сравнивать не с чем.
        контейнер2, репо2 = контур(tmp / "b")
        о = зов("--judge", {"session_id": "смена-2", "cwd": str(репо2), "tool_name": "Bash",
                            "tool_input": {"command": "git commit --amend --no-edit"}})
        ok &= case("④ смена ещё не коммитила — отказ «НЕ ЗНАЮ», отличный от «чужой»",
                   отказ(о) and "НЕ ЗНАЕТ" in причина(о) and "УЖЕ НЕ ТВОЙ" not in причина(о),
                   "тихо пропустить здесь значило бы вернуть ту же беду; и назвать это "
                   "«чужим» тоже нельзя — мы не проверяли", differ=True)

        # ⑤ «ВСЁ ВОКРУГ» ПРИ ЧУЖИХ ФАЙЛАХ. Случай 29.07.
        контейнер3, репо3 = контур(tmp / "c")
        for имя in ("чужое-1.md", "чужое-2.md"):
            (репо3 / имя).write_text("работа соседа", encoding="utf-8")
            os.utime(репо3 / имя, (time.time() - 7200, time.time() - 7200))  # старше смены
        sid3 = "смена-3"
        зов("--record", {"session_id": sid3, "cwd": str(репо3), "tool_name": "Write",
                         "tool_input": {"file_path": str(репо3 / "моё-новое.md")}})
        (репо3 / "моё-новое.md").write_text("моя работа", encoding="utf-8")
        о = зов("--judge", {"session_id": sid3, "cwd": str(репо3), "tool_name": "Bash",
                            "tool_input": {"command": "git add -A && git commit -m 'всё'"}})
        ok &= case("⑤ «всё вокруг» при чужих файлах — отказ, файлы названы ПОИМЁННО",
                   отказ(о) and "чужое-1.md" in причина(о) and "чужое-2.md" in причина(о)
                   and "моё-новое.md" not in причина(о),
                   "отказ без имён нельзя ни оспорить, ни исполнить: роль не узнает, "
                   "что именно чужое", differ=True)

        # ⑥ ВСТРЕЧНЫЙ к ⑤: те же файлы, но записанные ЭТОЙ сменой.
        контейнер4, репо4 = контур(tmp / "d")
        sid4 = "смена-4"
        for имя in ("а.md", "б.md"):
            зов("--record", {"session_id": sid4, "cwd": str(репо4), "tool_name": "Write",
                             "tool_input": {"file_path": str(репо4 / имя)}})
            (репо4 / имя).write_text("моя работа", encoding="utf-8")
        о = зов("--judge", {"session_id": sid4, "cwd": str(репо4), "tool_name": "Bash",
                            "tool_input": {"command": "git add -A"}})
        ok &= case("⑥ ВСТРЕЧНЫЙ: те же файлы, но записанные ЭТОЙ сменой — проходит",
                   not отказ(о),
                   "без него ⑤ зеленел бы у механизма, запрещающего «всё вокруг» ВСЕГДА — "
                   "то есть не различающего вовсе", differ=True)

        # ⑦ ВСТРЕЧНЫЙ: чистое дерево — брать нечего.
        контейнер5, репо5 = контур(tmp / "e")
        о = зов("--judge", {"session_id": "смена-5", "cwd": str(репо5), "tool_name": "Bash",
                            "tool_input": {"command": "git add -A"}})
        ok &= case("⑦ ВСТРЕЧНЫЙ: чистое дерево — проходит",
                   not отказ(о),
                   "отказ на пустом месте учит выключать механизм", differ=True)

        # ⑧ ПОИМЁННОЕ ДОБАВЛЕНИЕ — то самое, чего требует правило. Никогда не трогаем.
        о = зов("--judge", {"session_id": sid3, "cwd": str(репо3), "tool_name": "Bash",
                            "tool_input": {"command": "git add моё-новое.md"}})
        ok &= case("⑧ поимённое добавление не трогается никогда",
                   not отказ(о),
                   "механизм обязан пропускать ровно тот способ, к которому подталкивает",
                   differ=True)

        # ⑨ ХРАНИЛИЩЕ ВНЕ КОНТУРА — не наш предмет.
        вне = tmp / "снаружи"
        вне.mkdir()
        git(вне, "init", "-q")
        (вне / "файл.md").write_text("чьё-то", encoding="utf-8")
        os.utime(вне / "файл.md", (time.time() - 7200, time.time() - 7200))
        о = зов("--judge", {"session_id": "смена-9", "cwd": str(вне), "tool_name": "Bash",
                            "tool_input": {"command": "git add -A"}})
        ok &= case("⑨ репозиторий ВНЕ контура — молчим",
                   not отказ(о),
                   "правило про общее хранилище ролей; запрет шире предмета — путь "
                   "к выключению", differ=True)

        # ⑩ БЕЗВРЕДНЫЙ ОДНОКОРЕННОЙ. `stash list` только показывает.
        о_list = зов("--judge", {"session_id": sid3, "cwd": str(репо3), "tool_name": "Bash",
                                 "tool_input": {"command": "git stash list"}})
        о_stash = зов("--judge", {"session_id": sid3, "cwd": str(репо3), "tool_name": "Bash",
                                  "tool_input": {"command": "git stash"}})
        ok &= case("⑩ `git stash list` не путается со `stash` (забирает всё)",
                   not отказ(о_list) and отказ(о_stash),
                   "третья команда того же рода — отложить незакоммиченное; ловится "
                   "по способу брать, а не по имени", differ=True)

        # ⑪ ВЫКЛЮЧАТЕЛЬ узким словом.
        о_off = зов("--judge", {"session_id": sid3, "cwd": str(репо3), "tool_name": "Bash",
                                "tool_input": {"command": "git add -A"}},
                    {"MEZO_SHARED_REPO_GUARD": "off"})
        о_0 = зов("--judge", {"session_id": sid3, "cwd": str(репо3), "tool_name": "Bash",
                              "tool_input": {"command": "git add -A"}},
                  {"MEZO_SHARED_REPO_GUARD": "0"})
        ok &= case("⑪ слово выключения гасит, опечатка в нём — НЕ гасит",
                   not отказ(о_off) and отказ(о_0),
                   "выключатель, гаснущий от чего угодно непустого, гасится опечаткой "
                   "и молча", differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print(f"{'✅ ЗАХВАТ ЧУЖОГО — ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
