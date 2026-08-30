import type {
  Health, Message, MessagePage, Overview, Role, RolesResponse, Rule,
  SchemaReport, SourceInfo, Task, TaskDetail, TasksGrouped, TracksResponse,
} from './types';

/**
 * Все запросы идут на относительный /api — в дев-режиме его проксирует Vite
 * на локальный бэкенд (см. vite.config.ts). Абсолютных адресов в коде нет
 * намеренно: иначе собранный фронтенд помнил бы чужой порт.
 */
const BASE = '/api';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== '' && v !== 'all') url.searchParams.set(k, String(v));
  }

  const response = await fetch(url.toString(), { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    // 503 от бэкенда означает «снимка ещё нет / источник не задан» — это не сбой сети,
    // и показывать его надо словами, а не пустым списком.
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
      else if (body?.error) detail = String(body.error);
    } catch {
      /* тело не JSON — оставляем код статуса */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const parsed = await response.json();
      if (parsed?.error) detail = String(parsed.error);
      else if (parsed?.detail) detail = String(parsed.detail);
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => get<Health>('/health'),
  sources: () => get<SourceInfo[]>('/sources'),
  selectSource: (path: string) => post<{ active: string }>('/sources/select', { path }),
  refresh: () => post<{ refreshedAtUtc: string | null; error: string | null }>('/refresh', {}),

  overview: () => get<Overview>('/overview'),
  schema: () => get<SchemaReport>('/schema'),
  roles: () => get<RolesResponse>('/roles'),
  rules: () => get<Rule[]>('/rules'),
  writers: () => get<string[]>('/writers'),

  /**
   * `track` — отбор по набору, его делает СЛУЖБА, а не клиент:
   *   имя набора · 'none' — задачи без набора · 'all'/пусто — не отбирать.
   * ⚠️ 'none' и 'all' служебные. Если такое имя окажется настоящим набором, служба
   * отвечает отказом СО СЛОВОМ (400) и называет обходной путь — молчаливого «не того
   * ответа» здесь нет; текст отказа показывается человеку как есть.
   */
  tasks: (p: { status?: string; role?: string; track?: string; missingCriterion?: boolean }) =>
    get<Task[]>('/tasks', p),
  task: (id: number) => get<TaskDetail>(`/tasks/${id}`),

  /** Наборы с числом задач в каждом + отдельным числом — задачи БЕЗ набора. */
  tracks: () => get<TracksResponse>('/tracks'),

  /**
   * Задачи, сгруппированные по наборам. Группировку делает служба: клиент её
   * НЕ повторяет своей рукой — иначе два порядка однажды разойдутся, и экран
   * будет показывать не то, что отдаёт база.
   */
  tasksGrouped: (p: { status?: string; role?: string } = {}) =>
    get<TasksGrouped>('/tasks/grouped', p),

  messages: (p: {
    limit?: number; offset?: number; role?: string;
    priority?: string; search?: string; source?: string;
  }) => get<MessagePage>('/messages', p),
  message: (id: number) => get<Message>(`/messages/${id}`),
};

export type { Role, Rule, Task, Message };
export type { TaskGroup, TasksGrouped, TrackInfo, TracksResponse } from './types';
