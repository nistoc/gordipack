import { useMemo } from 'react';
import { api } from '../api';
import { usePolling } from '../usePolling';
import { useUrlEnum, useUrlParam } from '../useUrlState';
import type { FlowPoint, RoleRow } from '../historyModel';
import {
  DEFAULT_CLOSED_STATUSES, buildTimelines, computeByRole, computeByStatus, computeFlow,
  dayRange, distinctRoles, distinctStatuses, orderStatusKeys, statusColor, statusRu, todayUtc,
} from '../historyModel';

/**
 * «ДИНАМИКА ЗАДАЧ» — сколько карточек заводится, закрывается и остаётся открытыми,
 * по дням, ролям и статусам.
 *
 * 📌 СЛУЖБА ОТДАЁТ СЫРЬЁ (GET /api/tasks/history), АГРЕГАЦИЮ ДЕЛАЕТ КЛИЕНТ.
 *    Причина та же, что и у доски задач (TasksPage): период/роли/статусы — это
 *    переключатели, а не отдельные запросы. Держать всю арифметику в historyModel.ts
 *    (чистые функции без React) — чтобы её же можно было независимо повторить при
 *    сверке чисел на Python, не Copy-paste'я JSX.
 *
 * Четыре состояния экрана — тот же канон, что у страницы «Схема»: жду ответа ·
 * ответ не пришёл · ответ пришёл пустым (нечем строить график) · вот график.
 */
