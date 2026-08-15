import type { Task } from '../types';
import { ageDays, ageShort, fmtUtc } from '../format';
import { isCriterionGap, priorityMeta, statusMeta } from '../taskModel';

/** Важность — четыре засечки, закрашено столько, какова ступень. См. taskModel. */
export function PriorityMark({ priority }: { priority: string | null }) {
  const meta = priorityMeta(priority);
  return (
    <span
      className={`prio prio--${meta.key}`}
      title={`важность: ${meta.title}`}
      aria-label={`важность: ${meta.title}`}
      data-control={`priority-${meta.key}`}
    >
      {[0, 1, 2, 3].map((i) => (
        <i key={i} className={`prio__pip ${i < meta.pips ? 'prio__pip--on' : ''}`} />
      ))}
    </span>
  );
}

/** Статус — своя форма и свой цвет, слово живёт в подсказке и в aria. */
export function StatusMark({ status }: { status: string | null }) {
  const meta = statusMeta(status);
  return (
    <span
      className={`smark smark--${meta.key}`}
      title={`статус: ${meta.title}`}
      aria-label={`статус: ${meta.title}`}
      data-control={`status-mark-${meta.key}`}
    >
      {meta.glyph}
    </span>
  );
}

/**
 * ПЛИТКА ЗАДАЧИ — единица доски.
 *
 * Что на ней видно БЕЗ наведения мыши и без открытия карточки:
 *   · номер, статус (форма+цвет), важность (длина полоски), возраст от заведения;
 *   · ЕСТЬ ЛИ КРИТЕРИЙ ПРИЁМКИ — и это самый громкий элемент плитки, потому что
 *     по правилу контура без критерия задачу нельзя ни завести, ни закрыть;
 *   · связь с родительской карточкой, если она есть;
 *   · причина блокировки, если она есть.
 *
 * 🔴 ПОЧЕМУ «НЕТ КРИТЕРИЯ» КРИЧИТ, А «ЕСТЬ» ШЕПЧЕТ. Экран заводится ради поиска дыр.
 *    Если оба состояния оформить одинаково заметно, глазу придётся ЧИТАТЬ каждую плитку,
 *    чтобы понять, какая из них дыра, — а это ровно та работа, которую доска обязана снять.
 *    Поэтому отсутствие критерия — полоса на всю высоту плитки плюс подпись словами,
 *    а наличие — тихая строка с началом текста.
 *
 * ⚠️ ПУСТЫЕ ПОЛЯ НЕ РИСУЮТСЯ ВОВСЕ, а не рисуются пустыми. `blocked_reason` сейчас пуст
 *    во всех ста с лишним карточках: строка-заглушка под него дала бы сто пустых полосок
 *    и подтолкнула бы верстать «на глаз по сегодняшним данным». Появится причина —
 *    появится и строка.
 */
