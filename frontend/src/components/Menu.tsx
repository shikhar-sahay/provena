// Minimal accessible dropdown menu: Escape closes, outside click closes,
// arrow keys move between items.

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export interface MenuItem {
  key: string;
  label: string;
  hint?: string;
  danger?: boolean;
  icon?: ReactNode;
  onSelect: () => void;
}

export function Menu({
  trigger,
  items,
  label,
  align = "right",
  header,
}: {
  trigger: ReactNode;
  items: MenuItem[];
  label: string;
  align?: "left" | "right";
  header?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open ]);

  return (
    <div ref={rootRef} className="relative">
      <div onClick={() => setOpen((v) => !v)}>{trigger}</div>
      {open && (
        <div
          role="menu"
          aria-label={label}
          className={`pv-animate-fade absolute z-50 mt-1 min-w-48 overflow-hidden rounded-md border border-line bg-surface py-1 shadow-(--shadow) ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          {header && <div className="border-b border-line px-3 py-2">{header}</div>}
          {items.map((item) => (
            <button
              key={item.key}
              role="menuitem"
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={`pv-transition flex w-full cursor-pointer items-center gap-2 px-3 py-1.5 text-left text-sm ${
                item.danger ? "text-danger-ink hover:bg-danger-bg" : "text-ink hover:bg-hover"
              }`}
            >
              {item.icon}
              <span className="flex-1">{item.label}</span>
              {item.hint && <span className="text-xs text-ink3">{item.hint}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
