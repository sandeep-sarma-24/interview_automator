import { NavLink, Outlet } from "react-router-dom";
import { useOpsAuth } from "../OpsAuthContext";

const NAV = [
  { to: "/ops", label: "Overview", end: true },
  { to: "/ops/discovery", label: "Discovery" },
  { to: "/ops/worker", label: "Worker" },
  { to: "/ops/api-calls", label: "API Calls" },
  { to: "/ops/errors", label: "Errors" },
  { to: "/ops/roles", label: "Roles" },
  { to: "/ops/explain", label: "Score Inspector" },
];

export default function OpsShell() {
  const { logout } = useOpsAuth();
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-2.5">
          <span className="text-sm font-bold">⚙ Operator</span>
          <nav className="flex flex-1 flex-wrap gap-1 text-sm">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `rounded px-2.5 py-1 ${isActive ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <button onClick={logout} className="text-xs text-slate-500 hover:text-red-600">
            Log out
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-5">
        <Outlet />
      </main>
    </div>
  );
}
