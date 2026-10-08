// Global search component: connects to server-side /api/search with debouncing,
// grouped category results, keyboard navigation, and '/' shortcut.

import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Cpu,
  Database,
  FolderKanban,
  Loader2,
  Search,
  ShieldAlert,
} from "lucide-react";
import { api } from "../api/client";
import type { SearchResultItem } from "../api/client";

const CATEGORY_CONFIG: Record<
  SearchResultItem["category"],
  { label: string; icon: typeof FolderKanban }
> = {
  investigation: { label: "Investigations", icon: FolderKanban },
  evidence: { label: "Evidence", icon: Database },
  finding: { label: "Findings", icon: ShieldAlert },
  artifact: { label: "Artifacts", icon: Cpu },
};

const CATEGORY_ORDER: SearchResultItem["category"][] = [
  "investigation",
  "evidence",
  "finding",
  "artifact",
];

export function GlobalSearch() {
  const navigate = useNavigate();
  const searchId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);

  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Close dropdown on click outside
  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  // Global '/' keyboard shortcut to focus search input
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      inputRef.current?.focus();
      setOpen(true);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  // Debounced search query
  useEffect(() => {
    const term = query.trim();
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (term.length < 2) {
      setResults([]);
      setLoading(false);
      setActiveIndex(-1);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const response = await api.globalSearch(term);
        setResults(response.results);
        setActiveIndex(response.results.length > 0 ? 0 : -1);
      } catch {
        setResults([]);
        setActiveIndex(-1);
      } finally {
        setLoading(false);
      }
    }, 280);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query]);

  // Flattened list respecting category order for arrow navigation
  const groupedResults = CATEGORY_ORDER.reduce<
    { category: SearchResultItem["category"]; items: SearchResultItem[] }[]
  >((acc, cat) => {
    const items = results.filter((r) => r.category === cat);
    if (items.length > 0) acc.push({ category: cat, items });
    return acc;
  }, []);

  const flatOrderedResults = groupedResults.flatMap((g) => g.items);

  function handleSelect(item: SearchResultItem) {
    setOpen(false);
    setQuery("");
    navigate(item.url);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (flatOrderedResults.length === 0) return;
      setActiveIndex((prev) => (prev + 1) % flatOrderedResults.length);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (flatOrderedResults.length === 0) return;
      setActiveIndex((prev) =>
        prev <= 0 ? flatOrderedResults.length - 1 : prev - 1,
      );
      return;
    }

    if (event.key === "Enter") {
      if (
        open &&
        activeIndex >= 0 &&
        activeIndex < flatOrderedResults.length
      ) {
        event.preventDefault();
        handleSelect(flatOrderedResults[activeIndex]);
      } else if (open && flatOrderedResults.length > 0) {
        event.preventDefault();
        handleSelect(flatOrderedResults[0]);
      }
    }
  }

  return (
    <div ref={rootRef} className="relative w-28 min-w-0 shrink sm:w-64 md:w-72">
      <Search
        size={14}
        className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink3"
      />
      <input
        ref={inputRef}
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-label="Search investigations, evidence, findings, and artifacts"
        aria-controls={`${searchId}-results`}
        placeholder="Search everything..."
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        className="pv-transition h-8 w-full rounded-md border border-line bg-surface pr-8 pl-8 text-sm text-ink placeholder:text-ink3 hover:border-linestrong focus:border-accent focus:outline-none"
      />
      {loading ? (
        <Loader2
          size={13}
          className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 animate-spin text-ink3"
        />
      ) : (
        <kbd className="pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 rounded border border-line px-1 text-[11px] text-ink3 sm:block">
          /
        </kbd>
      )}

      {open && query.trim().length >= 2 && (
        <div
          id={`${searchId}-results`}
          role="listbox"
          className="pv-animate-fade fixed right-3 left-3 z-50 mt-1 max-h-[60dvh] overflow-y-auto rounded-md border border-line bg-surface shadow-lg sm:absolute sm:right-0 sm:left-auto sm:w-96"
        >
          {loading && flatOrderedResults.length === 0 ? (
            <div className="flex items-center gap-2 px-3 py-3 text-sm text-ink3">
              <Loader2 size={14} className="animate-spin text-accent" />
              Searching across investigations...
            </div>
          ) : flatOrderedResults.length === 0 ? (
            <div className="px-3 py-3 text-sm text-ink3">
              No results found for &ldquo;{query.trim()}&rdquo;.
            </div>
          ) : (
            groupedResults.map((group) => {
              const { label, icon: CategoryIcon } =
                CATEGORY_CONFIG[group.category];
              return (
                <div key={group.category} className="border-b border-line last:border-b-0">
                  <div className="flex items-center gap-1.5 bg-surface2/60 px-3 py-1 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
                    <CategoryIcon size={12} />
                    <span>{label}</span>
                    <span className="ml-auto font-mono text-[10px]">
                      {group.items.length}
                    </span>
                  </div>
                  {group.items.map((item) => {
                    const itemGlobalIndex = flatOrderedResults.indexOf(item);
                    const isSelected = itemGlobalIndex === activeIndex;

                    return (
                      <button
                        key={`${item.category}-${item.id}`}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onMouseEnter={() => setActiveIndex(itemGlobalIndex)}
                        onClick={() => handleSelect(item)}
                        className={`pv-transition flex w-full cursor-pointer flex-col px-3 py-2 text-left ${
                          isSelected ? "bg-hover" : "hover:bg-hover"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-medium text-ink">
                            {item.title}
                          </span>
                          {item.category !== "investigation" && (
                            <span className="shrink-0 truncate text-[11px] text-ink3">
                              {item.investigation_title}
                            </span>
                          )}
                        </div>
                        <span className="truncate font-mono text-xs text-ink3">
                          {item.subtitle}
                        </span>
                      </button>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
