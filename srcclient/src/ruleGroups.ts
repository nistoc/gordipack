import type { Rule } from './types';

/**
 * ГРУППИРОВКА ПРАВИЛ ПО СМЫСЛУ — и человеческое описание каждой группы.
 *
 * 🎯 Зачем. Правил полсотни, и плоским списком они не читаются: слово владельца
 *    2026-08-09 — «так их тяжело воспринимать». Список одного уровня заставляет
 *    держать в голове весь свод сразу, чтобы понять, о чём вообще каждая строка.
 *
 * 📌 ПОЧЕМУ ТЕМА ЗАДАНА СПИСКОМ КЛЮЧЕЙ, А НЕ УГАДЫВАЕТСЯ ПО СЛОВАМ В ТЕКСТЕ.
 *    Подбор по словам выглядит умнее и живёт хуже: он МОЛЧА меняет раскладку при
 *    любой правке текста правила, и проверить его нечем — «почему оно тут» не имеет
 *    ответа. Явный список проверяется глазами за минуту, а новое правило честно
 *    попадает в «тему не назначили» и там ВИДНО, что его не разобрали. Тихая
 *    ошибочная раскладка хуже громкого «не знаю».
 *
 * ⛔ ТЕМА — НЕ УТВЕРЖДЕНИЕ О СИЛЕ ПРАВИЛА. Действует правило или отозвано —
 *    отдельный вопрос, и отвечает на него поле `revoked`, которое считает сервис.
 *    Отозванные вынимаются из тем целиком и живут своей группой: перепутать
 *    отменённое с действующим — самая дорогая ошибка на этой странице.
 */
export interface RuleTheme {
  id: string;
  title: string;
  /** Описание для человека, который НЕ держит систему в голове. Без ключей и жаргона. */
  blurb: string;
  keys: readonly string[];
}

export const RULE_THEMES: readonly RuleTheme[] = [
  {
    id: 'code',
    title: 'Код и правки в нём',
    blurb:
      'Что обязательно сделать до и после изменения кода: прогнать проверки, показать, ' +
      'что меняется в договорённостях между частями системы, и кто вправе запускать службы. ' +
      'Цена нарушения — сломанная сборка и потерянный чужой труд.',
    keys: [
      'gate-before-commit',
      'contract-diff-before-commit',
      'acceptance-e2e',
      'migrations-core-only',
      'migrations-under-watch',
      'core-service-start-and-migrations',
      'services-self-raise',
      'rule8-destructive',
    ],
  },
  {
    id: 'data',
    title: 'Данные, устройство базы и записи о них',
    blurb:
      'Как менять устройство хранилища и как в него писать, чтобы задним числом было видно, ' +
      'кто, когда и на каком основании это сделал. Сюда же — правило о времени: ' +
      'все метки пишутся в одном часовом поясе, иначе сверки «когда что произошло» расходятся.',
    keys: [
      'migration-safety',
      'data-migration-provenance',
      'schema-step-records-itself',
      'append-only-messages',
      'md-to-sqlite-phased-cutover',
      'timestamp-utc-in-sqlite',
      'milestone-single-source',
      'revision-bump-same-stroke',
      'semantic-canon',
      'file-map',
    ],
  },
  {
    id: 'feed',
    title: 'Переписка и совместная работа',
    blurb:
      'Как участники говорят друг с другом: в каком виде писать сообщения, насколько срочно ' +
      'отвечать, что читать целиком, а что можно пропустить, и когда поднимать вопрос выше. ' +
      'От этих правил зависит, дойдёт ли сказанное до того, кому оно нужно.',
    keys: [
      'note-format',
      'note-priority-norm',
      'ack-deadline',
      'poll-format',
      'one-writer-one-channel',
      'shared-broadcast-channel',
      'full-scan-every-tick',
      'escalation-and-ground-truth',
      'coord-commits-coordination',
      'sync-sleep-backoff',
    ],
  },
  {
    id: 'memory',
    title: 'Память участника и возвращение к работе',
    blurb:
      'Что участник обязан сохранить о себе перед остановкой, чтобы, начав заново, не потерять ' +
      'нить и не переделывать уже сделанное. Сюда же — кто за какую часть работы отвечает.',
    keys: [
      'phoenix-save-on-stop',
      'rhythm-survives-rebirth',
      'dowry-facts-carry-source',
      'role-keeps-own-error-list',
      'role-migration-standard',
      'role-roster-and-zones',
    ],
  },
  {
    id: 'owner',
    title: 'Разговор с владельцем',
    blurb:
      'Как спрашивать и что показывать: задавать вопросы заранее и по существу, перепроверять ' +
      'цифры перед тем, как на них ссылаться, не молчать в простое, и держать задачи в общем ' +
      'списке, а не в переписке, где они теряются.',
    keys: [
      'questions-via-interface',
      'proactive-next-steps',
      'remeasure-before-ask',
      'task-discipline',
    ],
  },
  {
    id: 'borders',
    title: 'Границы: куда заходить нельзя',
    blurb:
      'Места, которые нельзя трогать вовсе — чужие рабочие каталоги и соседние проекты. ' +
      'Правил здесь мало, зато цена нарушения самая высокая: испорченной окажется чужая работа.',
    keys: ['no-scan-external-contours', 'gordi-aia-clone-forbidden'],
  },
];

