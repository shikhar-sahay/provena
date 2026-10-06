// Global investigation search: filters accessible investigations by title or
// case number, navigates on selection. Enter jumps to the filtered list view.

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { api } from "../api/client";
import type { Investigation } from "../api/client";

export function GlobalSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Investigation[] | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || items !== null) return;
    let cancelled = false;
    api
      .listInvestigations()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, items]);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open ]);

  const term = query.trim().toLowerCase();
  const matches = (items ?? [])
    .filter(
      (inv) =>
        term.length === 0 ||
        inv.title.toLowerCase().includes(term) ||
        inv.case_number.toLowerCase().includes(term),
    )
    .slice(0, 6);

  function goToList() {
    setOpen(false);
    navigate(term ? `/investigations?q=${encodeURIComponent(query.trim())}` : "/investigations");
  }

  return (
    <div ref={rootRef} className="relative w-44 shrink-0 sm:w-60 md:w-64">
      <Search
        size={14}
        className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink3"
      />
      <input
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-label="Search investigations"
        aria-controls="global-search-results"
        placeholder="Search investigations…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter") goToList();
          if (e.key === "Escape") setOpen(false);
        }}
        className="pv-transition h-8 w-full rounded-md border border-line bg-surface pr-8 pl-8 text-sm text-ink placeholder:text-ink3 hover:border-linestrong focus:border-accent focus:outline-none"
      />
      <kbd className="pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 rounded border border-line px-1 text-[11px] text-ink3 sm:block">
        /
      </kbd>
      {open && query.trim().length > 0 && (
        <div
          id="global-search-results"
          role="listbox"
          className="pv-animate-fade absolute right-0 left-0 z-50 mt-1 overflow-hidden rounded-md border border-line bg-surface shadow-(--shadow)"
        >
          {matches.length === 0 ? (
            <p className="px-3 py-2 text-sm text-ink3">
              {items === null ? "Searching…" : "No matching investigations."}
            </p>
          ) : (
            matches.map((inv) => (
              <button
                key={inv.id}
                role="option"
                aria-selected="false"
                onClick={() => {
                  setOpen(false);
                  setQuery("");
                  navigate(`/investigations/${inv.id}`);
                }}
                className="pv-transition flex w-full cursor-pointer flex-col px-3 py-2 text-left hover:bg-hover"
              >
                <span className="truncate text-sm font-medium">{inv.title}</span>
                <span className="font-mono text-xs text-ink3">{inv.case_number}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
