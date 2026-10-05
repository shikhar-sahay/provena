# sample-data

Synthetic, non-sensitive demonstration data lives here. Everything in this
directory is fictional and safe to commit: all people, IP addresses, and
domains are invented (IPs use reserved documentation ranges, domains use
example.com / example.net).

Rules:

- Only commit synthetic or clearly public demo data.
- **Real investigative evidence must never be committed.**
- No personal data, no credentials, no real case material.

## Flagship scenario: suspected internal data exfiltration

The starter set describes a fictional employee (`m.okafor`, workstation
`ws-114`) whose account shows unusual signs over three days: logins from an
unfamiliar address at odd hours, USB insertions followed by copies of
restricted files, and large outbound uploads.

| File                | Content                                              |
| ------------------- | ---------------------------------------------------- |
| authentication.log  | Fictional login successes, failures, odd-hour access |
| usb_activity.log    | Fictional USB insertions, mounts, removals           |
| file_access.log     | Fictional reads and copies of restricted files       |
| network_activity.log| Fictional uploads to external destinations           |

These files are plain text so they can be registered as `log` evidence today
and fed to the planned AI extraction milestone later. Runtime uploads are
stored under `evidence-storage/` (git-ignored) and are unrelated to this
directory.
