# Synthetic M4 authentication investigation

All identities, hosts and activity are fictional. IPs use reserved documentation
ranges. No credentials or real incident data are included. Patterns support
investigation hypotheses, not assertions of malicious intent.

| File | Profile | Content |
| --- | --- | --- |
| `linux-auth.txt` | Linux authentication, syslog, UTF-8; leave year and timezone unset | Repeated SSH failures, later success, multi-account failures, mixed-outcome burst, IPv6, yearless and missing time, duplicate and unsupported records |
| `windows-security.jsonl` | Windows Security, JSONL, UTF-8 | Three explicit 4740 lockouts and two isolated 4625 failures |
| `sysmon-context.jsonl` | Sysmon, JSONL, UTF-8 | Ordinary process creation and network context, never authentication detections |

## Reproduce locally

1. Install and migrate the local development environment using the project README.
   Use a synthetic local account with investigation management permissions.
2. Create an investigation and register the three files as evidence. Verify each
   item's integrity independently before ingestion.
3. In Security Events, create the three profiles above. Ingest each evidence item
   with its corresponding profile. Linux coverage is explicitly partial because
   two lines are unsupported; time uncertainty is retained for six recognized records.
4. Open Authentication. Expand source selection and choose exactly these three
   ingestion runs. Save a named event set. It contains 51 recognized event occurrences.
5. Run default detections. Expect five proposals: repeated failures, password spray,
   success after failures, explicit lockout concentration and mixed activity burst.
   The duplicate observation counts once; six uncertain-time records and two Sysmon
   context records do not participate in authentication time-window evaluation.
6. Open the spray proposal. Review its five triggering events and NAT/shared-source
   limitations. Explore support, then pivot to `192.0.2.20` to see all six related
   source-IP events. Inspect a
   source locator and evidence digest, then return to the finding.
7. Switch to the unknown-time lane to inspect six records that cannot establish
   cross-source chronology. Do not assign a current year or UTC implicitly.
8. Accept the spray proposal with a review note; reject the activity-burst proposal
   as synthetic benign service activity. Save an investigator annotation.
9. Generate a reviewed report from this workbench. Its selected input-set identity,
   parameters, coverage, accepted source-backed conclusion and separate decision
   inventory are frozen. Pending/rejected proposals are not validated conclusions.
10. Reingest the same three evidence/profile pairs. Create a selection using their
    new run IDs. It resolves to the same semantic set and existing finding identities.
    Rerun detections and confirm the accepted/rejected decisions remain intact.

Automated reproduction from `backend/`:

```sh
python -m pytest tests/test_m4_demo.py -q
```

The test uses disposable database/storage fixtures and executes upload, verification,
ingestion, selection, all five families, timeline/IP pivot, review, annotation,
reporting and identical reruns through actual APIs. It never touches production.
