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
 * То же время БЕЗ суффикса — только для колонок таблицы, чья ШАПКА уже несёт
 * «, UTC». Правило пояса не ослаблено: суффикс сказан один раз на колонку,
 * а не сорок один раз в столбик. Вне такой колонки эту функцию звать нельзя —
 * получится ровно та метка без пояса, от которой предостерегает шапка файла.
 */
export function fmtUtcBare(value: string | null | undefined): string {
  const full = fmtUtc(value);
  return full.endsWith(' UTC') ? full.slice(0, -4) : full;
}

/** «сколько назад» — грубо, для ощущения свежести, а не для отчёта. */
export function ago(value: string | null | undefined, nowIso?: string | null): string {
  if (!value) return '';
  const then = new Date(value).getTime();
  const now = nowIso ? new Date(nowIso).getTime() : Date.now();
  if (Number.isNaN(then) || Number.isNaN(now)) return '';
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