export function HistoryPage({ refreshMs }: { refreshMs: number }) {
  const history = usePolling(() => api.taskHistory(), refreshMs);

  // ── период ──────────────────────────────────────────────────────────────
  const PERIOD_KEYS = ['7', '14', '30', '90'] as const;
  const [periodKey, setPeriodKey] = useUrlEnum<(typeof PERIOD_KEYS)[number]>(
    'hPeriod', PERIOD_KEYS, '30', 'replace',
  );
  const period = Number(periodKey);
  const days = useMemo(() => dayRange(todayUtc(), period), [period]);

  // ── вид графика ─────────────────────────────────────────────────────────
  const VIEW_KEYS = ['flow', 'status', 'role'] as const;
  const [view, setView] = useUrlEnum<(typeof VIEW_KEYS)[number]>('hView', VIEW_KEYS, 'flow', 'replace');

  // ── роли: «все» или несколько выбранных ────────────────────────────────
  const [rolesRaw, setRolesRaw] = useUrlParam('hRoles', 'replace');
  const selectedRoles = useMemo<Set<string> | null>(() => {
    if (!rolesRaw) return null;
    const set = new Set(rolesRaw.split(',').map((s) => s.trim()).filter(Boolean));
    return set.size > 0 ? set : null;
  }, [rolesRaw]);
  const toggleRole = (role: string) => {
    const next = new Set(selectedRoles ?? []);
    if (next.has(role)) next.delete(role); else next.add(role);
    setRolesRaw(next.size === 0 ? null : [...next].sort().join(','));
  };

  // ── статусы, реально встречающиеся в этой базе (карточки + переходы) ───
  const dataStatuses = useMemo(() => (history.data ? distinctStatuses(history.data) : []), [history.data]);
  // Полотно для чипов «закрытые»/«показывать»: канон + то, что реально есть в базе —
  // так статус, которого в данных сейчас нет, всё равно можно ОБЪЯВИТЬ закрытым заранее.
  const statusUniverse = useMemo(
    () => orderStatusKeys(new Set([...DEFAULT_CLOSED_STATUSES, ...dataStatuses,
      'open', 'in_progress', 'in_review', 'blocked'])),
    [dataStatuses],
  );

  // ── какие статусы считаются «закрытыми» (по умолчанию done/dropped/failed) ─
  const [closedRaw, setClosedRaw] = useUrlParam('hClosed', 'replace');
  const closedSet = useMemo<Set<string>>(() => {
    if (closedRaw === null) return new Set(DEFAULT_CLOSED_STATUSES);
    if (closedRaw === 'none') return new Set();
    return new Set(closedRaw.split(',').map((s) => s.trim()).filter(Boolean));
  }, [closedRaw]);
  const toggleClosed = (status: string) => {
    const next = new Set(closedSet);
    if (next.has(status)) next.delete(status); else next.add(status);
    if (next.size === 0) { setClosedRaw('none'); return; }
    const isDefault = next.size === DEFAULT_CLOSED_STATUSES.length
      && DEFAULT_CLOSED_STATUSES.every((s) => next.has(s));
    setClosedRaw(isDefault ? null : [...next].sort().join(','));
  };

  // ── какие статусы показывать в виде «по статусам» (по умолчанию — все, что есть) ─
  const [showRaw, setShowRaw] = useUrlParam('hShow', 'replace');
  const displayStatuses = useMemo<string[]>(() => {
    if (showRaw === null) return dataStatuses;
    if (showRaw === 'none') return [];
    return orderStatusKeys(new Set(showRaw.split(',').map((s) => s.trim()).filter(Boolean)));
  }, [showRaw, dataStatuses]);
  const toggleShow = (status: string) => {
    const current = new Set(displayStatuses);
    if (current.has(status)) current.delete(status); else current.add(status);
    if (current.size === 0) { setShowRaw('none'); return; }
    const isDefault = current.size === dataStatuses.length && dataStatuses.every((s) => current.has(s));
    setShowRaw(isDefault ? null : [...current].sort().join(','));
  };

  const allRoles = useMemo(() => (history.data ? distinctRoles(history.data.cards) : []), [history.data]);

  // ── агрегация (чистые функции historyModel.ts) ──────────────────────────
  const timelines = useMemo(() => (history.data ? buildTimelines(history.data) : []), [history.data]);
  const flow = useMemo(
    () => (view === 'flow' ? computeFlow(timelines, days, closedSet, selectedRoles) : null),
    [view, timelines, days, closedSet, selectedRoles],
  );
  const byStatus = useMemo(
    () => (view === 'status' ? computeByStatus(timelines, days, displayStatuses, selectedRoles) : null),
    [view, timelines, days, displayStatuses, selectedRoles],
  );
  const byRole = useMemo(
    () => (view === 'role' ? computeByRole(timelines, days, closedSet, selectedRoles) : null),
    [view, timelines, days, closedSet, selectedRoles],
  );

  // ── состояние 1: жду ответа ──────────────────────────────────────────────
  if (!history.data && history.loading && !history.error) {
    return (
      <div className="page" data-panel="history" data-state="loading">
        <div className="banner" data-item="history-loading">Читаю карточки и переходы статуса…</div>
      </div>
    );
  }

  // ── состояние 2: ответ не пришёл ─────────────────────────────────────────
  if (!history.data) {
    const oldBackend = (history.error ?? '').includes('404');
    return (
      <div className="page" data-panel="history" data-state="error">
        <div className="banner banner--error" data-item="history-error">
          <strong>Не удалось прочитать динамику задач.</strong>
          <div className="small" style={{ marginTop: 4 }}>
            {oldBackend
              ? 'сервис старее этой вкладки: нет /api/tasks/history — перезапустите бэкенд'
              : (history.error ?? 'сервис не ответил и причины не назвал')}
          </div>
          <div className="small muted" style={{ marginTop: 4 }}>
            Это сообщение о СБОЕ ЧТЕНИЯ, а не о том, что задач нет.
          </div>
        </div>
        <button className="btn btn--ghost" onClick={history.reload} data-control="history-retry">
          Прочитать ещё раз
        </button>
      </div>
    );
  }

  // ── состояние 3: ответ пришёл, а строить не из чего ─────────────────────
  if (!history.data.supported) {
    return (
      <div className="page" data-panel="history" data-state="unsupported">
        <div className="banner banner--warn" data-item="history-unsupported">
          <strong>В этой базе динамику задач посчитать нечем.</strong>
          <div className="small" style={{ marginTop: 4 }}>{history.data.note}</div>
        </div>
      </div>
    );
  }
  if (history.data.cards.length === 0) {
    return (
      <div className="page" data-panel="history" data-state="empty">
        <div className="banner banner--warn" data-item="history-empty">
          <strong>В этой базе нет ни одной карточки задачи.</strong>
          <div className="small" style={{ marginTop: 4 }}>
            Сервис ответил успешно — таблица backlog прочитана и пуста.
          </div>
        </div>
      </div>
    );
  }

  // ── состояние 4: данные ──────────────────────────────────────────────────
  return (
    <div className="page" data-panel="history" data-state="ready">
      {history.error && (
        <div className="banner banner--error" data-item="history-stale">
          Последнее обновление не удалось: {history.error}. Ниже — то, что было прочитано раньше.
        </div>
      )}

      {!history.data.eventsSupported && (
        <div className="banner banner--warn" data-item="history-events-unsupported">
          {history.data.eventsNote}
        </div>
      )}

      {/* ── вид графика ─────────────────────────────────────────────────── */}
      <div className="filterbar" data-group="history-view-bar">
        <span className="filterbar__label">Вид</span>
        <button className={`fchip ${view === 'flow' ? 'fchip--on' : ''}`} onClick={() => setView('flow')} data-control="history-view-flow">Поток</button>
        <button className={`fchip ${view === 'status' ? 'fchip--on' : ''}`} onClick={() => setView('status')} data-control="history-view-status">По статусам</button>
        <button className={`fchip ${view === 'role' ? 'fchip--on' : ''}`} onClick={() => setView('role')} data-control="history-view-role">По ролям</button>
      </div>

      {/* ── период ──────────────────────────────────────────────────────── */}
      <div className="filterbar" data-group="history-period-bar">
        <span className="filterbar__label">Период</span>
        {PERIOD_KEYS.map((p) => (
          <button
            key={p}
            className={`fchip ${periodKey === p ? 'fchip--on' : ''}`}
            onClick={() => setPeriodKey(p)}
            data-control={`history-period-${p}`}
          >
            {p} дней
          </button>
        ))}
      </div>

      {/* ── роли ────────────────────────────────────────────────────────── */}
      <div className="filterbar" data-group="history-role-bar">
        <span className="filterbar__label">Роли</span>
        <button
          className={`fchip ${selectedRoles === null ? 'fchip--on' : ''}`}
          onClick={() => setRolesRaw(null)}
          data-control="history-role-all"
        >
          все
        </button>
        {allRoles.map((r) => (
          <button
            key={r}
            className={`fchip fchip--role ${selectedRoles?.has(r) ? 'fchip--on' : ''}`}
            onClick={() => toggleRole(r)}
            data-control={`history-role-${r}`}
          >
            {r}
          </button>
        ))}
      </div>

      {/* ── закрытые статусы (влияют на «Поток» и «По ролям») ──────────────── */}
      {view !== 'status' && (
        <div className="filterbar" data-group="history-closed-bar">
          <span className="filterbar__label">Закрытые</span>
          {statusUniverse.map((s) => (
            <button
              key={s}
              className={`fchip ${closedSet.has(s) ? 'fchip--on' : ''}`}
              onClick={() => toggleClosed(s)}
              data-control={`history-closed-${s}`}
              title="статус считается «закрытым» — переход в него = «закрыто», карточка в нём не входит в «открыто»"
            >
              {statusRu(s)}
            </button>
          ))}
        </div>
      )}

      {/* ── какие статусы показывать (влияет на «По статусам») ────────────── */}
      {view === 'status' && (
        <div className="filterbar" data-group="history-show-bar">
          <span className="filterbar__label">Показывать</span>
          {statusUniverse.map((s) => (
            <button
              key={s}
              className={`fchip ${displayStatuses.includes(s) ? 'fchip--on' : ''}`}
              onClick={() => toggleShow(s)}
              data-control={`history-show-${s}`}
            >
              {statusRu(s)}
            </button>
          ))}
        </div>
      )}

      {/* ── вид а) Поток ────────────────────────────────────────────────── */}
      {view === 'flow' && flow && (
        <div data-panel="history-flow">
          <div className="history-summary" data-group="history-flow-summary">
            новых <b>{flow.newTotal}</b> · закрыто <b>{flow.closedTotal}</b> · открыто было{' '}
            <b>{flow.openBefore}</b> → стало <b>{flow.points[flow.points.length - 1]?.openEnd ?? 0}</b>
          </div>
          <div className="history-chart-wrap">
            <FlowChart points={flow.points} />
          </div>
          <FlowLegend />
        </div>
      )}

      {/* ── вид б) По статусам ──────────────────────────────────────────── */}
      {view === 'status' && byStatus && (
        <div data-panel="history-status">
          {displayStatuses.length === 0 ? (
            <p className="muted" data-item="history-status-none">
              ни одного статуса не выбрано для показа — отметьте хотя бы один в строке «Показывать»
            </p>
          ) : (
            <>
              <div className="history-chart-wrap">
                <StatusChart days={days} series={byStatus} order={displayStatuses} />
              </div>
              <StatusLegend order={displayStatuses} />
            </>
          )}
        </div>
      )}

      {/* ── вид в) По ролям ─────────────────────────────────────────────── */}
      {view === 'role' && byRole && (
        <div data-panel="history-role">
          <div className="history-chart-wrap">
            <RoleChart rows={byRole} />
          </div>
          <RoleLegend />
        </div>
      )}
    </div>
  );
}

