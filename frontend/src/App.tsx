// Router: public login route plus the authenticated application shell.

import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import type { ReactNode } from "react";
import AppShell from "./components/AppShell";
import AnalysisPage from "./pages/AnalysisPage";
import AuditTab from "./pages/AuditTab";
import CustodyTab from "./pages/CustodyTab";
import DashboardPage from "./pages/DashboardPage";
import EvidenceDetailPage from "./pages/EvidenceDetailPage";
import EvidenceTab from "./pages/EvidenceTab";
import FindingsWorkspacePage from "./pages/FindingsWorkspacePage";
import InvestigationOverview from "./pages/InvestigationOverview";
import InvestigationWorkspace from "./pages/InvestigationWorkspace";
import InvestigationsPage from "./pages/InvestigationsPage";
import LoginPage from "./pages/LoginPage";
import OnboardingPage from "./pages/OnboardingPage";
import RegisterPage from "./pages/RegisterPage";
import WorkspacePage from "./pages/WorkspacePage";
import RegisterEvidencePage from "./pages/RegisterEvidencePage";
import ReportsPage from "./pages/ReportsPage";
import TimelineTab from "./pages/TimelineTab";
import UsersPage from "./pages/UsersPage";
import "./index.css";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="p-8 text-sm text-ink2">Loading Provena…</p>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="p-8 text-sm text-ink2">Loading Provena…</p>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireWorkspace({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-8 text-sm text-ink2">Loading Provena...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.active_workspace_id) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/onboarding" element={<RequireAuth><OnboardingPage /></RequireAuth>} />
      <Route
        element={
          <RequireAuth>
            <RequireWorkspace><AppShell /></RequireWorkspace>
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="investigations" element={<InvestigationsPage />} />
        <Route path="findings" element={<FindingsWorkspacePage />} />
        <Route path="users" element={<RequireAdmin><UsersPage /></RequireAdmin>} />
        <Route path="workspace" element={<RequireAdmin><WorkspacePage /></RequireAdmin>} />
        <Route path="investigations/:id" element={<InvestigationWorkspace />}>
          <Route index element={<InvestigationOverview />} />
          <Route path="evidence" element={<EvidenceTab />} />
          <Route path="evidence/register" element={<RegisterEvidencePage />} />
          <Route path="evidence/:eid" element={<EvidenceDetailPage />} />
          <Route path="analysis" element={<AnalysisPage />} />
          <Route path="timeline" element={<TimelineTab />} />
          <Route path="custody" element={<CustodyTab />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="audit" element={<AuditTab />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
