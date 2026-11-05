# M3 synthetic authentication investigation

All accounts, hosts, process paths and activity are invented. IP addresses are
reserved documentation ranges (RFC 5737 and 2001:db8::/32). No real credentials,
people or investigative records are included. Repeated lines represent distinct
source occurrences, not independently corroborated activity.

Files:

- `linux-auth.log`: SSH success/failure, publickey, invalid user, PAM failure and
  session records, account denial, IPv4/IPv6, yearless/missing time, duplicate and
  unsupported records. Profile: Linux authentication / syslog / UTF-8.
- `windows-security.jsonl`: Security 4624/4625/4634/4648/4740, conflicting and
  unsupported providers/events, and a malformed JSONL record. Profile: Windows
  Security / JSONL / UTF-8.
- `sysmon.csv`: process creation and network connection with named UtcTime,
  plus unsupported ID 99. Profile: Sysmon / CSV / UTF-8.

On a local disposable Provena instance:

1. Register/login, create a workspace and investigation, then open Evidence.
2. Upload these three files and independently verify each SHA-256.
3. Open Security Events and configure the three profiles listed above. Leave
   year/timezone blank initially, preserving source uncertainty.
4. Select each evidence/profile pair and ingest it. Open the coverage summaries.
5. Expect 11 Linux, 5 Windows Security and 2 Sysmon events (18 total). These are
   partial sets: Linux has 2 unsupported records; Windows 2 unsupported and 1
   rejected record; Sysmon 1 unsupported record.
6. Filter category `authentication`, outcome `failure`: expect 8 events. Inspect
   account/host/IP and follow an event to its source evidence and locator.
7. Reingest each identical evidence/profile pair: expect zero new events and
   unchanged stable identities. Separate run memberships record each retry.
8. Create another Linux profile with year 2026 and timezone `+00:00`. This is an
   explicit interpretation assumption; it creates another historical event
   interpretation. Filter Profile ID to compare without mixing event sets.

Automated equivalent, using in-memory SQLite and temporary synthetic storage:

```text
cd backend
python -m pytest tests/test_m3_demo.py -q -s
```

Do not run the manual procedure against production. No M4 detections or incident
sequence conclusions are implied by this dataset.
