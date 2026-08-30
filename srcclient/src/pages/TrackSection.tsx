import type { ReactNode } from 'react';
import type { Task, TaskGroup } from '../types';
import { TasksBoard } from './TasksBoard';

/**
 * СЕКЦИЯ ОДНОГО НАБОРА ЗАДАЧ: заголовок набора + доска ролей внутри него.
 *
 * 🎯 Почему набор — верхний уровень, а роли остались внутри. Доска отвечает на вопрос
 *    «чем занята роль», набор — на вопрос «куда эта работа входит». Второй вопрос
 *    крупнее первого: сперва видно, что делает контур, потом — кто именно. Обратная
 *    вложенность (колонка роли, внутри неё наборы) разорвала бы колонки и убила ответ
 *    доски, ради которого она заведена.
 *
 * 🔴 ГРУППА «БЕЗ НАБОРА» — ТАКАЯ ЖЕ СЕКЦИЯ, А НЕ ОСТАТОК. `trackId === null` рисуется
 *    ровно так же, с числом и заголовком словами. Задачи, не приписанные ни к чему,
 *    легче всего теряются именно на экране: их не показывают «чтобы не мешали», и
 *    пропажу нечем заметить — пустого места после них не остаётся.
 *
 * ⚠️ ПУСТАЯ ГРУППА ТОЖЕ РИСУЕТСЯ. «Набор есть, задач в нём нет» и «набора нет» — разные
 *    новости, и вторая нам никем не сообщается. Поэтому у пустой группы стои́т строка
 *    словами, а не отсутствие секции.
 */
export function TrackSection({
  group,
  tasks,
  allTasks,
  selectedId,
  onSelect,
  detailRail,
  order,
  nowMs,
  collapsed,
  onToggle,
}: {
  group: TaskGroup;
  /** Задачи набора, прошедшие фильтры страницы, — они станут плитками. */
  tasks: Task[];
  /** Полный набор задач (всех наборов): нужен доске для честного «показано из всего у роли». */
  allTasks: Task[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  detailRail?: ReactNode;
  order: (a: Task, b: Task) => number;
  nowMs: number;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const key = group.trackId ?? '(без набора)';
  const isUntracked = group.trackId === null;
  const hidden = group.count - tasks.length;

  return (
    <section
      className={`tracksec ${isUntracked ? 'tracksec--untracked' : ''}`}
      data-group={`track-section-${key}`}
      data-track={key}
      data-count={tasks.length}
      data-count-total={group.count}
    >
      <header className="tracksec__head">
        <button
          className="tracksec__toggle"
          onClick={onToggle}
          data-control={`track-toggle-${key}`}
          title={collapsed ? 'развернуть набор' : 'свернуть набор'}
          aria-expanded={!collapsed}
        >
          {collapsed ? '▶' : '▼'}
        </button>

        <h3 className="tracksec__title">
          {isUntracked ? 'Без набора' : group.trackId}
          {/* Число ВСЕГДА рядом с именем: секция без числа заставляет считать плитки глазами. */}
          <span className="tracksec__n" data-control={`track-count-${key}`}>
            {tasks.length}
            {hidden > 0 && (
              <span className="muted" title={`всего в наборе: ${group.count}; фильтры скрыли ${hidden}`}>
                {' '}/ {group.count}
              </span>
            )}
          </span>
        </h3>

        {group.status && (
          <span className={`tracksec__status tracksec__status--${group.status}`}>{group.status}</span>
        )}

        {/* Набор, которого нет в таблице наборов: задачи его называют, а записи нет.
            Молчать об этом нельзя — заголовка и статуса у такой секции не будет,
            и пустое место читалось бы как небрежность экрана, а не как факт базы. */}
        {!isUntracked && !group.declared && (
          <span
            className="tracksec__warn"
            data-control={`track-undeclared-${key}`}
            title="этот набор задачи называют, а записи о нём в таблице наборов нет"
          >
            ⚠ нет в таблице наборов
          </span>
        )}
      </header>

      {group.title && <p className="tracksec__sub muted">{group.title}</p>}

      {isUntracked && (
        <p className="tracksec__sub muted" data-panel="untracked-explain">
          задачи, не приписанные ни к одному набору. Показаны отдельной группой намеренно:
          иначе они пропали бы с экрана, а пропажу нечем было бы заметить
        </p>
      )}

      {!collapsed && group.count === 0 && (
        <p className="muted" data-panel={`track-empty-${key}`}>
          набор есть, задач в нём нет — это не то же самое, что «набора нет»
        </p>
      )}

      {!collapsed && group.count > 0 && tasks.length === 0 && (
        <p className="muted" data-panel={`track-filtered-out-${key}`}>
          под фильтр не попало ни одной из {group.count} — карточки набора никуда не делись,
          их отсеял фильтр
        </p>
      )}

      {!collapsed && tasks.length > 0 && (
        <TasksBoard
          tasks={tasks}
          allTasks={allTasks}
          selectedId={selectedId}
          onSelect={onSelect}
          detailRail={detailRail}
          order={order}
          nowMs={nowMs}
        />
      )}
    </section>
  );
}
