import { NavLink, Route, Routes } from 'react-router'
import { EngineStatus } from './components/EngineStatus'
import { HistoryPage } from './features/history/HistoryPage'
import { ImportPage } from './features/import/ImportPage'
import { NewGamePage } from './features/play/NewGamePage'
import { PlayPage } from './features/play/PlayPage'
import { ReviewPage } from './features/review/ReviewPage'

const navClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'font-semibold text-blue-800' : 'text-gray-600 hover:text-gray-900'

export default function App() {
  return (
    <div className="mx-auto max-w-5xl p-4 font-sans sm:p-8">
      <header className="mb-6 flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <h1 className="text-2xl font-bold">whyfish</h1>
        <nav className="flex gap-4">
          <NavLink to="/" end className={navClass}>
            Nueva partida
          </NavLink>
          <NavLink to="/import" className={navClass}>
            Importar
          </NavLink>
          <NavLink to="/games" className={navClass}>
            Historial
          </NavLink>
        </nav>
        <span className="ml-auto text-sm">
          <EngineStatus />
        </span>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<NewGamePage />} />
          <Route path="/play/:id" element={<PlayPage />} />
          <Route path="/games" element={<HistoryPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/review/:id" element={<ReviewPage />} />
          <Route path="*" element={<p>Página no encontrada.</p>} />
        </Routes>
      </main>
    </div>
  )
}
