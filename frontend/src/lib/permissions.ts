import type { Role } from '../api/client';

// Capability guidance within an already authorized case, matching backend initiation.
// This does not replace workspace/case authorization on the API.
export function canProduceAnalysis(role: Role | undefined, canManage: boolean, archivedLocked: boolean): boolean {
  return !archivedLocked && (role === 'admin' || role === 'forensic_analyst' || (role === 'investigator' && canManage));
}

// Finding production intentionally retains the broader inherited case-manager policy.
export function canProduceFindings(role: Role | undefined, canManage: boolean, archivedLocked: boolean): boolean {
  return !!role && !archivedLocked && (canManage || role === 'admin' || role === 'forensic_analyst');
}