/** Куда попадают правила, которым тему ещё не назначили. Пустой — не показывается. */
export const UNSORTED_THEME: RuleTheme = {
  id: 'unsorted',
  title: 'Тема не назначена',
  blurb:
    'Правила, которые в просмотрщике ещё не разложены по темам — как правило, недавно ' +
    'добавленные. Важность у них ровно такая же, как у остальных: читать наравне.',
  keys: [],
};

export const REVOKED_GROUP = {
  id: 'revoked',
  title: 'Отозванные — БОЛЬШЕ НЕ ДЕЙСТВУЮТ',
  blurb:
    'Правила, которые уже отменены. Их не стирают нарочно: видно, что было и почему отменили — ' +
    'иначе отменённое возвращается и его снова исполняют как приказ. Читать как историю, ' +
    'а не как указание.',
} as const;

/** Обратный указатель ключ → тема. Строится один раз, а не перебором на каждое правило. */
const THEME_BY_KEY = new Map<string, RuleTheme>();
for (const theme of RULE_THEMES) {
  for (const key of theme.keys) THEME_BY_KEY.set(key, theme);
}

export interface RuleGroup {
  id: string;
  title: string;
  blurb: string;
  rules: Rule[];
  /** Отозванные. Отдельный признак, а не сравнение id со строкой в разметке. */
  revoked: boolean;
}

/**
 * Разложить правила по группам.
 *
 * Порядок внутри группы: сперва закреплённые владельцем, затем по ключу. Слово владельца
 * весит больше слова координатора, и в списке это должно быть видно расположением,
 * а не только подписью — подпись читают не всегда, порядок замечают всегда.
 *
 * Отозванные идут ПОСЛЕДНЕЙ группой и по умолчанию свёрнуты: их счётчик виден
 * (значит, они не спрятаны), но глаз при чтении свода на них не спотыкается.
 */
export function groupRules(rules: readonly Rule[]): RuleGroup[] {
  const byTheme = new Map<string, Rule[]>();
  const revoked: Rule[] = [];

  for (const rule of rules) {
    if (rule.revoked) {
      revoked.push(rule);
      continue;
    }
    const theme = THEME_BY_KEY.get(rule.ruleKey) ?? UNSORTED_THEME;
    const bucket = byTheme.get(theme.id);
    if (bucket) bucket.push(rule);
    else byTheme.set(theme.id, [rule]);
  }

  const sort = (list: Rule[]) =>
    list.sort((a, b) => {
      const weight = (r: Rule) => (r.lockedBy === 'owner' ? 0 : 1);
      return weight(a) - weight(b) || a.ruleKey.localeCompare(b.ruleKey, 'ru');
    });

  const groups: RuleGroup[] = [];
  for (const theme of [...RULE_THEMES, UNSORTED_THEME]) {
    const list = byTheme.get(theme.id);
    // Пустая группа не показывается вовсе: заголовок с нулём — это шум, за которым
    // теряются группы с содержимым.
    if (!list || list.length === 0) continue;
    groups.push({ id: theme.id, title: theme.title, blurb: theme.blurb, rules: sort(list), revoked: false });
  }

  if (revoked.length > 0) {
    groups.push({ ...REVOKED_GROUP, rules: sort(revoked), revoked: true });
  }

  return groups;
}

/** Кто закрепил правило — словами, а не служебным обозначением. */
export function lockedByLabel(lockedBy: string | null): string | null {
  if (!lockedBy) return null;
  if (lockedBy === 'owner') return 'решение владельца';
  if (lockedBy === 'coord') return 'решение координатора';
  return `закрепил: ${lockedBy}`;
}

/**
 * Поле «кто разрешил» — свободный текст из базы, но два значения там служебные
 * (`owner`, `coord`). Переводим ТОЛЬКО их, остальное отдаём как записано: подменять
 * произвольный текст своими словами значило бы показывать не то, что в базе.
 */
export function authorizedLabel(authorized: string): string {
  if (authorized === 'owner') return 'владелец';
  if (authorized === 'coord') return 'координатор';
  return authorized;
}

/**
 * Когда правило перестанет действовать — словами.
 * «Условие не указано» — честнее пустого места: пустота читается как «бессрочно»,
 * а это разные вещи, и одна из них никем не решена.
 */
export function expiryLabel(kind: string | null, cond: string | null): string {
  const base =
    kind === 'forever' ? 'бессрочно'
      : kind === 'until_date' ? 'до даты'
        : kind === 'until_event' ? 'до события'
          : kind === 'while_measured' ? 'пока подтверждается замером'
            : 'условие отмены не указано';
  return cond ? `${base}: ${cond}` : base;
}
