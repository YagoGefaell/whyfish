import { ChartColumn, Dumbbell, FileUp, History, Settings, Swords } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink, Route, Routes } from 'react-router'
import { EngineStatus } from './components/EngineStatus'
import { HistoryPage } from './features/history/HistoryPage'
import { ImportPage } from './features/import/ImportPage'
import { NewGamePage } from './features/play/NewGamePage'
import { PlayPage } from './features/play/PlayPage'
import { ReviewPage } from './features/review/ReviewPage'
import { SettingsPage } from './features/settings/SettingsPage'
import { StatsPage } from './features/stats/StatsPage'
import { TrainPage } from './features/train/TrainPage'

function NavItem({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
          isActive ? 'bg-panel-2 text-fg' : 'text-muted hover:bg-panel hover:text-fg'
        }`
      }
    >
      {icon}
      {children}
    </NavLink>
  )
}

export default function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-[1400px] flex-col px-4 pb-4 sm:px-6">
      <header className="flex min-h-12 shrink-0 flex-wrap items-center gap-x-4 gap-y-1 py-1.5">
        <h1 className="text-lg font-bold tracking-tight">
          why<span className="text-accent">fish</span>
        </h1>
        <nav className="flex flex-wrap gap-1">
          <NavItem to="/" icon={<Swords size={16} />}>
            Jugar
          </NavItem>
          <NavItem to="/import" icon={<FileUp size={16} />}>
            Importar
          </NavItem>
          <NavItem to="/games" icon={<History size={16} />}>
            Historial
          </NavItem>
          <NavItem to="/stats" icon={<ChartColumn size={16} />}>
            Estadísticas
          </NavItem>
          <NavItem to="/train" icon={<Dumbbell size={16} />}>
            Entrenar
          </NavItem>
          <NavItem to="/settings" icon={<Settings size={16} />}>
            Ajustes
          </NavItem>
        </nav>
        <span className="ml-auto text-sm">
          <EngineStatus />
        </span>
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<NewGamePage />} />
          <Route path="/play/:id" element={<PlayPage />} />
          <Route path="/games" element={<HistoryPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/review/:id" element={<ReviewPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/train" element={<TrainPage />} />
          <Route path="*" element={<p>Página no encontrada.</p>} />
        </Routes>
      </main>
    </div>
  )
}
