import { useEffect, useState } from "react";
import { Check, Clipboard, Cpu, UserPlus } from "lucide-react";
import { api } from "../api/client";
import type { AiProviderHealth, Role, WorkspaceInvite, WorkspaceMember } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { RoleBadge } from "../components/Badge";
import { Avatar } from "../components/Brand";
import { Button } from "../components/Button";
import { Field, Select } from "../components/Field";
import { ErrorState, PageHeader, TableSkeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { actionErrorMessage } from "../lib/errors";
import { displayName, formatDate } from "../lib/format";

const ASSIGNABLE: Role[] = ["admin", "investigator", "forensic_analyst", "evidence_custodian"];

export default function WorkspacePage() {
  const { user, refresh } = useAuth();
  const { notify } = useToast();
  const [members, setMembers] = useState<WorkspaceMember[] | null>(null);
  const [health, setHealth] = useState<AiProviderHealth | null>(null);
  const [inviteRole, setInviteRole] = useState<Role>("investigator");
  const [invite, setInvite] = useState<WorkspaceInvite | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [roster, provider] = await Promise.all([api.listWorkspaceMembers(), api.aiProviderHealth()]);
      setMembers(roster);
      setHealth(provider);
      setError(null);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load workspace settings."));
    }
  }

  useEffect(() => { void load(); }, []);

  async function createInvite() {
    try {
      setInvite(await api.createWorkspaceInvite(inviteRole));
      setCopied(false);
      notify("success", "Invite code generated.");
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not create an invite."));
    }
  }

  async function changeRole(member: WorkspaceMember, role: Role) {
    try {
      const updated = await api.updateWorkspaceMemberRole(member.id, role);
      setMembers((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? null);
      if (member.id === user?.id) await refresh();
      notify("success", `${member.username}'s role was updated.`);
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not update the role."));
    }
  }

  async function copyInvite() {
    if (!invite?.code) return;
    await navigator.clipboard.writeText(invite.code);
    setCopied(true);
  }

  if (error) return <ErrorState body={error} onRetry={() => void load()} />;
  return (
    <div className="space-y-6">
      <PageHeader title="Workspace" description="Manage workspace members, role assignments, invitation codes, and local narrative availability." />

      <section className="rounded-md border border-line bg-surface p-4">
        <div className="flex items-start gap-3">
          <Cpu size={18} className="mt-0.5 text-ink2" />
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">Local narrative provider</h2>
            <p className="mt-1 text-sm text-ink2">{health?.detail ?? "Checking provider status..."}</p>
            {health && <p className="mt-1 font-mono text-xs text-ink3">{health.provider}{health.model ? ` / ${health.model}` : ""} · {health.available ? "available" : "fallback active"}</p>}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h2 className="text-sm font-semibold">Members</h2><p className="mt-0.5 text-sm text-ink2">Investigation teams can only be selected from this roster.</p></div>
          <div className="flex items-end gap-2">
            <Field label="Invite role" htmlFor="invite-role"><Select id="invite-role" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as Role)}>{ASSIGNABLE.filter((role) => role !== "admin").map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}</Select></Field>
            <Button variant="primary" size="sm" icon={<UserPlus size={14} />} onClick={() => void createInvite()}>Generate invite</Button>
          </div>
        </div>
        {invite?.code && <div className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-hover px-3 py-2"><span className="font-mono text-sm">{invite.code}</span><Button variant="secondary" size="sm" icon={copied ? <Check size={14} /> : <Clipboard size={14} />} onClick={() => void copyInvite()}>{copied ? "Copied" : "Copy"}</Button><span className="text-xs text-ink3">Expires {invite.expires_at ? formatDate(invite.expires_at) : "never"}. The full code is shown once.</span></div>}
        {members === null ? <TableSkeleton rows={4} /> : (
          <div className="overflow-x-auto rounded-md border border-line"><table className="w-full min-w-[40rem] text-left text-sm"><thead><tr className="border-b border-line bg-surface text-xs text-ink2"><th className="px-3 py-2 font-medium">Member</th><th className="px-3 py-2 font-medium">Role</th><th className="px-3 py-2 font-medium">Joined</th></tr></thead><tbody className="divide-y divide-line bg-surface">{members.map((member) => <tr key={member.id}><td className="px-3 py-2"><span className="flex items-center gap-2"><Avatar name={member.username} /><span><span className="block font-medium">{displayName(member)}</span><span className="block text-xs text-ink3">{member.username} · {member.email}</span></span></span></td><td className="px-3 py-2">{member.id === user?.id ? <RoleBadge role={member.role} /> : <Select aria-label={`Role for ${member.username}`} value={member.role} onChange={(e) => void changeRole(member, e.target.value as Role)}>{ASSIGNABLE.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}</Select>}</td><td className="px-3 py-2 text-xs text-ink3">{formatDate(member.joined_at)}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </div>
  );
}
