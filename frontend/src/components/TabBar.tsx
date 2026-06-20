import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/", label: "Dashboard", icon: "▢", end: true },
  { to: "/review", label: "Review", icon: "⭐", end: false },
  { to: "/companies", label: "Companies", icon: "🏢", end: false },
  { to: "/you", label: "You", icon: "👤", end: false },
];

export default function TabBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 border-t border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
      <div className="mx-auto flex max-w-md">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 py-2 text-xs ${
                isActive ? "text-blue-600 dark:text-blue-400" : "text-slate-500"
              }`
            }
          >
            <span className="text-lg leading-none">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
