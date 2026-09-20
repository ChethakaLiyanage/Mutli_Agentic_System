import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./context/auth-context";
import { DashboardPage } from "./pages/DashboardPage";
import { ClaimAssistantPage } from "./pages/ClaimAssistantPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AdminLoginPage } from "./pages/AdminLoginPage";

const PublicOnlyRoute = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="page-loading" role="status">Loading…</div>;
  }
  return user ? (
    <Navigate to={user.role === "admin" ? "/admin-dashboard" : "/dashboard"} replace />
  ) : <Outlet />;
};

const HomeRedirect = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="page-loading" role="status">Loading…</div>;
  }
  return <Navigate to={user ? (user.role === "admin" ? "/admin-dashboard" : "/dashboard") : "/login"} replace />;
};

const AdminRoute = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="page-loading" role="status">Loading…</div>;
  }

  return user?.role === "admin" ? (
    <Outlet />
  ) : (
    <Navigate to={user ? "/dashboard" : "/admin-login"} replace />
  );
};

const NonAdminRoute = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="page-loading" role="status">Loading…</div>;
  }

  return user?.role !== "admin" ? (
    <Outlet />
  ) : (
    <Navigate to="/admin-dashboard" replace />
  );
};

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/admin-login" element={<AdminLoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route element={<NonAdminRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/claim-assistant" element={<ClaimAssistantPage />} />
          </Route>
          <Route element={<AdminRoute />}>
            <Route path="/admin-dashboard" element={<AdminDashboard />} />
          </Route>
        </Route>
      </Route>

      <Route path="/" element={<HomeRedirect />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