// ── вспомогательное: сетка оси и подписи дней ─────────────────────────────

/**
 * Сетка оси Y. ВЕРХ ШКАЛЫ ОБЯЗАН БЫТЬ НЕ МЕНЬШЕ max, а не «ближайший подходящий шаг
 * снизу» — прежняя версия считала последнюю подпись условием `v <= max`, и при
 * max между двумя шагами (216 при шаге 50) верхней подписью оказывались «200»,
 * а точки/столбцы выше 200 рисовались ЗА пределами области графика. Замер владельца
 * 2026-09-14: «Поток»/30 дней — линия «открыто на конец дня» уходит за верхний край
 * после 06.09 (216 против подписи 200); «По статусам» — стопка ~610 при подписи 600.
 * Здесь — сперва ближайший «круглый» верх НЕ МЕНЬШЕ max, затем, если он совпал
 * с max почти вплотную (меньше 20% шага запаса), добавляется ещё один шаг —
 * чтобы верхняя точка не липла к самому краю графика.
 *
 * ⚠️ ШАГ ОБЯЗАН БЫТЬ ЦЕЛЫМ (≥ 1). Второй замер владельца 2026-09-14 (роль TAXO,
 *    30 дней): при малом max (например 1) прежний расчёт давал ДРОБНЫЙ шаг
 *    (0.2 — mag получался меньше единицы), и Math.round схлопывал соседние
 *    дробные отметки в ОДНО И ТО ЖЕ целое число (0,0,0,1,1,1,1 → после round
 *    видны повторы). Ось считает штуки задач — дробной отметки не бывает
 *    в принципе, — а повтор значения давал ПОВТОРЯЮЩИЙСЯ React key, из-за чего
 *    при смене фильтра старые подписи не убирались и налезали на новые
 *    («14 · 12 · 10 · 2 · 8 · 6 · 1 · 4 · 2 · 0» на снимке владельца).
 *    Починка — `mag` никогда не бывает меньше 1, значит и `step` тоже: тик
 *    считается ДО округления, а не после, и повторов не возникает по построению.
 */
