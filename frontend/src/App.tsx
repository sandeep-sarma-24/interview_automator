import { Navigate, Route, Routes } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth";
import RequireProfile from "./auth/RequireProfile";
import AppShell from "./components/AppShell";
import LoginPage from "./pages/LoginPage";
import OnboardingWizard from "./pages/OnboardingWizard";
import DashboardPage from "./pages/DashboardPage";
import ReviewPage from "./pages/ReviewPage";
import ApplicationDetailPage from "./pages/ApplicationDetailPage";
import CompaniesPage from "./pages/CompaniesPage";
import DiagnosticsPage from "./pages/DiagnosticsPage";
import YouPage from "./pages/YouPage";
import NotFoundPage from "./pages/NotFoundPage";
import RequireOps from "./ops/RequireOps";
import OpsLogin from "./ops/pages/OpsLogin";
import OpsOverview from "./ops/pages/OpsOverview";
import OpsDiscovery from "./ops/pages/OpsDiscovery";
import OpsWorker from "./ops/pages/OpsWorker";
import OpsApiCalls from "./ops/pages/OpsApiCalls";
import OpsErrors from "./ops/pages/OpsErrors";
import OpsRoles from "./ops/pages/OpsRoles";
import OpsExplain from "./ops/pages/OpsExplain";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAuth />}>
        <Route path="/onboarding" element={<OnboardingWizard />} />

        <Route element={<RequireProfile />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/review/:applicationId" element={<ApplicationDetailPage />} />
            <Route path="/companies" element={<CompaniesPage />} />
            <Route path="/diagnostics" element={<DiagnosticsPage />} />
            <Route path="/you" element={<YouPage />} />
          </Route>
        </Route>
      </Route>

      {/* Operator dashboard — separate OPS_TOKEN auth, not the candidate login */}
      <Route path="/ops/login" element={<OpsLogin />} />
      <Route path="/ops" element={<RequireOps />}>
        <Route index element={<OpsOverview />} />
        <Route path="discovery" element={<OpsDiscovery />} />
        <Route path="worker" element={<OpsWorker />} />
        <Route path="api-calls" element={<OpsApiCalls />} />
        <Route path="errors" element={<OpsErrors />} />
        <Route path="roles" element={<OpsRoles />} />
        <Route path="explain" element={<OpsExplain />} />
      </Route>

      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
