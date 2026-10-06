// Form primitives: labeled fields with consistent sizing and error display.

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const CONTROL =
  "pv-transition h-8 w-full rounded-md border border-line bg-surface px-2.5 text-sm text-ink placeholder:text-ink3 hover:border-linestrong focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-50";

export function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  error?: string | null;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <label
        htmlFor={htmlFor}
        className="mb-1 block text-[13px] font-medium text-ink2"
      >
        {label}
      </label>
      {children}
      {error ? (
        <p role="alert" className="mt-1 text-[13px] text-danger-ink">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1 text-[13px] text-ink3">{hint}</p>
      ) : null}
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`${CONTROL} h-auto min-h-20 py-2 leading-relaxed ${props.className ?? ""}`}
    />
  );
}
