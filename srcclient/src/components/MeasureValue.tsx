import type { Measure } from '../types';

/**
 * Показ замера, который может быть НЕПОДДЕРЖИВАЕМЫМ.
 *
 * 🔴 Ради этого компонента и заведён тип Measure: нарисовать «0» там, где
 *    посчитать было нечем, — самая дорогая ошибка просмотрщика. Ноль читается
 *    как хорошая новость («задач без критерия нет»), а на деле означает
 *    «в этой базе поля критерия не существует». Поэтому здесь вместо числа
 *    появляется прочерк и пояснение.
 */
export function MeasureValue({ measure, suffix }: { measure: Measure; suffix?: string }) {
  if (!measure.supported) {
    return (
      <span className="measure measure--unsupported" title={measure.note ?? 'не поддерживается этой базой'}>
        н/д
      </span>
    );
  }
  return (
    <span className="measure">
      {measure.value ?? 0}
      {suffix ? <span className="measure__suffix"> {suffix}</span> : null}
    </span>
  );
}

export function StatCard({
  label, measure, tone, hint,
}: {
  label: string;
  measure: Measure;
  tone?: 'normal' | 'warn' | 'good';
  hint?: string;
}) {
  const toneClass = !measure.supported
    ? 'stat--unsupported'
    : tone === 'warn' && (measure.value ?? 0) > 0
      ? 'stat--warn'
      : tone === 'good'
        ? 'stat--good'
        : '';

  return (
    <div className={`stat ${toneClass}`} title={measure.note ?? hint ?? ''}>
      <div className="stat__value"><MeasureValue measure={measure} /></div>
      <div className="stat__label">{label}</div>
      {!measure.supported && measure.note ? <div className="stat__note">{measure.note}</div> : null}
    </div>
  );
}
