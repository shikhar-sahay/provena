// Provena brand: theme-aware mark and lockup. The logo stays monochrome;
// semantic colors never recolor it. Source pack lives in public/brand/.

import { useTheme } from "../theme/ThemeContext";

export function BrandMark({ size = 22 }: { size?: number }) {
  const { dark } = useTheme();
  return (
    <img
      src={dark ? "/brand/mark-dark.svg" : "/brand/mark-light.svg"}
      alt="Provena"
      width={size}
      height={size}
      draggable={false}
    />
  );
}

export function BrandLockup({ height = 24 }: { height?: number }) {
  const { dark } = useTheme();
  return (
    <img
      src={dark ? "/brand/logo-dark.svg" : "/brand/logo-light.svg"}
      alt="Provena"
      style={{ height }}
      draggable={false}
    />
  );
}

export function Avatar({ name }: { name: string }) {
  const initials = name
    .split(/[\s_@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <span
      aria-hidden="true"
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-line bg-surface text-xs font-semibold text-ink shadow-xs"
    >
      {initials || "?"}
    </span>
  );
}
