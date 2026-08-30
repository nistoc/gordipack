import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Overview, Task, TaskDetail, TaskGroup, TasksGrouped } from '../types';
import { fmtUtc } from '../format';
import { StatCard } from '../components/MeasureValue';
import { Rail, RailStrip } from '../components/Rail';
import { PriorityMark, StatusMark } from '../components/TaskTile';
import { useUrlEnum, useUrlNumber, useUrlParam } from '../useUrlState';
import { TrackSection } from './TrackSection';
import {
  BOARD_SORTS, BOARD_SORT_KEYS, boardComparator, boardSort,
  isCriterionGap, orderStatuses, statusMeta,
} from '../taskModel';
import type { BoardSortKey } from '../taskModel';

const STATUS_TITLE: Record<string, string> = {
  open: 'открытые',
  in_review: 'на проверке',
  blocked: 'заблокированные',
  done: 'закрытые',
  dropped: 'снятые',
};

const DETAIL_RAIL = { defaultWidth: 560, minWidth: 380, maxWidth: 900 };

/**
 * Служебное значение отбора «задачи БЕЗ набора» — ровно то, что понимает служба
 * (`GET /api/tasks?track=none`). Держится ЗДЕСЬ одной строкой, а не рассыпано по коду:
 * разойдись оно со службой на одну букву — отбор молча вернул бы все задачи вместо
 * задач без набора, и экран выглядел бы исправным.
 * ⚠️ Если такое имя однажды окажется настоящим набором, служба отвечает отказом СО СЛОВОМ,
 * а не тихой подменой — этот отказ мы показываем человеку как есть.
 */
const UNTRACKED_KEY = 'none';

/**
 * Главная страница: задачи и — прежде всего — те из них, у которых НЕТ критерия
 * приёмки. Замер живой базы 2026-08-07 13:08 UTC: карточек 105, открытых 59, и у 22
 * из них поле критерия пустое. (Дата у числа обязательна: база живая, и за сутки от
 * прежнего замера в этом же файле — 78 карточек, 39 открытых, 25 без критерия — не
 * осталось ни одного совпавшего числа.)
 *
 * ОДНО ПРЕДСТАВЛЕНИЕ — ДОСКА: колонка на роль, плитки сверху вниз. Отвечает «чем занята
 * роль и где у неё дыры»: этот вопрос требует сравнения ролей, а сравнивать в плоском
 * списке нечем. Плоская таблица со всеми колонками стояла здесь вторым видом и убрана
 * по слову владельца 2026-08-10 09:34 UTC — вместе с переключателем видов, которому
 * после этого не из чего выбирать.
 *
 * 📌 ФИЛЬТРУЕМ НА КЛИЕНТЕ, а не запросом на каждый чих. Причина не в скорости:
 * переключатели обязаны показывать ЧЕСТНЫЕ СЧЁТЧИКИ, а счётчик по уже отфильтрованному
 * набору считал бы сам себя. Карточек около сотни — цена полного чтения ничтожна против
 * цифры, которая врёт.
 */
