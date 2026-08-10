import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Overview, Task, TaskDetail } from '../types';
import { fmtUtc } from '../format';
import { StatCard } from '../components/MeasureValue';
import { Rail } from '../components/Rail';
import { PriorityMark, StatusMark } from '../components/TaskTile';
import { useUrlEnum, useUrlNumber, useUrlParam } from '../useUrlState';
import { TasksBoard } from './TasksBoard';
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

  const status = statusRaw ?? 'open';
  const role = roleRaw ?? 'all';
  const onlyMissing = gapRaw === '1';
  const setStatus = (v: string) => setStatusRaw(v === 'open' ? null : v);
  const setRole = (v: string) => setRoleRaw(v === 'all' ? null : v);
  const setOnlyMissing = (v: boolean) => setGapRaw(v ? '1' : null);

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

  const tasks = usePolling<Task[]>(() => api.tasks({ status: 'all' }), refreshMs, []);
  const all = useMemo(() => tasks.data ?? [], [tasks.data]);

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

  const filtered = useMemo(() => all.filter((t) => {
    if (status !== 'all' && t.status !== status) return false;
    if (role !== 'all' && t.role !== role) return false;
    if (onlyMissing && !isCriterionGap(t)) return false;
    return true;
  }), [all, status, role, onlyMissing]);

  const criterionUnsupported = all.length > 0 && all.every((t) => !t.criterionSupported);
  const statusKeys = orderStatuses(statusCounts.keys());
  const roleKeys = [...roleCounts.keys()].sort();
  const gapsShown = filtered.filter(isCriterionGap).length;

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

      {tasks.error && (
        <div className="banner banner--error" data-panel="tasks-error">{tasks.error}</div>
      )}

      <TasksBoard
        tasks={filtered}
        allTasks={all}
        selectedId={openId}
        onSelect={setOpenId}
        detailRail={detailRail}
        order={boardOrder}
        nowMs={nowMs}
      />
    </div>
  );
}
