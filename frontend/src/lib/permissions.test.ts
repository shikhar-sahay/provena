import { expect, it } from 'vitest';
import { canProduceAnalysis, canProduceFindings } from './permissions';
import type { Role } from '../api/client';
const cases: [Role | undefined, boolean, boolean, boolean, boolean][] = [
  ['investigator', false, false, false, false], ['investigator', true, false, true, true],
  ['forensic_analyst', false, false, true, true], ['evidence_custodian', false, false, false, false],
  ['evidence_custodian', true, false, false, true], ['admin', true, false, true, true],
  ['forensic_analyst', false, true, false, false], ['investigator', true, true, false, false],
  [undefined, false, false, false, false],
];
for (const [role, manager, archived, analysis, findings] of cases) {
  it(`analysis capability: ${role}, manager=${manager}, archived=${archived}`, () => {
    expect(canProduceAnalysis(role, manager, archived)).toBe(analysis);
    expect(canProduceFindings(role, manager, archived)).toBe(findings);
  });
}