function axisTicks(max: number): number[] {
  const safeMax = Math.max(1, Math.ceil(max));
  const rough = safeMax / 4;
  const mag = Math.max(1, 10 ** Math.floor(Math.log10(rough || 1)));
  const norm = rough / mag;
  const step = Math.max(1, norm >= 5 ? 5 * mag : norm >= 2 ? 2 * mag : mag);
  let top = Math.ceil(safeMax / step) * step;
  if (top - safeMax < step * 0.2) top += step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + 0.5; v += step) ticks.push(v);
  return ticks;
}

function tickDayIndices(n: number, maxTicks = 10): number[] {
  if (n <= maxTicks) return Array.from({ length: n }, (_, i) => i);
  const step = Math.ceil(n / maxTicks);
  const idx: number[] = [];
  for (let i = 0; i < n; i += step) idx.push(i);
  if (idx[idx.length - 1] !== n - 1) idx.push(n - 1);
  return idx;
}

// ── SVG: вид а) Поток ───────────────────────────────────────────────────────

/**
 * ДВЕ ОСИ Y, А НЕ ОДНА ОБЩАЯ — слово владельца 2026-09-14 (снимок: роль TAXO,
 * 30 дней). Раньше столбцы («новых»/«закрыто») и линия («открыто на конец дня»)
 * делили одну шкалу, и при малом числе новых/закрытых (частый случай у роли
 * с небольшим потоком) столбцы становились почти незаметны на фоне линии,
 * потому что верх шкалы считался по МАКСИМУМУ ИЗ ВСЕХ ТРЁХ величин сразу.
 * ЛЕВАЯ шкала — от max(created, closed): по ней столбцы и горизонтальная сетка
 * (сетка — только левая, чтобы не было двух наложенных сеток). ПРАВАЯ шкала —
 * от max(openEnd): по ней линия и точки, без своей сетки — только короткая
 * засечка у правого края на каждый тик. Цифры разных цветов (левая — нейтральная
 * var(--muted), правая — var(--warn), тот же оранжевый, что у линии), и подписи
 * осей сверху слева/справа словами говорят, какая шкала чья.
 */
