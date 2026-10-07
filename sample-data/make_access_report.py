"""Deterministic generator for the synthetic demo PDF (stdlib only, no deps).

Writes sample-data/employee-access-report.pdf: a small machine-readable,
entirely fictional access report for the data-exfiltration scenario. The
generator computes all PDF cross-reference offsets programmatically, so the
output is byte-deterministic for identical input. Re-run to regenerate:

    python sample-data/make_access_report.py

All people, hosts, addresses, and domains are invented. IPs use reserved
documentation ranges (RFC 5737); domains use example.com / example.net.
"""

from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "employee-access-report.pdf"

PAGES = [
    [
        "PROVENA DEMO DOCUMENT - ENTIRELY FICTIONAL",
        "Employee Access Review - Q1 2026 (synthetic)",
        "",
        "This synthetic report summarizes fictional account activity for",
        "walkthrough purposes. No real people, systems, or events appear.",
        "",
        "Account: m.okafor (fictional employee)",
        "Workstation: ws-114 (fictional asset)",
        "Reviewer contact: a.lindqvist@example.com",
        "",
        "Observed sign-ins for m.okafor:",
        "- 2026-01-12 08:02:11 from 192.0.2.14 (expected office range)",
        "- 2026-01-13 02:14:55 from 192.0.2.90 (unfamiliar address)",
    ],
    [
        "Removable media (fictional endpoint records):",
        "- 2026-01-13 02:16:10 USB device KINGSTON-USB serial",
        "  4C5300FICTIONAL01 inserted on ws-114",
        "- 2026-01-13 02:47:02 device removed from ws-114",
        "",
        "Files referenced by the fictional review:",
        "- vendor-pricing-2026.xlsx (restricted share)",
        "- customer-list-2026.csv (restricted share)",
        "",
        "Network notes (fictional): outbound upload of 193402 bytes",
        "to 203.0.113.44, and archive-mirror.example.net lookup",
        "from ws-114 on 2026-01-13 02:23:18.",
        "",
        "End of synthetic report. No investigative conclusions intended.",
    ],
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_text_pdf(pages: list[list[str]]) -> bytes:
    """Build a minimal one-font PDF from lines of Latin-1 text. Deterministic."""
    objects: list[bytes] = []
    for index, lines in enumerate(pages):
        ops = ["BT /F1 11 Tf 50 770 Td 13 TL"]
        for line in lines:
            ops.append(f"({_escape(line)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    # Object numbering: 1 catalog, 2 pages, 3 font, then content+page pairs.
    # Content object i is (4 + i*2), page object i is (5 + i*2).
    n_pages = len(pages)
    kids = " ".join(f"{5 + i * 2} 0 R" for i in range(n_pages))
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i in range(n_pages):
        bodies.append(objects[i])
        bodies.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {4 + i * 2} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
            ).encode()
        )
    out = [b"%PDF-1.4\n"]
    offsets = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(sum(len(part) for part in out))
        out.append(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    startxref = sum(len(part) for part in out)
    out.append(f"xref\n0 {len(bodies) + 1}\n".encode())
    out.append(b"0000000000 65535 f \n")
    for offset in offsets:
        out.append(f"{offset:010d} 00000 n \n".encode())
    out.append(
        f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode()
    )
    return b"".join(out)


def main() -> None:
    OUTPUT.write_bytes(build_text_pdf(PAGES))
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
