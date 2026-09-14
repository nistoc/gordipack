import type { TaskHistory, TaskHistoryCard, TaskHistoryEvent } from './types';

/**
 * АГРЕГАЦИЯ ДЛЯ СТРАНИЦЫ «ДИНАМИКА ЗАДАЧ» — чистые функции, без React.
 *
 * 📌 Почему вся арифметика здесь, а не в компоненте: тот же список карточек и
 *    переходов пересчитывается под три разных вида графика и любой набор фильтров
 *    (период/роли/статусы) без нового обращения к сети (см. GET /api/tasks/history —
 *    служба отдаёт сырьё, агрегирует клиент). Чистые функции значит и то, что эту
 *    же логику можно независимо повторить на Python при сверке чисел — она не тянет
 *    за собой ни DOM, ни React.
 */

// ── статусы: русские подписи (СЛОВО ВЛАДЕЛЬЦА — конкретный список, не выдумывать) ──

export const STATUS_RU: Record<string, string> = {
  open: 'открыта',
  in_progress: 'в работе',
  in_review: 'на проверке',
  blocked: 'заблокирована',
  // Так же зовёт этот статус инструмент карточек задач (backlog) — слово владельца 2026-09-14.
  awaiting_word: 'ждёт слова',
  done: 'сделана',
  dropped: 'снята',
  failed: 'не удалась',
};

/** Неизвестный статус — как есть (слово владельца), а не переведён наугад и не спрятан. */
export function statusRu(status: string | null | undefined): string {
  if (!status) return '—';
  return STATUS_RU[status] ?? status;
}

/**
 * Порядок статусов по смыслу (живое выше завершённого) — тот же принцип, что и
 * в taskModel.ts (STATUS_ORDER), но со своим списком: там нет in_progress/failed,
 * а здесь они предусмотрены явно (слово владельца перечисляет оба).
 */
export const STATUS_ORDER = [
  'open', 'in_progress', 'in_review', 'blocked', 'awaiting_word', 'done', 'dropped', 'failed',
];

export function orderStatusKeys(present: Iterable<string>): string[] {
  const keys = [...present];
  const rest = keys.filter((s) => !STATUS_ORDER.includes(s)).sort();
  return [...STATUS_ORDER.filter((s) => keys.includes(s)), ...rest];
}

/** Статусы, которые по умолчанию считаются «закрытыми» — задание из описания задачи. */
export const DEFAULT_CLOSED_STATUSES: readonly string[] = ['done', 'dropped', 'failed'];

/**
 * Цвет статуса на графике — ПО МЕСТУ В КАНОНЕ, а не по смыслу отдельного статуса:
 * так гарантируется, что сколько бы статусов ни нашлось в базе, каждому достанется
 * свой цвет и они не столкнутся. Первые шесть — переменные темы (значит меняются
 * вместе со светлой/тёмной темой), дальше — запасные оттенки для редких статусов.
 */
const PALETTE = [
  'var(--warn)', 'var(--info)', 'var(--accent2)', 'var(--accent)',
  'var(--good)', 'var(--muted)', '#3aa6a0', '#c77dff',
];

export function statusColor(status: string, order: readonly string[]): string {
  const idx = order.indexOf(status);
  return PALETTE[(idx >= 0 ? idx : order.length) % PALETTE.length];
}

// ── время: день в UTC ────────────────────────────────────────────────────────

/** 'YYYY-MM-DD' — начало строки времени. База и сервис отдают время в UTC (правило контура),
 *  поэтому строковый срез достаточен и не требует разбора часового пояса. */
export function dayOf(value: string | null | undefined): string | null {
  if (!value) return null;
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(value);
  return m ? m[1] : null;
}

export function todayUtc(nowMs = Date.now()): string {
  return new Date(nowMs).toISOString().slice(0, 10);
}

export function addDaysUtc(day: string, delta: number): string {
  return new Date(new Date(`${day}T00:00:00Z`).getTime() + delta * 86_400_000)
    .toISOString().slice(0, 10);
}

