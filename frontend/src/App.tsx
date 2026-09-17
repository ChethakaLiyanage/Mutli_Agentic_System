import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./context/auth-context";
import { DashboardPage } from "./pages/DashboardPage";
import { ClaimAssistantPage } from "./pages/ClaimAssistantPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";

const PublicOnlyRoute = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="page-loading" role="status">Loading…</div>;
  }
  return user ? <Navigate to="/dashboard" replace /> : <Outlet />;
};

const HomeRedirect = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="page-loading" role="status">Loading…</div>;
  }
  return <Navigate to={user ? "/dashboard" : "/login"} replace />;
};

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/claim-assistant" element={<ClaimAssistantPage />} />
        </Route>
      </Route>

      <Route path="/" element={<HomeRedirect />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
