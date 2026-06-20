import { Navigate, Outlet } from "react-router-dom";
import { useProfile } from "../hooks/useProfile";
import LoadingSkeleton from "../components/LoadingSkeleton";

// Gate the app behind a completed trajectory profile (scoring needs it).
export default function RequireProfile() {
  const { data, isLoading, isError } = useProfile();
  if (isLoading) return <LoadingSkeleton label="Loading profile…" />;
  if (isError) return <Navigate to="/login" replace />;
  if (data && !data.has_profile) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}
