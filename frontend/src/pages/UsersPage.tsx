// Admin user management: roster with investigation context, creation,
// and activation control. Admin-only on both sides.

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ShieldAlert, UserPlus, Users } from "lucide-react";
import { api } from "../api/client";
import type { AdminUser, Role } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { RoleBadge } from "../components/Badge";
import { Avatar } from "../components/Brand";
import { Button } from "../components/Button";
import { Dialog } from "../components/Dialog";
import { Field, Input, Select } from "../components/Field";
import { EmptyState, ErrorState, PageHeader, TableSkeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { actionErrorMessage } from "../lib/errors";
import { displayName, formatDate } from "../lib/format";

const ROLES: Role[] = ["admin", "investigator", "forensic_analyst", "evidence_custodian"];

export default function UsersPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setUsers(await api.adminListUsers());
      setError(null);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load users."));
    }
  }, []);

  useEffect(() => {
    setUsers(null);
    void load();
  }, [load]);

  async function toggleActive(target: AdminUser) {
    try {
      const updated = await api.adminSetActive(target.id, !target.is_active);
      setUsers((current) => current?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
      notify("success", updated.is_active ? "Account reactivated." : "Account deactivated.");
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not update the account."));
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Users"
        description="Accounts, roles, activation, and investigation access. Changes are audited."
        actions={
          <Button variant="primary" size="sm" icon={<UserPlus size={14} />} onClick={() => setCreating(true)}>
            New user
          </Button>
        }
      />

      {error && <ErrorState body={error} onRetry={() => void load()} />}
      {users === null && !error && <TableSkeleton rows={5} />}
      {users !== null && users.length === 0 && (
        <EmptyState icon={<Users size={22} />} title="No users" body="User accounts will appear here." />
      )}
      {users !== null && users.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full min-w-[52rem] text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-surface text-[13px] text-ink2">
                <th className="px-3 py-2 font-medium">Account</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Investigations</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {users.map((account) => (
                <tr key={account.id} className="pv-transition hover:bg-hover">
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2">
                      <Avatar name={account.username} />
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{displayName(account)}</span>
                        <span className="block truncate text-xs text-ink3">
                          {account.username} · {account.email}
                        </span>
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <RoleBadge role={account.role} />
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {account.is_active ? (
                      <span className="text-[13px] text-success-ink">Active</span>
                    ) : (
                      <span className="text-[13px] text-ink3">Deactivated</span>
                    )}
                  </td>
                  <td className="max-w-xs px-3 py-2 text-[13px] text-ink2">
                    {account.investigations.length === 0 ? (
                      <span className="text-ink3">None</span>
                    ) : (
                      account.investigations.map((inv) => inv.case_number).join(", ")
                    )}
                  </td>
                  <td className="px-3 py-2 text-[13px] whitespace-nowrap text-ink3">
                    {formatDate(account.created_at)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {account.id !== user?.id && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void toggleActive(account)}
                      >
                        {account.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="flex items-start gap-1.5 text-xs text-ink3">
        <ShieldAlert size={13} className="mt-0.5 shrink-0" />
        Deactivation blocks sign-in immediately. Your own account and the last active admin are
        protected from deactivation.
      </p>

      <CreateUserDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(created) => {
          setUsers((current) => (current ? [...current, created] : [created]));
          setCreating(false);
        }}
      />
    </div>
  );
}

function CreateUserDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (user: AdminUser) => void;
}) {
  const { notify } = useToast();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("investigator");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (username.trim().length < 3 || !email.trim() || password.length < 8) {
      setError("Username (3+ chars), a valid email, and a password (8+ chars) are required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await api.adminCreateUser({
        username: username.trim(),
        email: email.trim(),
        full_name: fullName.trim() || undefined,
        password,
        role,
      });
      notify("success", `Account ${username.trim()} created.`);
      const roster = await api.adminListUsers();
      const created = roster.find((u) => u.username === username.trim());
      if (created) onCreated(created);
      else onClose();
    } catch (err) {
      setError(actionErrorMessage(err, "Could not create the account."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="New user" description="Accounts sign in with username or email.">
      <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Username" htmlFor="new-username">
            <Input id="new-username" value={username} onChange={(e) => setUsername(e.target.value)} maxLength={64} autoFocus />
          </Field>
          <Field label="Full name" htmlFor="new-fullname">
            <Input id="new-fullname" value={fullName} onChange={(e) => setFullName(e.target.value)} maxLength={255} />
          </Field>
        </div>
        <Field label="Email" htmlFor="new-email">
          <Input id="new-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={255} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Password" htmlFor="new-password">
            <Input id="new-password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Role" htmlFor="new-role">
            <Select id="new-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {error && (
          <p role="alert" className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" loading={busy}>
            Create account
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