export function TaskTile({
  task,
  selected,
  childCount,
  onOpen,
  onOpenParent,
  nowMs,
}: {
  task: Task;
  selected: boolean;
  /** Сколько карточек объявили эту своим родителем. 0 — блок иерархии не рисуется. */
  childCount: number;
  onOpen: () => void;
  onOpenParent: (parentId: number) => void;
  nowMs: number;
}) {
  const gap = isCriterionGap(task);
  const days = ageDays(task.createdAt, nowMs);

  /**
   * ПОРОГ «ЗАЛЕЖАЛАСЬ» — НЕДЕЛЯ, И ВЫДЕЛЕНА ОНА НАСЫЩЕННОСТЬЮ, А НЕ ЦВЕТОМ.
   *
   * Замер живой базы 2026-08-07 13:23 UTC: открытых 59, из них старше СУТОК — 29,
   * старше НЕДЕЛИ — 19. Порог в сутки красил бы половину доски, а выделение, которое
   * стоит у половины, не выделяет ничего.
   *
   * Цвет для возраста не берётся сознательно: оранжевый на этом экране уже занят —
   * им кричит отсутствие критерия приёмки. Второй смысл того же цвета обесценил бы
   * первый, а первый здесь главный.
   */
  const stale = days !== null && days >= 7 && task.status === 'open';
  const blocked = (task.blockedReason ?? '').trim();

  return (
    <article
      className={`tile ${gap ? 'tile--gap' : ''} ${selected ? 'tile--selected' : ''}`}
      data-item={`task-${task.id}`}
      data-task-id={task.id}
      data-task-status={task.status ?? ''}
      data-task-priority={task.priority ?? ''}
      data-criterion={gap ? 'missing' : task.criterionSupported ? 'present' : 'unsupported'}
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen();
        }
      }}
    >
      <div className="tile__meta" data-group={`tile-meta-${task.id}`}>
        <span className="tile__id mono">#{task.id}</span>
        <StatusMark status={task.status} />
        <PriorityMark priority={task.priority} />
        <span
          className={`tile__age ${stale ? 'tile__age--stale' : ''}`}
          title={
            `возраст карточки${stale ? ' — больше недели' : ''}\n`
            + `заведена ${fmtUtc(task.createdAt, true)}`
            + (task.createdBy ? ` · роль ${task.createdBy}` : '')
            + `\nизменена ${fmtUtc(task.updatedAt, true)}`
          }
          data-control={`age-${task.id}`}
        >
          {ageShort(task.createdAt, nowMs)}
        </span>
      </div>

      <div className="tile__title" title={task.title ?? ''}>{task.title}</div>

      <div className="tile__criterion" data-group={`tile-criterion-${task.id}`}>
        {!task.criterionSupported ? (
          <span className="muted small">поля критерия нет в базе</span>
        ) : gap ? (
          <span className="badge badge--gap">⚠ критерий приёмки не задан</span>
        ) : (
          <span className="tile__criterion-text" title={task.doneWhen ?? ''}>
            ✓ {task.doneWhen}
          </span>
        )}
      </div>

      {(task.parentId !== null || childCount > 0 || task.parentTrack) && (
        <div className="tile__rel" data-group={`tile-relations-${task.id}`}>
          {task.parentId !== null && (
            <button
              className="reltag reltag--parent"
              data-control={`open-parent-${task.id}`}
              title={`родительская карточка #${task.parentId} — щёлкнуть, чтобы открыть`}
              onClick={(e) => {
                e.stopPropagation();
                onOpenParent(task.parentId as number);
              }}
            >
              ↳ в составе #{task.parentId}
            </button>
          )}
          {childCount > 0 && (
            <span className="reltag reltag--children" title="карточек, объявивших эту родительской">
              ⤷ подзадач: {childCount}
            </span>
          )}
          {task.parentTrack && (
            <span className="reltag reltag--track" title="дорожка (parent_track)">
              {task.parentTrack}
            </span>
          )}
        </div>
      )}

      {blocked && (
        <div className="tile__blocked" data-group={`tile-blocked-${task.id}`} title={blocked}>
          ⛔ {blocked}
        </div>
      )}

      {/* Причина устаревания — у dropped ВСЕГДА, даже когда её нет: старые карточки без
          причины говорят это словами (тот же текст, что CLI-список), а не молчат как
          «нечего показать». Класс дыры — «поле пишется и не читается» (карточка #197). */}
      {task.status === 'dropped' && (
        <div
          className="tile__dropped-reason"
          data-group={`tile-dropped-reason-${task.id}`}
          title={task.droppedReason ?? 'НЕ ЗАПИСАНА (устарела до ворот 14.08)'}
        >
          ✗ причина: {task.droppedReason ?? 'НЕ ЗАПИСАНА (устарела до ворот 14.08)'}
        </div>
      )}

      {task.tags.length > 0 && (
        <div className="tile__tags" data-group={`tile-tags-${task.id}`}>
          {task.tags.map((tag) => <span key={tag} className="tag">{tag}</span>)}
        </div>
      )}
    </article>
  );
}