/** periodDays дней, включая endDay, шагом день — от старого к новому. */
export function dayRange(endDay: string, periodDays: number): string[] {
  const days: string[] = [];
  for (let i = periodDays - 1; i >= 0; i--) days.push(addDaysUtc(endDay, -i));
  return days;
}

// ── карточка + её переходы во времени ───────────────────────────────────────

export interface CardTimeline {
  card: TaskHistoryCard;
  createdDay: string | null;
  /** Статус при заведении — см. правило в buildTimelines. */
  initialStatus: string | null;
  /** Переходы этой карточки В ПОРЯДКЕ ВВОДА (как пришли с сервера — ORDER BY id).
   *  ⚠️ НЕ пересортировывать по `at`: переходы одной секунды иначе могут поменяться
   *  местами и исказить «статус на конец дня». */
  events: TaskHistoryEvent[];
}

/**
 * Статус при заведении карточки — from_status ПЕРВОГО (по порядку ввода) перехода,
 * если такой переход есть и у него записан from_status; иначе — текущий статус
 * карточки (единственное, что тогда известно).
 */
export function buildTimelines(history: TaskHistory): CardTimeline[] {
  const byTask = new Map<number, TaskHistoryEvent[]>();
  for (const e of history.events) {
    const list = byTask.get(e.taskId);
    if (list) list.push(e);
    else byTask.set(e.taskId, [e]);
  }
  return history.cards.map((card) => {
    const events = byTask.get(card.id) ?? [];
    const first = events[0];
    const initialStatus = first?.fromStatus ? first.fromStatus : card.status;
    return { card, createdDay: dayOf(card.createdAt), initialStatus, events };
  });
}

/**
 * Статус карточки НА КОНЕЦ дня `day` (включительно, 'at' ≤ конец дня).
 * null — карточка к этому дню ЕЩЁ НЕ СУЩЕСТВУЕТ (заведена позже): она обязана
 * пропасть из графика этого дня, а не посчитаться со своим текущим статусом
 * задним числом — иначе «открыто на конец дня» месяц назад включало бы карточки,
 * которых тогда не было.
 * Карточка без даты заведения (created_at пуст) считается существующей всегда:
 * раз мы не знаем, когда её завели, молча выкидывать её из графика — соврать
 * числом, которое выглядит точным.
 */
export function statusAtEndOfDay(t: CardTimeline, day: string): string | null {
  if (t.createdDay !== null && t.createdDay > day) return null;
  let status = t.initialStatus;
  for (const e of t.events) {
    const d = dayOf(e.at);
    if (d === null || d > day) break;
    if (e.toStatus) status = e.toStatus;
  }
  return status;
}

export function distinctStatuses(history: TaskHistory): string[] {
  const s = new Set<string>();
  for (const c of history.cards) if (c.status) s.add(c.status);
  for (const e of history.events) {
    if (e.fromStatus) s.add(e.fromStatus);
    if (e.toStatus) s.add(e.toStatus);
  }
  return orderStatusKeys(s);
}

export function distinctRoles(cards: readonly TaskHistoryCard[]): string[] {
  const s = new Set<string>();
  for (const c of cards) s.add(c.role ?? '—');
  return [...s].sort();
}

// ── вид а) «Поток» ───────────────────────────────────────────────────────────

export interface FlowPoint { day: string; created: number; closed: number; openEnd: number }

export interface FlowResult {
  points: FlowPoint[];
  /** «открыто было» — статус на конец дня ПЕРЕД началом периода. */
  openBefore: number;
  newTotal: number;
  closedTotal: number;
}

