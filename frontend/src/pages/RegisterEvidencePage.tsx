// Deep-linkable registration page: the same form as the drawer, centered.

import { Link, useParams } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { RegisterEvidenceForm } from "../components/RegisterEvidenceForm";

export default function RegisterEvidencePage() {
  const { id } = useParams<{ id: string }>();
  const invId = Number(id);

  return (
    <div className="mx-auto max-w-2xl">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-[13px] text-ink3">
        <Link to={`/investigations/${invId}/evidence`} className="hover:text-ink2 hover:underline">
          Evidence
        </Link>
        <ChevronRight size={13} aria-hidden="true" />
        <span aria-current="page">Register</span>
      </nav>
      <h1 className="mt-2 text-xl font-semibold tracking-tight">Register evidence</h1>
      <p className="mt-1 text-sm text-ink2">
        The file is stored under Provena control and a SHA-256 baseline is recorded.
      </p>
      <div className="mt-4 rounded-md border border-line bg-surface p-5">
        <RegisterEvidenceForm invId={invId} onDone={() => undefined} navigateOnSuccess />
      </div>
    </div>
  );
}
