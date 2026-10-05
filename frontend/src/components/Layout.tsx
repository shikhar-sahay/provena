// Authenticated application shell: sidebar navigation, user info, logout.

import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ROLE_LABELS } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/investigations", label: "Investigations", end: false },
];

const COMING_SOON = ["Evidence", "AI Analysis", "Reports"];

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60">
        <div className="border-b border-slate-800 px-5 py-4">
          <p className="text-lg font-semibold tracking-tight">Provena</p>
          <p className="text-xs text-slate-500">Investigation Platform</p>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium ${
                  isActive
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}

          <p className="px-3 pb-1 pt-4 text-xs font-medium uppercase tracking-wider text-slate-600">
            Planned
          </p>
          {COMING_SOON.map((label) => (
            <span
              key={label}
              title="Not implemented yet"
              className="flex cursor-not-allowed items-center justify-between rounded-md px-3 py-2 text-sm text-slate-600"
            >
              {label}
              <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
                Soon
              </span>
            </span>
          ))}
        </nav>

        <div className="border-t border-slate-800 px-5 py-4">
          <p className="truncate text-sm font-medium">{user?.full_name || user?.username}</p>
          <p className="text-xs text-slate-500">
            {user ? ROLE_LABELS[user.role] : ""} · {user?.username}
          </p>
          <button
            onClick={() => void logout()}
            className="mt-3 w-full rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            Log out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