export function TasksPage({ overview, refreshMs }: { overview: Overview | null; refreshMs: number }) {
  // Что открыто — В АДРЕСЕ. Перезагрузка возвращает тот же экран, ссылку можно отдать
  // другому, «назад» отменяет шаг, а не выкидывает со страницы.
  // Старый параметр `view` (доска/таблица) не читается вовсе: ссылка вида `?view=table`
  // из чьей-то переписки откроет доску, а не пустой экран.
  const [openId, setOpenId] = useUrlNumber('task');

  // Фильтры тоже в адресе, но ЗАМЕЩЕНИЕМ, а не шагом истории: иначе «назад» после
  // десятка щелчков по фишкам десять раз перебирал бы фильтры вместо возврата.
  const [statusRaw, setStatusRaw] = useUrlParam('status', 'replace');
  const [roleRaw, setRoleRaw] = useUrlParam('role', 'replace');
  const [gapRaw, setGapRaw] = useUrlParam('gap', 'replace');
  const [trackRaw, setTrackRaw] = useUrlParam('track', 'replace');

  const status = statusRaw ?? 'open';
  const role = roleRaw ?? 'all';
  const onlyMissing = gapRaw === '1';
  /** Отбор по набору: 'all' — все · UNTRACKED — без набора · иначе имя набора. */
  const track = trackRaw ?? 'all';
  const setStatus = (v: string) => setStatusRaw(v === 'open' ? null : v);
  const setRole = (v: string) => setRoleRaw(v === 'all' ? null : v);
  const setOnlyMissing = (v: boolean) => setGapRaw(v ? '1' : null);
  const setTrack = (v: string) => setTrackRaw(v === 'all' ? null : v);

  /**
   * ПОРЯДОК ПЛИТОК В КОЛОНКАХ ДОСКИ — тоже в адресе страницы, как и всё остальное
   * состояние: перезагрузка возвращает тот же порядок, ссылкой можно поделиться.
   * Замещением, а не шагом истории: это уточнение того же вида, как и фильтры.
   */
  const [boardSortKey, setBoardSortKey] = useUrlEnum<BoardSortKey>(
    'sort', BOARD_SORT_KEYS, 'default', 'replace',
  );
  const [boardDirRaw, setBoardDirRaw] = useUrlParam('dir', 'replace');
  const boardDir: 1 | -1 = boardDirRaw === 'desc' ? -1 : 1;
  const setBoardDir = (d: 1 | -1) => setBoardDirRaw(d === -1 ? 'desc' : null);
  const boardOrder = useMemo(
    () => boardComparator(boardSortKey, boardDir),
    [boardSortKey, boardDir],
  );
  const boardSortMeta = boardSort(boardSortKey);

  /**
   * ГРУППЫ ПО НАБОРАМ БЕРУТСЯ У СЛУЖБЫ — клиент их НЕ строит.
   * Порядок групп, признак «набора нет в таблице наборов» и группа «без набора»
   * приходят готовыми: собери я то же самое своей рукой, два порядка однажды
   * разошлись бы, и экран показывал бы не то, что отдаёт база.
   * Запрашиваем ПОЛНЫЙ набор (без status/role): фильтры страницы применяются к плиткам
   * на клиенте — иначе счётчики фишек считали бы сами себя.
   */
  const grouped = usePolling<TasksGrouped | null>(() => api.tasksGrouped(), refreshMs, []);
  const groups = useMemo<TaskGroup[]>(() => grouped.data?.groups ?? [], [grouped.data]);
  const all = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  /**
   * ОТБОР ПО НАБОРУ ДЕЛАЕТ СЛУЖБА, а не фильтр массива в браузере — иначе половина
   * работы стыка осталась бы непроверенной: отбор был бы «сделан» на экране и никогда
   * не спрошен у той стороны, которая за него отвечает.
   * Ответ служит ВСТРЕЧНЫМ СЛУЧАЕМ к группировке: число отобранных обязано совпасть
   * с числом в одноимённой группе. Разошлись — экран скажет это словами (ниже).
   */
  const picked = usePolling<Task[] | null>(
    () => (track === 'all' ? Promise.resolve(null) : api.tasks({ status: 'all', track })),
    refreshMs,
    [track],
  );

  const detail = usePolling<TaskDetail | null>(
    () => (openId === null ? Promise.resolve(null) : api.task(openId)),
    0,
    [openId],
  );

  // Возраст плиток считается от ОДНОГО «сейчас» на всю отрисовку: иначе соседние плитки
  // мерялись бы по чуть разным моментам, и сортировка по возрасту могла бы дрогнуть.
  const nowMs = Date.now();

  // Счётчики считаются по ПОЛНОМУ набору — иначе переключатель показывал бы,
  // сколько осталось после него самого.
  const statusCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of all) m.set(t.status ?? '—', (m.get(t.status ?? '—') ?? 0) + 1);
    return m;
  }, [all]);

  const roleCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of all) {
      if (status !== 'all' && t.status !== status) continue;
      m.set(t.role ?? '—', (m.get(t.role ?? '—') ?? 0) + 1);
    }
    return m;
  }, [all, status]);

  /**
   * Счётчики наборов. Считаются по группам СЛУЖБЫ (полный набор), с поправкой на
   * фильтры статуса и роли — но НЕ на сам отбор по набору: иначе фишка «набор»
   * показывала бы, сколько осталось после неё самой.
   */
  const trackCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const g of groups) {
      const key = g.trackId ?? UNTRACKED_KEY;
      const n = g.items.filter((t) => {
        if (status !== 'all' && t.status !== status) return false;
        if (role !== 'all' && t.role !== role) return false;
        if (onlyMissing && !isCriterionGap(t)) return false;
        return true;
      }).length;
      m.set(key, n);
    }
    return m;
  }, [groups, status, role, onlyMissing]);

  /** Фильтры страницы (статус · роль · «без критерия») — одним правилом на все места. */
  const passes = useMemo(() => (t: Task) => {
    if (status !== 'all' && t.status !== status) return false;
    if (role !== 'all' && t.role !== role) return false;
    if (onlyMissing && !isCriterionGap(t)) return false;
    return true;
  }, [status, role, onlyMissing]);

  /**
   * Что показываем: при отборе по набору — ОТВЕТ СЛУЖБЫ (её половина работы),
   * без отбора — все задачи из групп.
   */
  const shownBase = useMemo(
    () => (track === 'all' ? all : picked.data ?? []),
    [track, all, picked.data],
  );
  const filtered = useMemo(() => shownBase.filter(passes), [shownBase, passes]);

  /** Группа выбранного набора — по ней сверяем ответ отбора (встречный случай). */
  const pickedGroup = useMemo<TaskGroup | null>(() => {
    if (track === 'all') return null;
    const key = track.toLowerCase();
    return groups.find((g) => (g.trackId ?? UNTRACKED_KEY).toLowerCase() === key) ?? null;
  }, [groups, track]);

  /**
   * 🔬 ДВА ОТВЕТА ОБ ОДНОМ ПРЕДМЕТЕ — и экран обязан сказать, если они разошлись.
   * Отбор по набору и группировка считаются в службе ПОРОЗНЬ. Совпадение чисел — это
   * проверка, которую нельзя сделать одной ручкой, спрошенной дважды.
   */
  const pickMismatch =
    track !== 'all' && picked.data !== null && pickedGroup !== null
      ? picked.data.length !== pickedGroup.count
      : false;

  const criterionUnsupported = all.length > 0 && all.every((t) => !t.criterionSupported);
  const statusKeys = orderStatuses(statusCounts.keys());
  const roleKeys = [...roleCounts.keys()].sort();
  const gapsShown = filtered.filter(isCriterionGap).length;

  /** Что видно на экране прямо сейчас — по этому решаем, где рисовать открытую карточку. */
  const visibleIds = useMemo(() => new Set(filtered.map((t) => t.id)), [filtered]);
  const selectedTask = useMemo(
    () => (openId === null ? null : all.find((t) => t.id === openId) ?? null),
    [all, openId],
  );
  const selectedTrackKey = selectedTask
    ? (selectedTask.parentTrack ?? '').trim() || UNTRACKED_KEY
    : null;
  const detailVisibleInSection = openId !== null && visibleIds.has(openId);

  /**
   * ПОИСК ПО НОМЕРУ КАРТОЧКИ. Отдельным полем, а не «фильтром по номеру»: человек,
   * знающий номер, хочет ТЕЛО задачи, а не список из одной строки.
   * Три исхода, и каждый назван словами:
   *   · номера в базе нет ⇒ так и сказать, ничего не открывать;
   *   · номер есть и карточка видна ⇒ открыть, показать рядом с её плиткой;
   *   · номер есть, но фильтры её скрывают ⇒ ОТКРЫТЬ ВСЁ РАВНО и сказать, где она лежит.
   * Третий исход — главный: молчаливое «ничего не произошло» здесь неотличимо от поломки.
   */
  const [findRaw, setFindRaw] = useState('');
  const [findNote, setFindNote] = useState<string | null>(null);

  /**
   * Свёрнутые секции наборов. По умолчанию РАЗВЁРНУТЫ ВСЕ, включая «без набора»:
   * свёрнутая по умолчанию группа — это спрятанная группа, а её задачи ровно так
   * и теряются. Сворачивание — удобство человека, а не умолчание экрана.
   * Живёт в состоянии страницы, а не в адресе: это не то, чем делятся ссылкой.
   */
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const toggleCollapsed = (key: string) => setCollapsed((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  const submitFind = () => {
    const cleaned = findRaw.trim().replace(/^#/, '');
    if (cleaned === '') { setFindNote(null); return; }
    const n = Number(cleaned);
    if (!Number.isFinite(n) || !Number.isInteger(n) || n <= 0) {
      setFindNote(`«${findRaw.trim()}» — это не номер карточки. Номер — целое число, например 492`);
      return;
    }
    const found = all.find((t) => t.id === n) ?? null;
    if (!found) {
      setFindNote(`карточки #${n} в этой базе нет — открывать нечего (задач всего ${all.length})`);
      return;
    }
    setOpenId(n);
    const where = (found.parentTrack ?? '').trim() || 'без набора';
    setFindNote(
      passes(found) && (track === 'all' || shownBase.some((t) => t.id === n))
        ? `#${n} — «${found.title ?? 'без заголовка'}», набор ${where}`
        : `#${n} открыта, но фильтры её сейчас скрывают: набор ${where}, статус ${found.status ?? '—'}, роль ${found.role ?? '—'}. Карточка показана отдельно выше доски`,
    );
  };

  /**
   * Рейл открытой карточки. Собран здесь, а не внутри доски: разметку карточки читает
   * и правит страница задач, а доска отвечает лишь за то, КУДА в полосе рейл встанет.
   */
  const detailRail: ReactNode = openId === null ? null : (
    <Rail
      id="task-detail"
      title={`Карточка #${openId}`}
      {...DETAIL_RAIL}
      /* Класс — договор между страницей и доской: доска ищет по нему рейл, чтобы
         поставить его на высоту выбранной плитки, а правило CSS применяет отступ. */
      className="rail--detail"
      onClose={() => setOpenId(null)}
    >
      {detail.error && (
        <div className="banner banner--error" data-panel="task-detail-error">{detail.error}</div>
      )}
      {detail.loading && !detail.data && (
        <p className="muted" data-panel="task-detail-loading">читаю карточку…</p>
      )}
      {detail.data && (
        <div data-panel="task-detail">
          <h4 className="rail__h4">{detail.data.task.title}</h4>
          <div className="detail__meta muted" data-group="task-meta">
            <span className="mono">{detail.data.task.role}</span>{' · '}
            <StatusMark status={detail.data.task.status} /> {detail.data.task.status}{' · '}
            <PriorityMark priority={detail.data.task.priority} /> {detail.data.task.priority}
            <br />
            создано {fmtUtc(detail.data.task.createdAt)}
            {detail.data.task.createdBy ? ` · завела роль ${detail.data.task.createdBy}` : ''}
            <br />
            изменено {fmtUtc(detail.data.task.updatedAt)}
            {(detail.data.task.parentId !== null || detail.data.task.parentTrack) && (
              <>
                <br />
                {detail.data.task.parentId !== null && (
                  <button
                    className="reltag reltag--parent"
                    data-control="detail-open-parent"
                    onClick={() => setOpenId(detail.data!.task.parentId as number)}
                    title="открыть родительскую карточку"
                  >
                    ↳ в составе #{detail.data.task.parentId}
                  </button>
                )}
                {detail.data.task.parentTrack && (
                  <span className="reltag reltag--track">{detail.data.task.parentTrack}</span>
                )}
              </>
            )}
            {(detail.data.task.blockedReason ?? '').trim() && (
              <div className="tile__blocked" data-group="task-blocked">
                ⛔ {detail.data.task.blockedReason}
              </div>
            )}
          </div>

          <section data-group="task-criterion">
            <h5>Критерий приёмки</h5>
            {!detail.data.task.criterionSupported
              ? <p className="muted">в этой базе поля критерия нет</p>
              : detail.data.task.hasCriterion
                ? <pre className="pre">{detail.data.task.doneWhen}</pre>
                : <p className="badge badge--gap">не задан</p>}
          </section>

          {detail.data.bodyMd && (
            <section data-group="task-body">
              <h5>Описание</h5>
              <pre className="pre">{detail.data.bodyMd}</pre>
            </section>
          )}

          {detail.data.events.length > 0 && (
            <section data-group="task-events">
              <h5>События ({detail.data.events.length})</h5>
              <ul className="events" data-list="task-events">
                {detail.data.events.map((e) => (
                  <li key={e.id} data-item={`task-event-${e.id}`}>
                    <span className="mono muted">{fmtUtc(e.at, true)}</span>{' '}
                    <strong>{e.actorRole}</strong> {e.eventType}
                    {e.fromStatus || e.toStatus ? ` (${e.fromStatus ?? '—'} → ${e.toStatus ?? '—'})` : ''}
                    {e.bodyMd ? <div className="muted">{e.bodyMd}</div> : null}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {detail.data.tests.length > 0 && (
            <section data-group="task-tests">
              <h5>Проверки ({detail.data.tests.length})</h5>
              <ul className="events" data-list="task-tests">
                {detail.data.tests.map((t) => (
                  <li key={t.id} data-item={`task-test-${t.id}`}>
                    <strong>{t.title}</strong> — {t.method} — {t.status}
                    {t.command ? <pre className="pre pre--inline">{t.command}</pre> : null}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {detail.data.missingFeatures.length > 0 && (
            <p className="muted" data-panel="task-missing-features">
              в этой базе нет: {detail.data.missingFeatures.join(', ')} — соответствующие
              разделы пусты не потому, что данных нет, а потому, что их негде хранить
            </p>
          )}
        </div>
      )}
    </Rail>
  );

  return (
    <div className="page page--rails" data-panel="tasks-page">
      {overview && (
        <div className="stats" data-group="tasks-stats">
          <StatCard label="открытых" measure={overview.tasksOpen} />
          <StatCard label="закрытых" measure={overview.tasksDone} />
          <StatCard label="всего карточек" measure={overview.tasksTotal} />
          <StatCard
            label="открытых БЕЗ критерия приёмки"
            measure={overview.tasksOpenWithoutCriterion}
            tone="warn"
            hint="критерий приёмки — поле backlog.done_when"
          />
        </div>
      )}

      {criterionUnsupported && (
        <div className="banner banner--warn" data-panel="criterion-unsupported-banner">
          В этой базе нет колонки <code>backlog.done_when</code> — критерий приёмки нигде не хранится.
          Пустое место критерия на плитках ниже означает «поля нет», а не «критерий не задан».
        </div>
      )}

      {/* Сводный счётчик и фильтры стоят НАД полосой рейлов, а не внутри колонки:
          колонок бывает десяток, и счётчик по всему набору внутри одной из них
          читался бы как счётчик этой колонки. */}
      <div className="viewbar" data-group="shown-bar">
        <span className="muted small" data-control="shown-summary">
          показано {filtered.length} из {all.length}
          {gapsShown > 0 && <> · без критерия <b className="warnnum">{gapsShown}</b></>}
        </span>
      </div>

      <div className="filterbar" data-group="filter-status-bar">
        <span className="filterbar__label">Статус</span>
        <button
          className={`fchip ${status === 'all' ? 'fchip--on' : ''}`}
          onClick={() => setStatus('all')}
          data-control="status-all"
        >
          все <span className="fchip__n">{all.length}</span>
        </button>
        {statusKeys.map((s) => (
          <button
            key={s}
            className={`fchip fchip--${s} ${status === s ? 'fchip--on' : ''}`}
            onClick={() => setStatus(s)}
            data-control={`status-${s}`}
          >
            <span className={`smark smark--${statusMeta(s).key}`}>{statusMeta(s).glyph}</span>{' '}
            {STATUS_TITLE[s] ?? s} <span className="fchip__n">{statusCounts.get(s)}</span>
          </button>
        ))}
      </div>

      <div className="filterbar" data-group="filter-role-bar">
        <span className="filterbar__label">Роль</span>
        <button
          className={`fchip ${role === 'all' ? 'fchip--on' : ''}`}
          onClick={() => setRole('all')}
          data-control="role-all"
        >
          все <span className="fchip__n">{[...roleCounts.values()].reduce((a, b) => a + b, 0)}</span>
        </button>
        {roleKeys.map((r) => (
          <button
            key={r}
            className={`fchip fchip--role ${role === r ? 'fchip--on' : ''}`}
            onClick={() => setRole(role === r ? 'all' : r)}
            data-control={`role-${r}`}
          >
            {r} <span className="fchip__n">{roleCounts.get(r)}</span>
          </button>
        ))}
      </div>

      {/* ── ОТБОР ПО НАБОРУ ──────────────────────────────────────────────────────
          Фишки идут В ПОРЯДКЕ СЛУЖБЫ (действующие наборы → приостановленные → закрытые →
          незаявленные → «без набора» последней), а не по алфавиту: порядок здесь сам
          отвечает на вопрос «чем контур занят сейчас».
          «Без набора» стои́т такой же фишкой, как остальные, — 381 задача на замере
          2026-08-30 22:53 UTC, и спрятать их значило бы спрятать три четверти базы. */}
      <div className="filterbar" data-group="filter-track-bar">
        <span className="filterbar__label">Набор</span>
        <button
          className={`fchip ${track === 'all' ? 'fchip--on' : ''}`}
          onClick={() => setTrack('all')}
          data-control="track-all"
        >
          все <span className="fchip__n">{[...trackCounts.values()].reduce((a, b) => a + b, 0)}</span>
        </button>
        {groups.map((g) => {
          const key = g.trackId ?? UNTRACKED_KEY;
          const shown = trackCounts.get(key) ?? 0;
          return (
            <button
              key={key}
              className={`fchip fchip--track ${g.trackId === null ? 'fchip--untracked' : ''} ${track === key ? 'fchip--on' : ''}`}
              onClick={() => setTrack(track === key ? 'all' : key)}
              data-control={`track-${key}`}
              title={
                g.trackId === null
                  ? 'задачи, не приписанные ни к одному набору'
                  : `${g.title ?? 'заголовка у набора нет'}${g.declared ? '' : ' · этого набора нет в таблице наборов'}`
              }
            >
              {g.trackId === null ? 'без набора' : g.trackId}
              {!g.declared && g.trackId !== null && <span className="fchip__warn" title="нет в таблице наборов">⚠</span>}
              <span className="fchip__n">{shown}</span>
              {shown !== g.count && (
                <span className="fchip__n muted" title={`всего в наборе: ${g.count}`}>/{g.count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── ПОИСК ПО НОМЕРУ КАРТОЧКИ ─────────────────────────────────────────────
          Не фильтр, а ПЕРЕХОД: человек, знающий номер, хочет тело задачи. Ответ всегда
          словами — «нет такой», «открыта», «открыта, но её скрывают фильтры». */}
      <div className="filterbar" data-group="find-by-id-bar">
        <span className="filterbar__label">Карточка №</span>
        {/*
          🔴 ЭТО ФОРМА, А НЕ ПОЛЕ СО СЛУШАТЕЛЕМ КЛАВИШИ — замер 2026-08-30 23:06 UTC.
          Сперва здесь стоял `onKeyDown={e => e.key === 'Enter' && submitFind()}`. На живом
          экране кнопка «перейти» работала, а Enter в поле — НЕТ: при том же содержимом поля
          нажатие не давало ни перехода, ни строки ответа. Тихий отказ: человек жмёт Enter
          (первое, что делают с полем ввода числа) и видит, что «ничего не произошло», —
          неотличимо от поломки всей страницы.
          Форма с кнопкой-отправкой даёт то же поведение штатным путём браузера, а не
          самодельным разбором клавиши: Enter в единственном текстовом поле формы отправляет
          её сам. Чинится ПРИЧИНА (своя реализация того, что уже умеет платформа),
          а не следствие.
          `display: contents` на форме — чтобы строка фильтров осталась одной строкой.
        */}
        <form
          className="findform"
          data-group="find-id-form"
          onSubmit={(e) => { e.preventDefault(); submitFind(); }}
        >
          <input
            className="findbox"
            type="text"
            inputMode="numeric"
            value={findRaw}
            placeholder="номер, напр. 492"
            onChange={(e) => setFindRaw(e.target.value)}
            data-control="find-id-input"
            aria-label="перейти к карточке по номеру"
          />
          <button className="fchip" type="submit" data-control="find-id-go">перейти</button>
        </form>
        {findRaw !== '' && (
          <button
            className="fchip"
            onClick={() => { setFindRaw(''); setFindNote(null); }}
            data-control="find-id-clear"
          >
            очистить
          </button>
        )}
        {findNote && (
          <span className="muted small" data-panel="find-id-note">{findNote}</span>
        )}
      </div>

      {/* ── ПОРЯДОК ПЛИТОК В КОЛОНКАХ ─────────────────────────────────────────────
          Строка стоит ВПЛОТНУЮ к строкам фильтров, с подписью «в колонках»: порядок
          относится к плиткам ВНУТРИ колонки, а не к самим колонкам — те стоят от самой
          нагруженной роли к самой свободной. Требование владельца 2026-08-07 14:04 UTC. */}
      <div className="filterbar" data-group="board-sort-bar">
        <span className="filterbar__label">В колонках</span>
        {BOARD_SORTS.map((s) => (
          <button
            key={s.key}
            className={`fchip ${boardSortKey === s.key ? 'fchip--on' : ''}`}
            onClick={() => setBoardSortKey(s.key)}
            data-control={`board-sort-${s.key}`}
            title={`порядок плиток внутри каждой колонки: ${s.title}`}
          >
            {s.title}
          </button>
        ))}
        {/* Направление СЛОВАМИ, а не одной стрелкой: «возраст по возрастанию» — это
            старые сверху или новые? Стрелка на этот вопрос не отвечает. */}
        <button
          className="fchip fchip--dir"
          onClick={() => setBoardDir(boardDir === 1 ? -1 : 1)}
          data-control="board-sort-dir"
          data-dir={boardDir === 1 ? 'asc' : 'desc'}
          title="перевернуть порядок"
        >
          {boardDir === 1 ? '▲' : '▼'} {boardDir === 1 ? boardSortMeta.asc : boardSortMeta.desc}
        </button>
      </div>

      <div className="filterbar" data-group="filter-extra-bar">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={onlyMissing}
            onChange={(e) => setOnlyMissing(e.target.checked)}
            data-control="filter-missing-criterion"
          />
          только без критерия приёмки
        </label>
      </div>

      {grouped.error && (
        <div className="banner banner--error" data-panel="tasks-error">{grouped.error}</div>
      )}

      {/* Отказ отбора приходит СО СЛОВОМ (напр. имя набора совпало со служебным
          значением) — показываем текст службы как есть, а не пустой экран. */}
      {picked.error && (
        <div className="banner banner--error" data-panel="track-filter-error">
          отбор по набору «{track}» не выполнен: {picked.error}
        </div>
      )}

      {/* Служба сама говорит, если сумма по группам не сошлась с числом задач или
          если наборы собраны без таблицы наборов. Печатаем её слово, а не глотаем. */}
      {grouped.data?.note && (
        <div className="banner banner--warn" data-panel="grouping-note">{grouped.data.note}</div>
      )}

      {pickMismatch && pickedGroup && picked.data && (
        <div className="banner banner--warn" data-panel="track-pick-mismatch">
          🔴 два ответа службы об одном наборе разошлись: отбор вернул {picked.data.length} карточек,
          а в группе того же набора их {pickedGroup.count}. Показан ответ отбора; расхождение
          означает, что одна из двух ручек считает не то — это находка, а не помеха показу.
        </div>
      )}

      {/* Карточка, открытая поиском по номеру, но скрытая фильтрами, показывается
          ОТДЕЛЬНОЙ полосой над досками. Иначе переход по номеру выглядел бы как
          «ничего не произошло» — то есть неотличимо от поломки. */}
      {openId !== null && !detailVisibleInSection && (
        <div className="page__loose-detail" data-panel="detail-outside-board">
          <p className="muted small">
            карточка #{openId} открыта отдельно: под текущими фильтрами её плитки на доске нет
            {selectedTask && (
              <> — она в наборе {(selectedTask.parentTrack ?? '').trim() || 'без набора'},
                статус {selectedTask.status ?? '—'}, роль {selectedTask.role ?? '—'}</>
            )}
          </p>
          <RailStrip name="tasks-loose-detail" heightMode="natural">
            {detailRail}
          </RailStrip>
        </div>
      )}

      {/* ── ЗАДАЧИ ГРУППАМИ ПО НАБОРАМ ───────────────────────────────────────────
          При отборе одного набора рисуется ровно одна секция — та, что вернула служба;
          без отбора — все группы в её порядке, включая пустые и «без набора». */}
      <div className="tracksecs" data-panel="tasks-by-track">
        {grouped.loading && groups.length === 0 && (
          <p className="muted" data-panel="tasks-loading">читаю задачи…</p>
        )}

        {track === 'all'
          ? groups.map((g) => {
            const key = g.trackId ?? UNTRACKED_KEY;
            return (
              <TrackSection
                key={key}
                group={g}
                tasks={g.items.filter(passes)}
                allTasks={all}
                selectedId={openId}
                onSelect={setOpenId}
                detailRail={
                  detailVisibleInSection && selectedTrackKey === key ? detailRail : undefined
                }
                order={boardOrder}
                nowMs={nowMs}
                collapsed={collapsed.has(key)}
                onToggle={() => toggleCollapsed(key)}
              />
            );
          })
          : (
            <TrackSection
              group={
                pickedGroup ?? {
                  // Набор назван в адресе, а в группах его нет: показываем то, что
                  // вернул отбор, и не делаем вид, что набора не существует.
                  trackId: track === UNTRACKED_KEY ? null : track,
                  title: null,
                  status: null,
                  declared: false,
                  count: filtered.length,
                  items: [],
                }
              }
              tasks={filtered}
              allTasks={all}
              selectedId={openId}
              onSelect={setOpenId}
              detailRail={detailVisibleInSection ? detailRail : undefined}
              order={boardOrder}
              nowMs={nowMs}
              collapsed={false}
              onToggle={() => { /* при отборе одного набора сворачивать нечего */ }}
            />
          )}
      </div>
    </div>
  );
}
