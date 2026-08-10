/**
 * Время везде показываем в UTC с ЯВНЫМ суффиксом — это правило контура,
 * а не украшение: метка без пояса неотличима от местного времени, и именно
 * на этом различии сгорают сверки «когда что произошло».
 *
 * На вход приходят две формы:
 *   · из базы   — 'YYYY-MM-DD HH:MM:SS' (уже UTC, без суффикса);
 *   · от сервиса — ISO с поясом ('2026-08-06T16:17:19+00:00').
 * Обе приводим к одному виду. Что не разобрали — показываем как есть,
 * а не подставляем «сейчас»: неизвестное время лучше неверного.
 */
export function fmtUtc(value: string | null | undefined, withSeconds = false): string {
  if (!value) return '—';

  const bare = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(value);
  if (bare && !/[+-]\d{2}:?\d{2}$|Z$/.test(value)) {
    const [, y, m, d, hh, mm, ss] = bare;
    return `${y}-${m}-${d} ${hh}:${mm}${withSeconds && ss ? ':' + ss : ''} UTC`;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const iso = parsed.toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, withSeconds ? 19 : 16)} UTC`;
}

/**
 * Метка времени → миллисекунды, ЯВНО считая её UTC, когда пояс не указан.
 *
 * 🔴 ЗАЧЕМ ОТДЕЛЬНАЯ ФУНКЦИЯ, А НЕ `new Date(value)`. База отдаёт время в виде
 * '2026-08-07 13:04:41' — без пояса и через пробел. Такую строку движок браузера
 * разбирает как МЕСТНОЕ время, то есть в поясе +02:00 карточка, заведённая минуту
 * назад, получает возраст «2 часа 1 минута». Возраст — одно из полей, ради которых
 * писана доска, и ошибка ровно на смещение пояса была бы не видна глазом: числа
 * правдоподобные, просто неверные. Поэтому пояс здесь навязывается, а не угадывается.
 */
export function parseUtcMs(value: string | null | undefined): number | null {
  if (!value) return null;
  const hasZone = /[+-]\d{2}:?\d{2}$|Z$/i.test(value);
  const normalized = hasZone ? value : value.replace(' ', 'T') + 'Z';
  const ms = new Date(normalized).getTime();
  return Number.isNaN(ms) ? null : ms;
}

/**
 * Возраст карточки в сутках (дробных) от момента заведения. null — если времени нет
 * или оно не разобрано; ноль здесь был бы ложью («карточка заведена только что»).
 */
export function ageDays(createdAt: string | null | undefined, nowMs = Date.now()): number | null {
  const then = parseUtcMs(createdAt);
  if (then === null) return null;
  return Math.max(0, (nowMs - then) / 86_400_000);
}

/** Возраст короткой подписью для плитки: «26 сут», «5 ч», «12 мин». */
export function ageShort(createdAt: string | null | undefined, nowMs = Date.now()): string {
  const days = ageDays(createdAt, nowMs);
  if (days === null) return '—';
  if (days >= 1) return `${Math.floor(days)} сут`;
  const hours = days * 24;
  if (hours >= 1) return `${Math.floor(hours)} ч`;
  return `${Math.max(1, Math.floor(hours * 60))} мин`;
}

/** «сколько назад» — грубо, для ощущения свежести, а не для отчёта. */
export function ago(value: string | null | undefined, nowIso?: string | null): string {
  if (!value) return '';
  const then = parseUtcMs(value);
  const now = nowIso ? parseUtcMs(nowIso) : Date.now();
  if (then === null || now === null) return '';
  const sec = Math.max(0, Math.round((now - then) / 1000));
  if (sec < 60) return `${sec} с назад`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} мин назад`;
  const hours = Math.round(min / 60);
  if (hours < 48) return `${hours} ч назад`;
  return `${Math.round(hours / 24)} сут назад`;
}

export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}
