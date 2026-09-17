import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../context/auth-context";

export const ProtectedRoute = () => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="page-loading" role="status" aria-live="polite">
        <span className="loading-spinner" aria-hidden="true" />
        Loading your account…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
};
