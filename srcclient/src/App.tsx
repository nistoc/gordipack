import { useState } from 'react';
import { api } from './api';
import { usePolling } from './usePolling';
import type { Health, Overview } from './types';
import { SourceBar } from './components/SourceBar';
import { StatCard } from './components/MeasureValue';
import { TasksPage } from './pages/TasksPage';
import { FeedPage } from './pages/FeedPage';
import { RolesPage } from './pages/RolesPage';
import { RulesPage } from './pages/RulesPage';
import { SchemaPage } from './pages/SchemaPage';

type Tab = 'tasks' | 'feed' | 'roles' | 'rules' | 'schema';

const TABS: Array<{ id: Tab; title: string }> = [
  { id: 'tasks', title: 'Задачи' },
  { id: 'feed', title: 'Лента' },
  { id: 'roles', title: 'Роли' },
  { id: 'rules', title: 'Правила' },
  { id: 'schema', title: 'Схема' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('tasks');
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

      <main>
        {tab === 'tasks' && <TasksPage overview={overview.data} refreshMs={refreshMs} />}
        {tab === 'feed' && <FeedPage refreshMs={refreshMs} />}
        {tab === 'roles' && <RolesPage overview={overview.data} refreshMs={refreshMs} />}
        {tab === 'rules' && <RulesPage refreshMs={refreshMs} />}
        {tab === 'schema' && <SchemaPage overview={overview.data} refreshMs={refreshMs} />}
      </main>

      <footer className="footer muted">
        Сервис открывает базу ТОЛЬКО НА ЧТЕНИЕ и ничего в неё не пишет.
        Время везде UTC.
      </footer>
    </div>
  );
}
