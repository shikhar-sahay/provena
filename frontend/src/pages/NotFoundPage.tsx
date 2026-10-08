import { ArrowLeft, Home, ScanSearch } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { BrandLockup } from "../components/Brand";
import { ProvenanceMotif } from "../components/ProvenanceMotif";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canvas px-5 py-12 text-ink">
      <ProvenanceMotif className="pointer-events-none absolute inset-0 h-full w-full text-ink opacity-45" />
      <section className="pv-animate-rise relative w-full max-w-lg rounded-xl border border-line bg-surface/95 p-7 text-center shadow-(--shadow) backdrop-blur-sm sm:p-10">
        <div className="flex justify-center">
          <BrandLockup height={28} />
        </div>
        <div className="mx-auto mt-8 flex h-12 w-12 items-center justify-center rounded-xl border border-line bg-canvas text-ink2">
          <ScanSearch size={22} strokeWidth={1.6} />
        </div>
        <p className="mt-6 font-mono text-xs font-semibold tracking-[0.18em] text-ink3 uppercase">
          Error 404
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Page not found</h1>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-ink2">
          The requested location does not exist or may have moved. No investigation data was changed.
        </p>
        <div className="mt-7 flex flex-col-reverse justify-center gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="pv-transition inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-md border border-line bg-surface px-4 text-sm font-medium hover:border-linestrong hover:bg-hover"
          >
            <ArrowLeft size={15} />
            Go back
          </button>
          <Link
            to="/"
            className="pv-transition inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primaryink hover:bg-primaryhover"
          >
            <Home size={15} />
            Return home
          </Link>
        </div>
      </section>
    </main>
  );
}
