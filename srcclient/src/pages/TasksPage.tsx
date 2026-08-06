import { useMemo, useState } from 'react';
import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Overview, Task, TaskDetail } from '../types';
import { fmtUtc, fmtUtcBare } from '../format';
import { StatCard } from '../components/MeasureValue';
import { Rail, RailStrip } from '../components/Rail';
import { useUrlNumber } from '../useUrlState';

const PRIORITY_RANK: Record<string, number> = { critical: 0, high: 1, normal: 2, low: 3 };

const STATUS_TITLE: Record<string, string> = {
  open: 'открытые',
  done: 'закрытые',
  blocked: 'заблокированные',
  dropped: 'снятые',
};

/**
 * ШИРИНЫ РЕЙЛОВ — СЧИТАНЫ ОТ СОДЕРЖИМОГО, А НЕ ВЗЯТЫ ДОЛЯМИ ОТ ЭКРАНА.
 *
 * Таблица несёт восемь колонок, семь из них с заданной шириной:
 *     # 4rem + статус 6 + важность 6 + роль 7 + критерий 13 + создано 8.5 + изменено 8.5 = 53rem = 848px
 * плюс заголовок, которому нужно хотя бы ~280px, чтобы не рваться на каждом слове.
 * Отсюда пол 1130px: НИЖЕ ЭТОГО КОЛОНКИ НАЧНУТ ПРЯТАТЬСЯ.
 *
 * ЗАМЕР 2026-08-06 17:47 UTC, ПОЧЕМУ ШИРИНЫ УМЕНЬШИЛИСЬ. Прежний набор (даты по 10rem,
 * ширина по умолчанию 1320) на окне 1265px давал полосу шире окна на 95px, и колонка
 * «изменено» уходила за правый край — то есть колонка была добавлена и НЕ ВИДНА.
 * Место съедал суффикс «UTC», повторённый в каждой из 82 ячеек; он переехал в ШАПКУ
 * колонки, где сказан один раз и остаётся явным. Ширина по умолчанию посажена под
 * типовое окно, а не под мой экран: колонка, которую надо доскроллить, для владельца
 * не существует.
 */
const TABLE_RAIL = { defaultWidth: 1210, minWidth: 1130, maxWidth: 1900 };
const DETAIL_RAIL = { defaultWidth: 560, minWidth: 380, maxWidth: 900 };

type SortKey = 'gap' | 'id' | 'status' | 'priority' | 'role' | 'title' | 'criterion' | 'createdAt' | 'updatedAt';

const COLUMNS: Array<{ key: SortKey; title: string; width?: string }> = [
  { key: 'id', title: '#', width: '4rem' },
  { key: 'status', title: 'статус', width: '6rem' },
  { key: 'priority', title: 'важность', width: '6rem' },
  { key: 'role', title: 'роль', width: '7rem' },
  { key: 'title', title: 'заголовок' },
  { key: 'criterion', title: 'критерий приёмки', width: '13rem' },
  { key: 'createdAt', title: 'создано, UTC', width: '8.5rem' },
  { key: 'updatedAt', title: 'изменено, UTC', width: '8.5rem' },
];

/**
 * Главная страница: задачи и — прежде всего — те из них, у которых НЕТ критерия
 * приёмки. Замер живой базы 2026-08-06 17:17 UTC: карточек 78, открытых 39, и у 25
 * из них поле критерия пустое. (Дата у числа обязательна: база живая, за час
 * значения менялись трижды.)
 *
 * 📌 ФИЛЬТРУЕМ НА КЛИЕНТЕ, а не запросом на каждый чих. Причина не в скорости:
 * переключатели обязаны показывать ЧЕСТНЫЕ СЧЁТЧИКИ («открытых 39, закрытых 39»),
 * а счётчик по уже отфильтрованному набору считал бы сам себя. Карточек меньше сотни —
 * цена одного полного чтения ничтожна против цифры, которая врёт.
 */
