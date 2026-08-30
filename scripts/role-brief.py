# -*- coding: utf-8 -*-
"""
role-brief.py — СОБИРАЕМЫЙ НАКАЗ РОЛИ + ПАЁК ПУЛА (заход 2.1 + П⑥ плана «Роли
не забывают»). Наказ не пишется рукой и не протухает молча: он СОБИРАЕТСЯ из живых
источников при каждом вызове. Рукописный наказ уже победил верную память роли
(живой случай 27.08) — этот собирается из того, что и так правится по ходу работы.

    python <КОНТУР>/.mezosync/scripts/role-brief.py --role PROTO

ИСТОЧНИКИ (сломанный ИСТОЧНИК НАЗЫВАЕТСЯ, наказ не собирается молча неполным):
  · реестр ролей (зона, жизненный цикл)      · права (role_rights, живые)
  · формы вызова — ВЫЧИСЛЯЮТСЯ от mezo_paths  · пул: карточки + скиллы + объявления
  · умения роли (role_skill, протухшие по expired_at НЕ входят)

ГРАНИЦА ВСЛУХ: пометки «обязательный шаг» у правил свода НЕТ полем — свод в паёк
не режется, печатается счёт активных правил и команда запроса. Резать свод на глаз
значило бы решать за читателя, что ему не понадобится.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

from mezo_paths import resolve_db, live_scripts

S = live_scripts().as_posix()
OPEN = ("open", "in_progress", "blocked", "awaiting_word", "in_review")


def section(title, fn, out):
    """Секция наказа: поломка источника НАЗЫВАЕТСЯ строкой, а не молчит и не роняет
    остальные секции (наказ, собравшийся молча без куска, — ложь о полноте)."""
    try:
        fn(out)
    except Exception as e:                             # noqa: BLE001
        out.append(f"⚠️ {title}: ИСТОЧНИК НЕ ПРОЧИТАН ({type(e).__name__}: {e}) — "
                   f"наказ НЕПОЛОН, это не «пусто»")


def build(conn, role, полный=False):
    """полный=True (флаг --waiting) — раздел «ТЕБЯ ЖДУТ» печатает СПИСОК ЦЕЛИКОМ.
    Команда в строке остатка обязана существовать: обещать несуществующий вызов —
    ровно предмет карточки #124 (имя инструмента, которого нет по названному пути)."""
    out = []

    def роль(out):
        r = conn.execute("SELECT lifecycle, zone FROM roles WHERE role=?", (role,)).fetchone()
        if not r:
            out.append(f"⚠️ роли {role} нет в реестре — зона неизвестна, спроси владельца")
            return
        lc, zone = r
        out.append(f"🧭 РОЛЬ {role} [{lc}] · зона: {zone or '— не названа'}")
        if lc != "alive":
            out.append(f"   ⚠️ жизненный цикл «{lc}» — работать без живого слова нельзя")
    section("реестр ролей", роль, out)

    def права(out):
        rows = conn.execute(
            "SELECT role, right_key, scope, kind FROM role_rights "
            "WHERE role IN (?, 'ALL') AND revoked_at IS NULL AND spent_at IS NULL "
            "ORDER BY role DESC, id", (role,)).fetchall()
        if not rows:
            out.append("🔑 ПРАВ ИМЕННЫХ НЕТ — только общие правила свода")
            return
        out.append(f"🔑 ПРАВА (живые, {len(rows)}):")
        for r_, key, scope, kind in rows:
            out.append(f"   · {key} [{kind}{', общее' if r_ == 'ALL' else ''}]: "
                       f"{(scope or '')[:90]}")
    section("права", права, out)

    def формы(out):
        out.append("🛠 ФОРМЫ ВЫЗОВА (вычислены от живого каталога — не переписывай в память "
                   "относительными):")
        for name, tail, что in [
                ("guard-all.py", "", "шаг 0 пробуждения: все гарды"),
                ("read-phoenix.py", f" --role {role}", "сохранённая память"),
                ("read-messages.py", f" --role {role}", "лента; дочитай и --ack"),
                ("backlog.py", f" list --role {role}", "карточки (пул первым)"),
                ("track.py", " view", "витрина пула"),
                ("write-message.py", f" --role {role} --file <нота.md>", "писать (длинное — файлом)"),
                ("save-phoenix.py", f" --role {role} --section state --file <f>", "сохранить память")]:
            out.append(f"   {что:32} python {S}/{name}{tail}")
        # ═══ Карточка #362: уборка памяти — ПОСЛЕ первого отчёта, не внутри старта ═══
        # Замер 29.08: полный старт роли 41 мин, из них ~13 — сжатие раздутых разделов
        # памяти ДО первого отчёта. Владелец ждёт признака жизни, а роль прибирается.
        # Порядок называется ЗДЕСЬ, а не новым шагом: шаги пробуждения не удлиняются.
        out.append("   ⚖️ порядок пробуждения: гарды → наказ → память → лента → ПЕРВЫЙ "
                   "ОТЧЁТ владельцу; УБОРКА памяти (сжатие раздутых разделов) — отдельным "
                   "ходом ПОСЛЕ отчёта: красные общего прогона о раздутых разделах — "
                   "долг дня, не приказ убирать немедленно")
    section("формы вызова", формы, out)

    def пул(out):
        pools = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT track_id, title, skills FROM tracks WHERE status='active'")}
        if not pools:
            out.append("🎯 ПУЛ: активного пула нет")
            return
        ph = ",".join("?" * len(pools))
        mine = conn.execute(
            f"SELECT id, title, status, parent_track FROM backlog WHERE role=? "
            f"AND parent_track IN ({ph}) AND status IN {OPEN!r}".replace("'open'", "'open'"),
            (role, *pools)).fetchall()
        if len(pools) > 1:
            out.append(f"⚠️ активных пулов {len(pools)} — норма ОДИН; судьба лишнего — "
                       f"слово владельца")
        else:
            # Карточка #399 ступень ④ (слово владельца 29.08 14:39 UTC): направление —
            # первой строкой секции. Взятие вне его — предупреждение; причина — вслух.
            out.append(f"🧭 НАПРАВЛЕНИЕ КОНТУРА: {next(iter(pools))} — вне его задач "
                       f"не бери; законная причина — вслух (claim --off-pool)")
        if not mine:
            out.append(f"🎯 в пуле ({', '.join(sorted(pools))}) твоих карточек нет")
            return
        for tid, (title, skills) in pools.items():
            карточки = [m for m in mine if m[3] == tid]
            if not карточки:
                continue
            out.append(f"🎯 ПУЛ {tid}: «{title[:70]}»")
            out.append(f"   🧰 скиллы под задачу: {skills[:150] if skills else 'НЕ НАЗВАНЫ — спроси заводившего пул'}")
            for bid, t, st, _tr in карточки:
                out.append(f"   #{bid} [{st}] {t[:76]}")
        sys.path.insert(0, str(live_scripts()))
        from backlog import live_and_overdue, pool_open_ids
        _, overdue = live_and_overdue(conn, pool_open_ids(conn, set(pools)))
        for bid, actor, _u, note, hours in overdue[:3]:
            out.append(f"   ⏰ {actor} молчит над карточкой #{bid} — шаг истёк {hours} ч")
        out.append(f"   полнее: python {S}/track.py view")
    section("пул", пул, out)

    def вопросы_владельцу(out):
        # ═══ Карточка #430 ступень ④ (правило interview-before-recommend): вопросы,
        # ждущие слова владельца, ДОСТАВЛЯЮТСЯ — роль видит их в стартовой сводке
        # и несёт в первый отчёт. Замер 29.08: шесть карточек ждали слова МОЛЧА,
        # старшей 11 суток — владелец не услышал ни об одной.
        # Возраст — от часа ПОСТАНОВКИ в «жду слова» (событие), не от updated_at:
        # комментарии двигают updated_at и молодили бы старый вопрос.
        rows = conn.execute(
            "SELECT b.id, b.role, b.blocked_reason,"
            " CAST((julianday('now') - julianday(COALESCE("
            "   (SELECT MAX(e.at) FROM backlog_events e"
            "    WHERE e.backlog_id = b.id AND e.to_status = 'awaiting_word'),"
            "   b.updated_at))) * 24 AS INTEGER)"
            " FROM backlog b WHERE b.status = 'awaiting_word' ORDER BY 4 DESC").fetchall()
        if not rows:
            # ноль ждущих ⇒ НИ ОДНОЙ строки: счётчик, горящий всегда, не значит
            # ничего и промолчит, когда впервые окажется настоящим (встречный① критерия)
            return
        возраст = lambda ч: f"{ч // 24} дн" if ч >= 48 else f"{ч} ч"   # noqa: E731
        out.append(f"🙋 ЖДУТ СЛОВА ВЛАДЕЛЬЦА: {len(rows)} (старший {возраст(rows[0][3])}) — "
                   f"старое ПЕРВЫМ, неси в отчёт; отвеченное исчезает само")
        for bid, r, why, ч in rows[:6]:
            вопрос = (why or "вопрос в карточке").strip().splitlines()[0]
            out.append(f"   карточка #{bid} ({r}, {возраст(ч)}) — {вопрос[:84]}")
        if len(rows) > 6:
            out.append(f"   … и ещё {len(rows) - 6}")
    section("вопросы владельцу", вопросы_владельцу, out)

    def тебя_ждут(out):
        # ═══ Карточка #471 (слово владельца 30.08 10:16 UTC): чужие ожидания НЕ переживают
        # пересоздания роли — ни одно. Замер @COORD 30.08 09:49: в текст пересоздания
        # попадает НОЛЬ чужих ожиданий при обеих его мерках. Сбывшийся случай — карточка
        # #124: риск назван @STUD 11.08 ПЕРЕД прошлым пересозданием PROTO, сбылся, предмет
        # ждал 19 суток. Место выбрано ЗАМЕРОМ, а не вкусом: текст пересоздания роль читает
        # ОДИН раз в жизни, стартовую сводку — каждую сверку.
        #
        # 🩸 ОТБОР ПО СЛОВАМ ОТВЕРГНУТ ЗАМЕРОМ (30.08 10:21 UTC), и это стоило мне прогноза:
        # словарь ожидания («ждёт», «рука», «решение», «приёмка»…) в окне ±120 знаков вокруг
        # имени дал 126 из 275 пар — 46%, почти половину, то есть НЕ сокращает. И главное:
        # карточку #124 он НЕ поймал — ту самую, ради которой всё делается. Узкая мерка
        # @COORD теряла её же. ⇒ Отбираем ПОЛЯМИ карточки, а не словами в тексте:
        # состояние «на приёмке» — машинный признак ожидания чужой руки, возраст — мера боли.
        # Замер того же часа: пар «роль × чужая карточка» 275 · из них на приёмке 13.
        роли = [r[0] for r in conn.execute(
            "SELECT role FROM roles WHERE lifecycle='alive'")]
        if role not in роли:
            роли.append(role)
        ph_ = ",".join("?" * len(OPEN))
        строки = conn.execute(
            f"SELECT id, role, status, title, COALESCE(body_md,''), COALESCE(done_when,''),"
            f" CAST((julianday('now') - julianday(created_at)) AS INTEGER)"
            f" FROM backlog WHERE status IN ({ph_}) AND role <> ?", (*OPEN, role)).fetchall()
        import re as _re
        обо_мне = _re.compile(rf"(?<![A-Za-z]){_re.escape(role)}(?![A-Za-z])")
        мои = [(i, r, st, t, age) for i, r, st, t, b, d, age in строки
               if обо_мне.search(f"{t}\n{b}\n{d}")]
        if not мои:
            # ⚖️ Ноль говорится СЛОВОМ, в отличие от соседней секции «ждут слова владельца».
            # Там ноль — норма дня, и вечная строка была бы шумом. Здесь ноль — редкость
            # (замер 30.08: непустой список у ВСЕХ девяти ролей, от 7 до 55), и роль по этому
            # разделу судит «мне никто ничего не должен». Молчащий раздел от несобравшегося
            # роль не отличит — а это ровно тот класс, ради которого раздел и заводится.
            out.append("🫱 ТЕБЯ НЕ ЖДЁТ НИКТО — проверено запросом к чужим незакрытым "
                       "карточкам, это НЕ «раздел не собрался»")
            return
        # на приёмке — первыми (чужая рука названа состоянием), дальше старшие
        мои.sort(key=lambda m: (m[2] != "in_review", -m[4]))
        показать = мои if полный else мои[:10]
        возраст = lambda ч: f"{ч} дн"                             # noqa: E731
        out.append(f"🫱 ТЕБЯ ЖДУТ: {len(мои)} чужих незакрытых карточек называют тебя "
                   f"(на приёмке — первыми, дальше старшие)")
        for i, r, st, t, age in показать:
            out.append(f"   карточка #{i} [{r} · {st} · {возраст(age)}] {t[:70]}")
        if len(мои) > len(показать):
            out.append(f"   … ещё {len(мои) - len(показать)} — python {S}/role-brief.py "
                       f"--role {role} --waiting")
        out.append("   ⚖️ мерка ШИРОКАЯ: имя роли названо в карточке — это УПОМИНАНИЕ, "
                   "а не доказанное ожидание. Читай сама; отбор по словам отвергнут замером")
    section("тебя ждут", тебя_ждут, out)

    def ты_сдал(out):
        # ═══ Встречная половина, находка @RCC (записка #4426 §②): пересоздания не переживает
        # не только ЧУЖОЕ ожидание, но и СВОЯ сданная работа. «У тебя роль не узнает, что ЕЁ
        # ЖДУТ; у меня — что ОНА СДАЛА и чьей руки ждёт результат». Цена разная: чужое
        # ожидание живёт в чужой голове и однажды прозвучит, а сданная работа, о которой
        # забыл сдавший, не прозвучит нигде — приёмщик ещё не дошёл, сдавший не помнит.
        # ═══ Карточка #482 ступень ③: приёмщик — ПОЛЕМ, и он виден ЗДЕСЬ. Поле, которое
        # заполняют и никто не читает, мертво; поэтому оно печатается там, где роль и так
        # смотрит, а «не назначен» говорится СЛОВОМ — иначе пустота неотличима от «назначен,
        # но не показан», и роль не узнает, что её работа не ждёт ничьей руки.
        есть_поле = "reviewer" in {r[1] for r in conn.execute("PRAGMA table_info(backlog)")}
        поле = "COALESCE(reviewer,'')" if есть_поле else "''"
        rows = conn.execute(
            f"SELECT id, title, CAST((julianday('now') - julianday(updated_at)) * 24 AS INTEGER),"
            f" {поле}"
            f" FROM backlog WHERE role=? AND status='in_review' ORDER BY updated_at",
            (role,)).fetchall()
        if not rows:
            return          # ноль здесь — норма дня, а не редкость: вечная строка была бы шумом
        безрукие = sum(1 for r in rows if not (r[3] or "").strip())
        out.append(f"📤 ТЫ СДАЛ, ЖДЁТ ЧУЖОЙ РУКИ: {len(rows)} — приёмку не торопи, "
                   f"но и не забывай: о своей сдаче помнишь только ты"
                   + (f" · 🫱 БЕЗ НАЗНАЧЕННОГО ПРИЁМЩИКА: {безрукие}" if безрукие else ""))
        for i, t, ч, кто in rows[:6]:
            кто = (кто or "").strip()
            out.append(f"   карточка #{i} ({ч} ч на полке · "
                       + (f"приёмщик: {кто[:28]}" if кто else "приёмщик НЕ НАЗНАЧЕН")
                       + f") {t[:52]}")
        if len(rows) > 6:
            out.append(f"   … и ещё {len(rows) - 6}")
    section("ты сдал", ты_сдал, out)

    def умения(out):
        rows = conn.execute(
            "SELECT skill, measured_at, until_cond FROM role_skill "
            "WHERE role=? AND expired_at IS NULL ORDER BY measured_at DESC", (role,)).fetchall()
        expired = conn.execute(
            "SELECT COUNT(*) FROM role_skill WHERE role=? AND expired_at IS NOT NULL",
            (role,)).fetchone()[0]
        if not rows:
            out.append("🧠 УМЕНИЙ В ТАБЛИЦЕ НЕТ — таблица роли пишется её же рукой "
                       + (f"(протухших скрыто: {expired})" if expired else ""))
            return
        out.append(f"🧠 УМЕНИЯ ({len(rows)} живых"
                   + (f"; протухших скрыто {expired} — напоминание о протухшем вреднее "
                      f"отсутствия" if expired else "") + "):")
        for skill, mat, cond in rows[:6]:
            out.append(f"   · {skill[:80]} (замер {mat[:10]}"
                       + (f"; протухнет: {cond[:50]}" if cond else "") + ")")
        if len(rows) > 6:
            out.append(f"   … и ещё {len(rows) - 6}")
    section("умения", умения, out)

    def ритм(out):
        st = conn.execute(
            "SELECT status FROM rules WHERE rule_key='sync-alarm-in-chat'").fetchone()
        if not st or st[0] != "active":
            out.append("⏰ РИТМ: правило sync-alarm-in-chat "
                       + ("ОТОЗВАНО" if st else "НЕ НАЙДЕНО")
                       + " — ритм спроси у владельца, прежнему стандарту не верь")
            return
        out.append("⏰ РИТМ (слово владельца 29.08): будильник ВНУТРИ чата; наказ — ФАЙЛОМ; "
                   "будильник гибнет с чатом — при пересоздании перезаведи ПЕРВЫМ ходом; "
                   "задачу-расписание вне чата для сверок не заводи")
        out.append(f"   период и стандарт целиком: python {S}/set-rule.py "
                   f"--key sync-alarm-in-chat --show")
    section("ритм", ритм, out)

    def свод(out):
        n = conn.execute("SELECT COUNT(*) FROM rules WHERE status='active'").fetchone()[0]
        out.append(f"📜 СВОД: активных правил {n} — в стартовую сводку не режется (граница в шапке); "
                   f"целиком: python {S}/set-rule.py --list")
    section("свод", свод, out)

    def ответы(out):
        st = conn.execute(
            "SELECT status FROM rules WHERE rule_key='owner-reply-format'").fetchone()
        if not st or st[0] != "active":
            out.append("🗣 ОТВЕТЫ ВЛАДЕЛЬЦУ: правило owner-reply-format не активно — "
                       "форму спроси у владельца")
            return
        out.append("🗣 ОТВЕТЫ ВЛАДЕЛЬЦУ: перед КАЖДЫМ ответом владельцу перечитай правило "
                   "(тут ссылка, не тело — две редакции разошлись бы):")
        out.append(f"   python {S}/set-rule.py --key owner-reply-format --show")
    section("ответы владельцу", ответы, out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Собираемый наказ роли + стартовая сводка пула")
    ap.add_argument("--role", required=True)
    ap.add_argument("--db", default=None)
    ap.add_argument("--waiting", action="store_true",
                    help="раздел «ТЕБЯ ЖДУТ» — список ЦЕЛИКОМ, без свёртки остатка")
    a = ap.parse_args()
    role = a.role.upper()
    try:
        db = Path(resolve_db(a.db, __file__))
    except SystemExit as e:
        # resolve_db отказывает сам (базы нет / аренда) — наказ обязан сказать СВОИМИ
        # словами, что он НЕ СОБРАН, а не отдать голый отказ нижнего слоя.
        sys.exit(f"⛔ НАКАЗ НЕ СОБРАН: {e} — это не «пустой наказ»")
    if not db.exists():
        sys.exit(f"⛔ НАКАЗ НЕ СОБРАН: базы нет ({db}) — это не «пустой наказ»")
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    print(f"═══ НАКАЗ {role} (собран из живой базы сейчас; рукописной копии НЕ верь "
          f"старше этого вывода)")
    for line in build(conn, role, полный=a.waiting):
        print(line)
    conn.close()


if __name__ == "__main__":
    main()
