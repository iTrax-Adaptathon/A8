import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/Layout/AppLayout';
import { CapacityOverview } from './pages/CapacityOverview';
import { Resources } from './pages/Resources';
import { PatientFlow } from './pages/PatientFlow';
import { AuditHistory } from './pages/AuditHistory';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/capacity" replace />} />
          <Route path="/capacity" element={<CapacityOverview />} />
          <Route path="/resources" element={<Resources />} />
          <Route path="/patients" element={<PatientFlow />} />
          <Route path="/audit" element={<AuditHistory />} />
          <Route path="*" element={<Navigate to="/capacity" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
