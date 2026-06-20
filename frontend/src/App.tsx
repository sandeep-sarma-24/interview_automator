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

      <Route path="/404" element={<NotFoundPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