export function computeFlow(
  timelines: readonly CardTimeline[],
  days: readonly string[],
  closedSet: ReadonlySet<string>,
  roles: ReadonlySet<string> | null,
): FlowResult {
  const inRole = (t: CardTimeline) => roles === null || roles.has(t.card.role ?? '—');
  const dayIndex = new Map(days.map((d, i) => [d, i] as const));
  const points: FlowPoint[] = days.map((day) => ({ day, created: 0, closed: 0, openEnd: 0 }));

  for (const t of timelines) {
    if (!inRole(t) || t.createdDay === null) continue;
    const idx = dayIndex.get(t.createdDay);
    if (idx !== undefined) points[idx].created += 1;
  }

  for (const t of timelines) {
    if (!inRole(t)) continue;
    for (const e of t.events) {
      if (!e.toStatus || !closedSet.has(e.toStatus)) continue;
      const d = dayOf(e.at);
      if (d === null) continue;
      const idx = dayIndex.get(d);
      if (idx !== undefined) points[idx].closed += 1;
    }
  }

  for (let i = 0; i < days.length; i++) {
    let openEnd = 0;
    for (const t of timelines) {
      if (!inRole(t)) continue;
      const st = statusAtEndOfDay(t, days[i]);
      if (st !== null && !closedSet.has(st)) openEnd += 1;
    }
    points[i].openEnd = openEnd;
  }

  let openBefore = 0;
  if (days.length > 0) {
    const dayBefore = addDaysUtc(days[0], -1);
    for (const t of timelines) {
      if (!inRole(t)) continue;
      const st = statusAtEndOfDay(t, dayBefore);
      if (st !== null && !closedSet.has(st)) openBefore += 1;
    }
  }

  return {
    points,
    openBefore,
    newTotal: points.reduce((a, p) => a + p.created, 0),
    closedTotal: points.reduce((a, p) => a + p.closed, 0),
  };
}

// ── вид б) «По статусам» ─────────────────────────────────────────────────────

/** статус → числа по дням (в порядке days). Map, а не объект: ключи — статусы из
 *  базы, и мало ли какой окажется зарезервированным именем поля объекта. */
export function computeByStatus(
  timelines: readonly CardTimeline[],
  days: readonly string[],
  displayStatuses: readonly string[],
  roles: ReadonlySet<string> | null,
): Map<string, number[]> {
  const inRole = (t: CardTimeline) => roles === null || roles.has(t.card.role ?? '—');
  const result = new Map<string, number[]>();
  for (const s of displayStatuses) result.set(s, days.map(() => 0));

  for (let i = 0; i < days.length; i++) {
    for (const t of timelines) {
      if (!inRole(t)) continue;
      const st = statusAtEndOfDay(t, days[i]);
      if (st === null) continue;
      const arr = result.get(st);
      if (arr) arr[i] += 1;
    }
  }
  return result;
}

// ── вид в) «По ролям» ─────────────────────────────────────────────────────────

export interface RoleRow { role: string; created: number; closed: number; openNow: number }

export function computeByRole(
  timelines: readonly CardTimeline[],
  days: readonly string[],
  closedSet: ReadonlySet<string>,
  roles: ReadonlySet<string> | null,
): RoleRow[] {
  if (days.length === 0) return [];
  const start = days[0];
  const today = days[days.length - 1];
  const inRole = (t: CardTimeline) => roles === null || roles.has(t.card.role ?? '—');

  const roleSet = new Set<string>();
  for (const t of timelines) if (inRole(t)) roleSet.add(t.card.role ?? '—');

  const rows: RoleRow[] = [];
  for (const role of [...roleSet].sort()) {
    let created = 0;
    let closed = 0;
    let openNow = 0;
    for (const t of timelines) {
      if ((t.card.role ?? '—') !== role) continue;
      if (t.createdDay !== null && t.createdDay >= start && t.createdDay <= today) created += 1;
      const st = statusAtEndOfDay(t, today);
      if (st !== null && !closedSet.has(st)) openNow += 1;
      for (const e of t.events) {
        if (!e.toStatus || !closedSet.has(e.toStatus)) continue;
        const d = dayOf(e.at);
        if (d !== null && d >= start && d <= today) closed += 1;
      }
    }
    rows.push({ role, created, closed, openNow });
  }

  const total = rows.reduce(
    (acc, r) => ({
      role: 'всего',
      created: acc.created + r.created,
      closed: acc.closed + r.closed,
      openNow: acc.openNow + r.openNow,
    }),
    { role: 'всего', created: 0, closed: 0, openNow: 0 },
  );
  return [...rows, total];
}