function FlowChart({ points }: { points: FlowPoint[] }) {
  const W = 900;
  const H = 300;
  const padL = 40;
  // ⚠️ padR ≥ 40 — под цифры правой шкалы (слово владельца, пункт 2): при 16,
  //    как было раньше, подписи правой оси обрезались бы краем SVG.
  const padR = 44;
  const padT = 26;
  const padB = 46;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const n = Math.max(1, points.length);

  const leftMax = Math.max(1, ...points.map((p) => Math.max(p.created, p.closed)));
  const leftTicks = axisTicks(leftMax);
  const leftYMax = leftTicks[leftTicks.length - 1] || leftMax;
  const rightMax = Math.max(1, ...points.map((p) => p.openEnd));
  const rightTicks = axisTicks(rightMax);
  const rightYMax = rightTicks[rightTicks.length - 1] || rightMax;

  const y0 = padT + innerH;
  const leftScale = innerH / leftYMax;
  const rightScale = innerH / rightYMax;
  const yLeft = (v: number) => y0 - v * leftScale;
  const yRight = (v: number) => y0 - v * rightScale;

  const groupW = innerW / n;
  const barW = Math.max(1, groupW * 0.32);
  const tickIdx = tickDayIndices(points.length);

  const linePoints = points
    .map((p, i) => `${(padL + groupW * (i + 0.5)).toFixed(1)},${yRight(p.openEnd).toFixed(1)}`)
    .join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="history-svg" role="img" aria-label="Поток задач по дням — две шкалы: слева новых/закрыто, справа открыто">
      {/* подписи осей — какая шкала чья, словами и цветом */}
      {/* слова левой подписи — цветами своих столбцов, как «открыто» справа цветом линии */}
      <text x={padL} y={14} textAnchor="start" fontSize={10} fill="var(--muted)">
        <tspan fill="var(--info)">новых</tspan> · <tspan fill="var(--good)">закрыто</tspan>
      </text>
      <text x={W - padR} y={14} textAnchor="end" fontSize={10} fill="var(--warn)">открыто</text>

      {/* сетка и подписи — ТОЛЬКО левая шкала, чтобы не накладывать две сетки */}
      {leftTicks.map((t, i) => (
        <g key={`L-${i}`}>
          <line x1={padL} x2={W - padR} y1={yLeft(t)} y2={yLeft(t)} stroke="var(--border)" strokeWidth={1} />
          <text x={padL - 6} y={yLeft(t) + 3} textAnchor="end" fontSize={10} fill="var(--muted)">{t}</text>
        </g>
      ))}

      {/* правая шкала — короткая засечка у края + цифра тем же цветом, что линия */}
      {rightTicks.map((t, i) => (
        <g key={`R-${i}`}>
          <line x1={W - padR} x2={W - padR + 5} y1={yRight(t)} y2={yRight(t)} stroke="var(--warn)" strokeWidth={1} />
          <text x={W - padR + 8} y={yRight(t) + 3} textAnchor="start" fontSize={10} fill="var(--warn)">{t}</text>
        </g>
      ))}

      {points.map((p, i) => {
        const cx = padL + groupW * i + groupW / 2;
        return (
          <g key={p.day}>
            <title>{`${p.day} UTC — новых ${p.created} · закрыто ${p.closed} · открыто на конец дня ${p.openEnd}`}</title>
            <rect x={cx - barW - 1} y={yLeft(p.created)} width={barW} height={Math.max(0, y0 - yLeft(p.created))} fill="var(--info)" />
            <rect x={cx + 1} y={yLeft(p.closed)} width={barW} height={Math.max(0, y0 - yLeft(p.closed))} fill="var(--good)" />
          </g>
        );
      })}

      <polyline points={linePoints} fill="none" stroke="var(--warn)" strokeWidth={2} />
      {points.map((p, i) => (
        <circle key={`c-${p.day}`} cx={padL + groupW * (i + 0.5)} cy={yRight(p.openEnd)} r={2.6} fill="var(--warn)">
          <title>{`${p.day} UTC — открыто на конец дня: ${p.openEnd}`}</title>
        </circle>
      ))}

      {tickIdx.map((i) => {
        const cx = padL + groupW * (i + 0.5);
        return (
          <text
            key={i}
            x={cx}
            y={H - padB + 16}
            textAnchor="end"
            fontSize={10}
            fill="var(--muted)"
            transform={`rotate(-55 ${cx} ${H - padB + 16})`}
          >
            {points[i].day.slice(5)}
          </text>
        );
      })}
    </svg>
  );
}

