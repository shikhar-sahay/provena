// Provena application shell: compact sidebar, contextual topbar with global
// search and creation, user menu, and theme control.

import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Building2, FolderKanban, LayoutDashboard, LogOut, Plus, ShieldAlert, Users } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "./Toast";
import { Avatar, BrandLockup, BrandMark } from "./Brand";
import { GlobalSearch } from "./GlobalSearch";
import { Menu } from "./Menu";
import { NewInvestigationDialog } from "./NewInvestigationDialog";
import { RoleBadge } from "./Badge";
import { Button } from "./Button";
import { ThemeToggle } from "./ThemeToggle";
import { ProvenanceMotif } from "./ProvenanceMotif";
import { displayName } from "../lib/format";

const NAV = [
  { to: "/", label: "Dashboard", end: true, icon: <LayoutDashboard size={15} />, admin: false },
  { to: "/investigations", label: "Investigations", end: false, icon: <FolderKanban size={15} />, admin: false },
  { to: "/findings", label: "Findings", end: false, icon: <ShieldAlert size={15} />, admin: false },
  { to: "/users", label: "Users", end: true, icon: <Users size={15} />, admin: true },
  { to: "/workspace", label: "Workspace", end: true, icon: <Building2 size={15} />, admin: true },
];

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
        <Link
          to="/"
          className="pv-transition flex h-14 items-center justify-center border-b border-line px-5 hover:bg-hover"
          aria-label="Provena home"
        >
          <BrandLockup height={24} />
        </Link>

        <nav aria-label="Primary" className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
          {NAV.filter((item) => !item.admin || user?.role === "admin").map((item) => (
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
        </nav>

        <div className="border-t border-line px-4 py-3">
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

      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <ProvenanceMotif className="app-motif pointer-events-none absolute inset-0 h-full w-full text-ink" />
        <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
          <div className="flex h-14 w-full items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
            <div className="flex items-center lg:hidden">
              <Link to="/" className="shrink-0" aria-label="Provena home">
                <BrandMark size={22} />
              </Link>
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
                  <span className="hidden sm:inline">New investigation</span>
                  <span className="sm:hidden">New</span>
                </Button>
              )}
              <ThemeToggle />
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

        <main className="relative z-10 min-w-0 flex-1 pb-20 lg:pb-0">
          <div className="mx-auto max-w-6xl px-3 py-4 sm:px-6 sm:py-6">
            <Outlet />
          </div>
        </main>
      </div>

      <nav
        aria-label="Primary mobile navigation"
        className="fixed inset-x-0 bottom-0 z-40 grid border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
        style={{ gridTemplateColumns: `repeat(${NAV.filter((item) => !item.admin || user?.role === "admin").length}, minmax(0, 1fr))` }}
      >
        {NAV.filter((item) => !item.admin || user?.role === "admin").map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `pv-transition flex min-w-0 flex-col items-center gap-1 px-1 py-2 text-[10px] font-medium ${
                isActive ? "bg-hover text-ink" : "text-ink2 hover:bg-hover hover:text-ink"
              }`
            }
          >
            <span className="text-ink3">{item.icon}</span>
            <span className="w-full truncate text-center">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <NewInvestigationDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