export function TasksPage({ overview, refreshMs }: { overview: Overview | null; refreshMs: number }) {
  const [status, setStatus] = useState('open');
  const [role, setRole] = useState('all');
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'gap', dir: 1 });
  // Какая карточка открыта — в адресе страницы: «назад» и перезагрузка возвращают к ней,
  // а ссылку можно отдать другому.
  const [openId, setOpenId] = useUrlNumber('task');

  const tasks = usePolling<Task[]>(() => api.tasks({ status: 'all' }), refreshMs, []);
  const all = useMemo(() => tasks.data ?? [], [tasks.data]);

  const detail = usePolling<TaskDetail | null>(
    () => (openId === null ? Promise.resolve(null) : api.task(openId)),
    0,
    [openId],
  );

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
    if (onlyMissing && !(t.criterionSupported && !t.hasCriterion)) return false;
    return true;
  }), [all, status, role, onlyMissing]);

  const sorted = useMemo(() => {
    const list = [...filtered];
    const cmp = (a: Task, b: Task): number => {
      switch (sort.key) {
        // Порядок по умолчанию: сначала то, ради чего страница, — открытые без критерия.
        case 'gap': {
          const g = (t: Task) => (t.criterionSupported && !t.hasCriterion && t.status === 'open' ? 0 : 1);
          if (g(a) !== g(b)) return g(a) - g(b);
          const p = (t: Task) => PRIORITY_RANK[t.priority ?? 'normal'] ?? 9;
          if (p(a) !== p(b)) return p(a) - p(b);
          return a.id - b.id;
        }
        case 'id': return a.id - b.id;
        case 'priority':
          return (PRIORITY_RANK[a.priority ?? 'normal'] ?? 9) - (PRIORITY_RANK[b.priority ?? 'normal'] ?? 9);
        // Критерий сортируем по НАЛИЧИЮ, а не по тексту: вопрос «у кого его нет»,
        // а не «чей текст начинается с буквы А».
        case 'criterion': {
          const c = (t: Task) => (!t.criterionSupported ? 2 : t.hasCriterion ? 1 : 0);
          if (c(a) !== c(b)) return c(a) - c(b);
          return a.id - b.id;
        }
        case 'createdAt':
        case 'updatedAt': {
          const x = (a[sort.key] ?? '') as string;
          const y = (b[sort.key] ?? '') as string;
          return x < y ? -1 : x > y ? 1 : 0;
        }
        default: {
          const x = String(a[sort.key] ?? '');
          const y = String(b[sort.key] ?? '');
          return x.localeCompare(y, 'ru');
        }
      }
    };
    list.sort((a, b) => cmp(a, b) * sort.dir);
    return list;
  }, [filtered, sort]);

  const onSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));

  const criterionUnsupported = all.length > 0 && all.every((t) => !t.criterionSupported);
  const statusKeys = ['open', 'done', 'blocked', 'dropped'].filter((s) => statusCounts.has(s));
  const roleKeys = [...roleCounts.keys()].sort();

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
          Пустой столбец ниже означает «поля нет», а не «критерий не задан».
        </div>
      )}

      <RailStrip name="tasks">
        <Rail
          id="tasks-list"
          title="Задачи"
          {...TABLE_RAIL}
          toolbar={
            <span className="muted" data-control="tasks-count">
              показано {sorted.length} из {all.length}
            </span>
          }
        >
          {/* Переключатели строкой, а не выпадающим списком: видно ВСЕ значения сразу
              и сколько за каждым стоит. Список прячет и состав, и объём. */}
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
            {sort.key !== 'gap' && (
              <button
                className="fchip"
                onClick={() => setSort({ key: 'gap', dir: 1 })}
                data-control="sort-reset"
                title="вернуть порядок по умолчанию: сначала открытые без критерия"
              >
                ↺ порядок по умолчанию
              </button>
            )}
          </div>

          {tasks.error && (
            <div className="banner banner--error" data-panel="tasks-error">{tasks.error}</div>
          )}

          <table className="table" data-list="tasks-table">
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    style={c.width ? { width: c.width } : undefined}
                    className={`th-sort ${sort.key === c.key ? 'th-sort--on' : ''}`}
                    onClick={() => onSort(c.key)}
                    data-control={`sort-${c.key}`}
                    title="щёлкнуть — сортировать; ещё раз — в обратную сторону"
                  >
                    {c.title}
                    <span className="th-sort__mark">
                      {sort.key === c.key ? (sort.dir === 1 ? '▲' : '▼') : '↕'}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((t) => {
                const gap = t.criterionSupported && !t.hasCriterion;
                return (
                  <tr
                    key={t.id}
                    className={`row ${gap ? 'row--gap' : ''} ${openId === t.id ? 'row--open' : ''}`}
                    onClick={() => setOpenId(openId === t.id ? null : t.id)}
                    data-item={`task-${t.id}`}
                  >
                    <td className="mono">{t.id}</td>
                    <td><span className={`chip chip--${t.status ?? 'unknown'}`}>{t.status}</span></td>
                    <td><span className={`chip chip--p-${t.priority ?? 'normal'}`}>{t.priority}</span></td>
                    <td className="mono">{t.role}</td>
                    <td>
                      {t.title}
                      {t.tags.length > 0 && (
                        <span className="tags">
                          {t.tags.map((tag) => <span key={tag} className="tag">{tag}</span>)}
                        </span>
                      )}
                    </td>
                    <td>
                      {!t.criterionSupported
                        ? <span className="muted">поля нет в базе</span>
                        : t.hasCriterion
                          ? <span className="criterion" title={t.doneWhen ?? ''}>{t.doneWhen}</span>
                          : <span className="badge badge--gap">критерий не задан</span>}
                    </td>
                    <td className="mono muted" title={fmtUtc(t.createdAt, true)}>{fmtUtcBare(t.createdAt)}</td>
                    <td className="mono muted" title={fmtUtc(t.updatedAt, true)}>{fmtUtcBare(t.updatedAt)}</td>
                  </tr>
                );
              })}
              {sorted.length === 0 && !tasks.loading && (
                <tr data-item="tasks-empty">
                  <td colSpan={COLUMNS.length} className="muted">под фильтр ничего не попало</td>
                </tr>
              )}
            </tbody>
          </table>
        </Rail>

        {openId !== null && (
          <Rail
            id="task-detail"
            title={`Карточка #${openId}`}
            {...DETAIL_RAIL}
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
                  {detail.data.task.role} · {detail.data.task.status} · {detail.data.task.priority}
                  <br />
                  создано {fmtUtc(detail.data.task.createdAt)}
                  <br />
                  изменено {fmtUtc(detail.data.task.updatedAt)}
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
        )}
      </RailStrip>
    </div>
  );
}