function FlowLegend() {
  return (
    <div className="history-legend" data-group="history-flow-legend">
      <span><i className="history-legend__swatch" style={{ background: 'var(--info)' }} /> новых</span>
      <span><i className="history-legend__swatch" style={{ background: 'var(--good)' }} /> закрыто</span>
      <span><i className="history-legend__swatch" style={{ background: 'var(--warn)' }} /> открыто на конец дня (правая шкала)</span>
    </div>
  );
}

// ── SVG: вид б) По статусам ──────────────────────────────────────────────────

function StatusChart({ days, series, order }: { days: string[]; series: Map<string, number[]>; order: string[] }) {
  const W = 900;
  const H = 320;
  const padL = 40;
  const padR = 16;
  const padT = 14;
  const padB = 46;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const n = Math.max(1, days.length);
  const totals = days.map((_, i) => order.reduce((a, s) => a + (series.get(s)?.[i] ?? 0), 0));
  const maxVal = Math.max(1, ...totals);
  const ticks = axisTicks(maxVal);
  const yMax = ticks[ticks.length - 1] || maxVal;
  const y0 = padT + innerH;
  const scale = innerH / yMax;
  const groupW = innerW / n;
  const barW = Math.max(1, groupW * 0.62);
  const tickIdx = tickDayIndices(days.length);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="history-svg" role="img" aria-label="Задачи по статусам, по дням">
      {ticks.map((t, i) => (
        <g key={`t-${i}`}>
          <line x1={padL} x2={W - padR} y1={y0 - t * scale} y2={y0 - t * scale} stroke="var(--border)" strokeWidth={1} />
          <text x={padL - 6} y={y0 - t * scale + 3} textAnchor="end" fontSize={10} fill="var(--muted)">{t}</text>
        </g>
      ))}

      {days.map((day, i) => {
        let acc = 0;
        const x = padL + groupW * i + (groupW - barW) / 2;
        return (
          <g key={day}>
            {order.map((status) => {
              const v = series.get(status)?.[i] ?? 0;
              if (v === 0) return null;
              const segY = y0 - (acc + v) * scale;
              const segH = v * scale;
              acc += v;
              return (
                <rect key={status} x={x} y={segY} width={barW} height={segH} fill={statusColor(status, order)}>
                  <title>{`${day} UTC — ${statusRu(status)}: ${v}`}</title>
                </rect>
              );
            })}
          </g>
        );
      })}

      {tickIdx.map((i) => {
        const cx = padL + groupW * (i + 0.5);
        return (
          <text
            key={i}
            x={cx}
            y={H - padB + 16}
            textAnchor="end"
            fontSize={10}
            fill="var(--muted)"
            transform={`rotate(-55 ${cx} ${H - padB + 16})`}
          >
            {days[i].slice(5)}
          </text>
        );
      })}
    </svg>
  );
}

