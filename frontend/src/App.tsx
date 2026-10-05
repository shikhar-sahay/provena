// Router: public login route plus the authenticated application shell.

import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import type { ReactNode } from "react";
import Layout from "./components/Layout";
import AuditTab from "./pages/AuditTab";
import CustodyTab from "./pages/CustodyTab";
import DashboardPage from "./pages/DashboardPage";
import EvidenceDetailPage from "./pages/EvidenceDetailPage";
import EvidenceTab from "./pages/EvidenceTab";
import InvestigationOverview from "./pages/InvestigationOverview";
import InvestigationWorkspace from "./pages/InvestigationWorkspace";
import InvestigationsPage from "./pages/InvestigationsPage";
import LoginPage from "./pages/LoginPage";
import NewInvestigationPage from "./pages/NewInvestigationPage";
import RegisterEvidencePage from "./pages/RegisterEvidencePage";
import TimelineTab from "./pages/TimelineTab";
import "./index.css";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="p-8 text-sm text-slate-400">Loading Provena…</p>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireCreator({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <p className="p-8 text-sm text-slate-400">Loading Provena…</p>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin" && user.role !== "investigator") {
    return <Navigate to="/investigations" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="investigations" element={<InvestigationsPage />} />
        <Route
          path="investigations/new"
          element={
            <RequireCreator>
              <NewInvestigationPage />
            </RequireCreator>
          }
        />
        <Route path="investigations/:id" element={<InvestigationWorkspace />}>
          <Route index element={<InvestigationOverview />} />
          <Route path="evidence" element={<EvidenceTab />} />
          <Route path="evidence/register" element={<RegisterEvidencePage />} />
          <Route path="evidence/:eid" element={<EvidenceDetailPage />} />
          <Route path="timeline" element={<TimelineTab />} />
          <Route path="custody" element={<CustodyTab />} />
          <Route path="audit" element={<AuditTab />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
