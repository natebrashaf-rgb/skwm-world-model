import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import OverviewPage from './pages/OverviewPage'
import GraphPage from './pages/GraphPage'
import HotspotPage from './pages/HotspotPage'
import FrontierPage from './pages/FrontierPage'
import TrendPage from './pages/TrendPage'
import ScienceMapPage from './pages/ScienceMapPage'
import QaPage from './pages/QaPage'
import ReportPage from './pages/ReportPage'
import ModelPage from './pages/ModelPage'
import TimelinePage from './pages/TimelinePage'
import DataPage from './pages/DataPage'
import LibrarianDashboard from './pages/LibrarianDashboard'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/hotspot" element={<HotspotPage />} />
        <Route path="/frontier" element={<FrontierPage />} />
        <Route path="/trend" element={<TrendPage />} />
        <Route path="/sciencemap" element={<ScienceMapPage />} />
        <Route path="/qa" element={<QaPage />} />
        <Route path="/report" element={<ReportPage />} />
        <Route path="/model" element={<ModelPage />} />
        <Route path="/timeline" element={<TimelinePage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="/dashboard" element={<LibrarianDashboard />} />
      </Routes>
    </AppLayout>
  )
}
