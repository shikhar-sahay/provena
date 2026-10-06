// Toast notifications: success and error feedback for user actions.

import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";

interface Toast {
  id: number;
  tone: "success" | "error";
  message: string;
}

const ToastContext = createContext<{
  notify: (tone: "success" | "error", message: string) => void;
} | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider.");
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const notify = useCallback((tone: "success" | "error", message: string) => {
    const id = nextId.current++;
    setToasts((current) => [...current.slice(-3), { id, tone, message }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pv-animate-toast pointer-events-auto flex items-start gap-2.5 rounded-md border border-line bg-raised px-3.5 py-2.5 shadow-(--shadow)"
          >
            {toast.tone === "success" ? (
              <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-success-ink" />
            ) : (
              <AlertCircle size={16} className="mt-0.5 shrink-0 text-danger-ink" />
            )}
            <p className="flex-1 text-sm text-ink">{toast.message}</p>
            <button
              aria-label="Dismiss notification"
              onClick={() => dismiss(toast.id)}
              className="pv-transition shrink-0 cursor-pointer rounded text-ink3 hover:text-ink"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
