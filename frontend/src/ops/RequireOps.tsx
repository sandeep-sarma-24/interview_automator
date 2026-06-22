import { Navigate } from "react-router-dom";
import { useOpsAuth } from "./OpsAuthContext";
import OpsShell from "./components/OpsShell";

// Guard + layout for the operator section. The OPS_TOKEN is independent of the
// candidate login. A wrong/expired token triggers a 401 -> logout via opsClient.
export default function RequireOps() {
  const { token } = useOpsAuth();
  if (!token) return <Navigate to="/ops/login" replace />;
  return <OpsShell />;
}
