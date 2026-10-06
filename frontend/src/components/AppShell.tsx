// Provena application shell: compact sidebar, contextual topbar with global
// search and creation, user menu, and theme control.

import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { FolderKanban, LayoutDashboard, LogOut, Moon, Plus, Sun } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "./Toast";
import { useTheme } from "../theme/ThemeContext";
import { Avatar, BrandLockup, BrandMark } from "./Brand";
import { GlobalSearch } from "./GlobalSearch";
import { Menu } from "./Menu";
import { NewInvestigationDialog } from "./NewInvestigationDialog";
import { RoleBadge } from "./Badge";
import { Button } from "./Button";
import { ThemeToggle } from "./ThemeToggle";
import { displayName } from "../lib/format";

const NAV = [
  { to: "/", label: "Dashboard", end: true, icon: <LayoutDashboard size={15} /> },
  { to: "/investigations", label: "Investigations", end: false, icon: <FolderKanban size={15} /> },
];

const PLANNED = ["Findings", "AI Analysis", "Reports"];

export default function AppShell() {
  const { user, logout } = useAuth();
  const { notify } = useToast();
  const [creating, setCreating] = useState(false);
  const canCreate = user?.role === "admin" || user?.role === "investigator";

  async function onLogout() {
    await logout();
    notify("success", "Signed out.");
  }

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface lg:flex">
        <Link to="/" className="flex items-center border-b border-line px-5 py-4" aria-label="Provena home">
          <BrandLockup height={22} />
        </Link>

        <nav aria-label="Primary" className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `pv-transition flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium ${
                  isActive ? "bg-hover text-ink" : "text-ink2 hover:bg-hover hover:text-ink"
                }`
              }
            >
              <span className="text-ink3">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}

          <p className="px-2.5 pt-4 pb-1 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
            Planned
          </p>
          {PLANNED.map((label) => (
            <span
              key={label}
              title="Planned for a future milestone"
              className="flex cursor-not-allowed items-center justify-between rounded-md px-2.5 py-1.5 text-sm text-ink3"
            >
              {label}
              <span className="rounded border border-line px-1.5 py-px text-[10px] font-medium tracking-wide uppercase">
                Soon
              </span>
            </span>
          ))}
        </nav>

        <div className="space-y-3 border-t border-line px-4 py-3">
          <ThemeToggle />
          {user && (
            <div className="flex items-center gap-2.5">
              <Avatar name={user.username} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{displayName(user)}</p>
                <p className="truncate text-xs text-ink3">{user.username}</p>
              </div>
              <button
                onClick={() => void onLogout()}
                title="Log out"
                aria-label="Log out"
                className="pv-transition cursor-pointer rounded-md p-1.5 text-ink3 hover:bg-hover hover:text-ink"
              >
                <LogOut size={15} />
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
          <div className="flex h-14 w-full items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-2 lg:hidden">
              <Link to="/" className="shrink-0" aria-label="Provena home">
                <BrandMark size={22} />
              </Link>
              <nav aria-label="Primary" className="flex shrink-0 items-center gap-1">
                {NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `rounded-md px-2 py-1 text-sm font-medium ${
                        isActive ? "bg-hover text-ink" : "text-ink2 hover:text-ink"
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>

            <div className="ml-auto flex items-center gap-2.5 sm:gap-3">
              <GlobalSearch />
              {canCreate && (
                <Button
                  variant="primary"
                  size="sm"
                  icon={<Plus size={14} />}
                  onClick={() => setCreating(true)}
                  className="h-8 shadow-xs"
                >
                  <span className="hidden sm:inline">New Investigation</span>
                  <span className="sm:hidden">New</span>
                </Button>
              )}
              <div className="lg:hidden">
                <ThemeToggleCompact />
              </div>
              {user && (
                <Menu
                  label="Account"
                  trigger={
                    <button
                      aria-label="Account menu"
                      className="pv-transition flex cursor-pointer items-center justify-center rounded-full p-0.5 hover:ring-2 hover:ring-line focus-visible:outline-none"
                    >
                      <Avatar name={user.username} />
                    </button>
                  }
                  header={
                    <div>
                      <p className="truncate text-sm font-medium">{displayName(user)}</p>
                      <p className="truncate text-xs text-ink3">{user.username}</p>
                      <div className="mt-1.5">
                        <RoleBadge role={user.role} />
                      </div>
                    </div>
                  }
                  items={[{ key: "logout", label: "Log out", icon: <LogOut size={14} />, onSelect: () => void onLogout() }]}
                />
              )}
            </div>
          </div>
        </header>

        <main className="min-w-0 flex-1">
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
            <Outlet />
          </div>
        </main>
      </div>

      <NewInvestigationDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function ThemeToggleCompact() {
  const { dark, setChoice } = useTheme();
  return (
    <button
      type="button"
      title={dark ? "Switch to light theme" : "Switch to dark theme"}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setChoice(dark ? "light" : "dark")}
      className="pv-transition flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-ink2 hover:bg-hover hover:text-ink"
    >
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}
