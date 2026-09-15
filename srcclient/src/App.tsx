import { useState } from 'react';
import { api } from './api';
import { usePolling } from './usePolling';
import { useUrlEnum } from './useUrlState';
import type { Health, Overview } from './types';
import { SourceBar } from './components/SourceBar';
import { StatCard } from './components/MeasureValue';
import { ErrorBoundary } from './components/ErrorBoundary';
import { TasksPage } from './pages/TasksPage';
import { HistoryPage } from './pages/HistoryPage';
import { FeedPage } from './pages/FeedPage';
import { RolesPage } from './pages/RolesPage';
import { RulesPage } from './pages/RulesPage';
import { SchemaPage } from './pages/SchemaPage';

type Tab = 'tasks' | 'history' | 'feed' | 'roles' | 'rules' | 'schema';

const TABS: Array<{ id: Tab; title: string }> = [
  { id: 'tasks', title: 'Задачи' },
  { id: 'history', title: 'Динамика задач' },
  { id: 'feed', title: 'Лента' },
  { id: 'roles', title: 'Роли' },
  { id: 'rules', title: 'Правила' },
  { id: 'schema', title: 'Схема' },
];

const TAB_IDS: readonly Tab[] = TABS.map((t) => t.id);

export default function App() {
  // Открытая вкладка живёт В АДРЕСЕ (?page=…), как фильтры страниц: иначе перезагрузка
  // возвращала на «Задачи», а фильтры «Динамики задач» из адреса оставались без своей
  // страницы. Смена вкладки — шаг истории: «назад» возвращает на прежнюю вкладку.
  const [tab, setTab] = useUrlEnum<Tab>('page', TAB_IDS, 'tasks', 'push');
  const [generation, setGeneration] = useState(0);

  // Состояние сервиса опрашиваем чаще, чем данные: по нему видно,
  // жив ли бэкенд и когда он в последний раз перечитывал базу.
  const health = usePolling<Health>(() => api.health(), 5000, [generation]);
  const refreshMs = Math.max(5, health.data?.refreshSeconds ?? 15) * 1000;
  const overview = usePolling<Overview>(() => api.overview(), refreshMs, [generation]);

  const onSourceChanged = () => setGeneration((g) => g + 1);

  return (
    // Страница задач несёт полосу рейлов и потому выходит из общей рамки 1600px:
    // рамка считалась под одно содержимое, и при появлении рейла место отнималось бы
    // у таблицы — то есть у колонок, которые человек пришёл смотреть.
    <div className={`app ${tab === 'tasks' ? 'app--wide' : ''}`} data-panel="app">
      <header className="header">
        <h1>Перископ</h1>
        <div className="muted">
          {overview.data?.groupName ? `группа: ${overview.data.groupName} · ` : ''}
          {health.data?.activeDbPath ?? 'база не выбрана'}
        </div>
      </header>

      <SourceBar health={health.data} onChanged={onSourceChanged} />

      {health.error && (
        <div className="banner banner--error">
          Бэкенд не отвечает: {health.error}. Он запускается отдельно — см. ../src/README.md.
        </div>
      )}

      {overview.data && tab !== 'tasks' && (
        <div className="stats">
          <StatCard label="записок" measure={overview.data.messages} />
          <StatCard label="в истории" measure={overview.data.messagesHistory} />
          <StatCard label="ролей" measure={overview.data.roles} />
          <StatCard label="правил" measure={overview.data.rules} />
          <StatCard label="открытых задач без критерия" measure={overview.data.tasksOpenWithoutCriterion} tone="warn" />
        </div>
      )}

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? 'tab--active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.title}
          </button>
        ))}
      </nav>

      {/*
        Ловушка обёрнута ВОКРУГ АКТИВНОЙ СТРАНИЦЫ, а не вокруг всего приложения:
        упавшая страница обязана падать одна. Вкладки при этом остаются на месте,
        и человек уходит на соседнюю страницу вместо перезагрузки браузера.
        `key={tab}` сбрасывает ловушку при смене вкладки — иначе сообщение об ошибке
        одной страницы осталось бы висеть поверх другой, исправной.
      */}
      <main>
        <ErrorBoundary key={tab} where={`страница «${TABS.find((t) => t.id === tab)?.title ?? tab}»`}>
          {tab === 'tasks' && <TasksPage overview={overview.data} refreshMs={refreshMs} />}
          {tab === 'history' && <HistoryPage refreshMs={refreshMs} />}
          {tab === 'feed' && <FeedPage refreshMs={refreshMs} />}
          {tab === 'roles' && <RolesPage overview={overview.data} refreshMs={refreshMs} />}
          {tab === 'rules' && <RulesPage refreshMs={refreshMs} />}
          {tab === 'schema' && <SchemaPage overview={overview.data} refreshMs={refreshMs} />}
        </ErrorBoundary>
      </main>

      <footer className="footer muted">
        Сервис открывает базу ТОЛЬКО НА ЧТЕНИЕ и ничего в неё не пишет.
        Время везде UTC.
      </footer>
    </div>
  );
}
