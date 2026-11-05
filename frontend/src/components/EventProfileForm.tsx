import { useState } from "react";
import type { EventProfileConfig } from "../api/client";
import { Button } from "./Button";
import { Field, Input, Select } from "./Field";

export function EventProfileForm({ save, busy }: { save: (name: string, config: EventProfileConfig) => Promise<void>; busy: boolean }) {
  const [name, setName] = useState("");
  const [adapter, setAdapter] = useState<EventProfileConfig["adapter"]>("linux_auth");
  const [format, setFormat] = useState<EventProfileConfig["format"]>("syslog");
  const [encoding, setEncoding] = useState<EventProfileConfig["encoding"]>("utf-8");
  const [host, setHost] = useState("");
  const [zone, setZone] = useState("");
  const [year, setYear] = useState("");
  const [convention, setConvention] = useState<EventProfileConfig["timestamp_convention"]>("source");
  return <form className="space-y-3 rounded-md border border-line p-4" onSubmit={(e) => {
    e.preventDefault();
    void save(name, { adapter, format, encoding, source_host: host.trim() || null,
      timezone: zone.trim() || null, year: adapter === "linux_auth" && year ? Number(year) : null,
      timestamp_convention: convention });
  }}>
    <h2 className="text-sm font-semibold">New immutable source profile</h2>
    <p className="text-xs text-ink3">Configuration changes create a new interpretation. Leave unknown year and timezone blank. Native EVTX, XML and positional Properties exports are unsupported.</p>
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label="Profile name" htmlFor="event-profile-name"><Input id="event-profile-name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Adapter" htmlFor="event-adapter"><Select id="event-adapter" value={adapter} onChange={(e) => {
        const next = e.target.value as EventProfileConfig["adapter"]; setAdapter(next);
        setFormat(next === "linux_auth" ? "syslog" : "jsonl"); setConvention("source");
      }}><option value="linux_auth">Linux authentication</option><option value="windows_security">Windows Security</option><option value="sysmon">Sysmon context</option></Select></Field>
      <Field label="Source format" htmlFor="event-format"><Select id="event-format" value={format} onChange={(e) => setFormat(e.target.value as EventProfileConfig["format"])}>
        {adapter === "linux_auth" ? <option value="syslog">Syslog / auth.log / secure</option> : <><option value="jsonl">JSONL</option><option value="json">JSON</option><option value="csv">CSV</option></>}
      </Select></Field>
      <Field label="Encoding" htmlFor="event-encoding"><Select id="event-encoding" value={encoding} onChange={(e) => setEncoding(e.target.value as EventProfileConfig["encoding"])}><option value="utf-8">UTF-8</option><option value="utf-8-sig">UTF-8 with BOM</option><option value="latin-1">Latin-1 (explicit assumption)</option></Select></Field>
      <Field label="Source host fallback" htmlFor="event-host"><Input id="event-host" maxLength={256} value={host} onChange={(e) => setHost(e.target.value)} /></Field>
      <Field label="Timezone assumption (optional)" htmlFor="event-zone"><Input id="event-zone" placeholder="+05:30 or America/New_York" maxLength={64} value={zone} onChange={(e) => setZone(e.target.value)} /></Field>
      {adapter === "linux_auth" && <Field label="Year for yearless syslog (optional)" htmlFor="event-year"><Input id="event-year" type="number" min={1970} max={2100} value={year} onChange={(e) => setYear(e.target.value)} /></Field>}
      <Field label="Timestamp convention" htmlFor="event-time-convention"><Select id="event-time-convention" value={convention} onChange={(e) => setConvention(e.target.value as EventProfileConfig["timestamp_convention"])}><option value="source">Preserve source conventions</option><option value="iso8601">ISO timestamps only</option>{adapter === "linux_auth" && <option value="syslog">Yearless syslog only</option>}</Select></Field>
    </div>
    <Button type="submit" loading={busy}>Save source profile</Button>
  </form>;
}
