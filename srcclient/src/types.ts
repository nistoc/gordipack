// Формы ответов бэкенда (../src). Держатся руками — генератора клиента здесь нет.
// Если правишь контракт в C#, правь и здесь: расхождение молча не всплывёт.

export interface SourceInfo {
  path: string;
  name: string;
  sizeBytes: number;
  modifiedUtc: string;
  isActive: boolean;
}

export interface Health {
  status: 'ok' | 'no-source' | 'error';
  activeDbPath: string | null;
  scanRoot: string | null;
  readOnly: boolean;
  refreshSeconds: number;
  lastRefreshUtc: string | null;
  lastChangeDetectedUtc: string | null;
  lastError: string | null;
  nowUtc: string;
}

/**
 * Замер, который умеет сказать «этой базой не поддерживается».
 * Ноль и «нечем посчитать» — разные новости, и интерфейс обязан их различать.
 */
export interface Measure {
  value: number | null;
  supported: boolean;
  note: string | null;
}

export interface SchemaVersion {
  declared: string | null;
  milestone: string | null;
  stepsTotal: number | null;
  stepsAfterMilestone: number | null;
  note: string | null;
}

export interface Overview {
  groupName: string | null;
  schemaVersion: SchemaVersion;
  messages: Measure;
  messagesHistory: Measure;
  roles: Measure;
  rules: Measure;
  tasksTotal: Measure;
  tasksOpen: Measure;
  tasksDone: Measure;
  tasksOpenWithoutCriterion: Measure;
  lastMessageUtc: string | null;
  builtAtUtc: string;
}

export interface Task {
  id: number;
  role: string | null;
  title: string | null;
  status: string | null;
  priority: string | null;
  doneWhen: string | null;
  criterionSupported: boolean;
  hasCriterion: boolean;
  tags: string[];
  parentId: number | null;
  parentTrack: string | null;
  blockedReason: string | null;
  /** Причина устаревания (последний переход в dropped с запиской); null у dropped = «НЕ ЗАПИСАНА». */
  droppedReason: string | null;
  createdBy: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  bodyLength: number;
}

/**
 * Набор задач (в базе — таблица `tracks`, у задачи — поле `parent_track`).
 * `declared: false` — набор, который задачи НАЗЫВАЮТ, а записи о нём нет вовсе:
 * заголовка и статуса у такого не будет, но задачи его видны. Показать только
 * заявленные значило бы потерять задачи молча.
 */
export interface TrackInfo {
  trackId: string;
  title: string | null;
  status: string | null;   // active | paused | done — как в базе; null у незаявленного
  declared: boolean;
  taskCount: number;
}

/** Витрина наборов. `untracked` — задачи БЕЗ набора: это не набор, потому отдельным числом. */
export interface TracksResponse {
  items: TrackInfo[];
  untracked: number;
  tasksTotal: number;
  note: string | null;
}

/**
 * Группа задач одного набора. `trackId === null` — группа «без набора»: она приходит
 * ВСЕГДА, пока такие задачи есть, и стои́т последней. Её отсутствие читалось бы
 * как «таких задач нет».
 */
export interface TaskGroup {
  trackId: string | null;
  title: string | null;
  status: string | null;
  declared: boolean;
  count: number;
  items: Task[];
}

/**
 * Задачи, сгруппированные по наборам.
 * ⚠️ `totalTasks` обязан равняться сумме `count` по группам — это и есть проверка
 * «ничего не потеряно группировкой». Расхождение служба называет в `note`, а экран
 * обязан его НАПЕЧАТАТЬ, а не проглотить: молчащая пропажа неотличима от «столько и было».
 */
export interface TasksGrouped {
  groups: TaskGroup[];
  totalTasks: number;
  ungrouped: number;          // задач без набора
  undeclaredTracks: number;   // наборов, которых нет в таблице tracks
  note: string | null;
}

export interface TaskEvent {
  id: number;
  at: string | null;
  actorRole: string | null;
  eventType: string | null;
  fromStatus: string | null;
  toStatus: string | null;
  bodyMd: string | null;
}

export interface TaskTest {
  id: number;
  title: string | null;
  method: string | null;
  status: string | null;
  command: string | null;
  expected: string | null;
  lastRunAt: string | null;
  lastResultMd: string | null;
}

export interface TaskDetail {
  task: Task;
  bodyMd: string | null;
  events: TaskEvent[];
  tests: TaskTest[];
  linkedMessages: Message[];
  missingFeatures: string[];
}

export interface Message {
  id: number;
  writerRole: string | null;
  timestamp: string | null;
  priority: string | null;
  tags: string[];
  broadcast: boolean | null;
  source: string | null;
  bodyLength: number;
  bodyPreview: string;
  bodyMd: string | null;
}

export interface MessagePage {
  items: Message[];
  limit: number;
  offset: number;
  total: number;
  sourceObject: string;
}

export interface Role {
  role: string;
  status: string | null;
  statusNote: string | null;
  statusUpdatedAt: string | null;
  inRoster: boolean | null;
  cursorAt: number | null;
  messagesWritten: number | null;
  lastMessageAt: string | null;
  phoenixSections: number;
  phoenixSavedAt: string | null;
}

export interface RolesResponse {
  items: Role[];
  missingFeatures: string[];
}

export interface Rule {
  ruleKey: string;
  status: string | null;
  statusNote: string | null;
  version: number | null;
  lockedBy: string | null;
  updatedAt: string | null;
  bodyLength: number;
  bodyPreview: string;
  body: string | null;
  expiryKind: string | null;      // forever | until_date | until_event | while_measured
  expiryCond: string | null;
  basis: string | null;
  authorized: string | null;
  sourceRef: string | null;
  /** Правило отменено и больше НЕ действует. Считает сервис — см. RuleDto. */
  revoked: boolean;
  /** Чем установлено «отозвано»: поле статуса или шапка текста. */
  revokedBasis: string | null;
}

export interface SchemaObject {
  name: string;
  type: string;
  columns: string[];
}

/**
 * ⚠️ ИМЕНА ПОЛЕЙ ЗДЕСЬ — ДОСЛОВНО ТЕ, ЧТО В `SchemaReportDto` (../src/Model/Contracts.cs).
 *
 * 🔴 Замер 2026-08-08 23:26 UTC: тут стояло `presentButUnknownToViewer`, а сервис
 *    отдаёт `presentButUnknownToPeriscope`. Опечатка не даёт ни ошибки сборки, ни
 *    предупреждения — TypeScript верит объявлению, а не ответу по сети, — и на живой
 *    странице `undefined.length` роняет отрисовку, гася ВЕСЬ экран целиком.
 *    Расхождение имени на одно слово стоило страницы «Схема» в полном молчании.
 */
export interface SchemaReport {
  present: SchemaObject[];
  expectedButMissing: string[];
  presentButUnknownToPeriscope: string[];
  note: string;
}