function StatusLegend({ order }: { order: string[] }) {
  return (
    <div className="history-legend" data-group="history-status-legend">
      {order.map((s) => (
        <span key={s}>
          <i className="history-legend__swatch" style={{ background: statusColor(s, order) }} /> {statusRu(s)}
        </span>
      ))}
    </div>
  );
}

// ── SVG: вид в) По ролям ──────────────────────────────────────────────────────

function RoleChart({ rows }: { rows: RoleRow[] }) {
  const W = 900;
  const rowH = 34;
  const padL = 90;
  const padR = 60;
  const padT = 16;
  const H = padT + rows.length * rowH + 8;
  const innerW = W - padL - padR;
  const maxVal = Math.max(1, ...rows.flatMap((r) => [r.created, r.closed, r.openNow]));
  const scale = innerW / maxVal;
  const barH = 8;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="history-svg" role="img" aria-label="Задачи по ролям">
      {rows.map((r, i) => {
        const yBase = padT + i * rowH;
        const isTotal = r.role === 'всего';
        return (
          <g key={r.role}>
            {isTotal && (
              <line x1={0} x2={W} y1={yBase - 8} y2={yBase - 8} stroke="var(--border)" strokeWidth={1} />
            )}
            <text
              x={padL - 8}
              y={yBase + barH * 1.5 + 4}
              textAnchor="end"
              fontSize={11}
              fill={isTotal ? 'var(--text)' : 'var(--muted)'}
              fontWeight={isTotal ? 700 : 400}
            >
              {r.role}
            </text>

            <rect x={padL} y={yBase} width={Math.max(0.5, r.created * scale)} height={barH} fill="var(--info)">
              <title>{`${r.role} — новых: ${r.created}`}</title>
            </rect>
            <text x={padL + r.created * scale + 4} y={yBase + barH} fontSize={10} fill="var(--muted)">{r.created}</text>

            <rect x={padL} y={yBase + barH + 2} width={Math.max(0.5, r.closed * scale)} height={barH} fill="var(--good)">
              <title>{`${r.role} — закрыто за период: ${r.closed}`}</title>
            </rect>
            <text x={padL + r.closed * scale + 4} y={yBase + barH * 2 + 2} fontSize={10} fill="var(--muted)">{r.closed}</text>

            <rect x={padL} y={yBase + (barH + 2) * 2} width={Math.max(0.5, r.openNow * scale)} height={barH} fill="var(--warn)">
              <title>{`${r.role} — открыто сейчас: ${r.openNow}`}</title>
            </rect>
            <text x={padL + r.openNow * scale + 4} y={yBase + barH * 3 + 4} fontSize={10} fill="var(--muted)">{r.openNow}</text>
          </g>
        );
      })}
    </svg>
  );
}

function RoleLegend() {
  return (
    <div className="history-legend" data-group="history-role-legend">
      <span><i className="history-legend__swatch" style={{ background: 'var(--info)' }} /> новых</span>
      <span><i className="history-legend__swatch" style={{ background: 'var(--good)' }} /> закрыто за период</span>
      <span><i className="history-legend__swatch" style={{ background: 'var(--warn)' }} /> открыто сейчас</span>
    </div>
  );
}
