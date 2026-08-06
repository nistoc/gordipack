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
  createdBy: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  bodyLength: number;
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
}

export interface SchemaObject {
  name: string;
  type: string;
  columns: string[];
}

export interface SchemaReport {
  present: SchemaObject[];
  expectedButMissing: string[];
  presentButUnknownToViewer: string[];
  note: string;
}
