// Authentication state: current user, token storage, login/logout.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import type { User } from "../api/client";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  register: (payload: { username: string; email: string; full_name: string; password: string }) => Promise<void>;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (!localStorage.getItem("provena_token")) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        localStorage.removeItem("provena_token");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (usernameOrEmail: string, password: string) => {
    const result = await api.login(usernameOrEmail, password);
    localStorage.setItem("provena_token", result.access_token);
    setUser(result.user);
  }, []);

  const register = useCallback(async (payload: { username: string; email: string; full_name: string; password: string }) => {
    const result = await api.register(payload);
    localStorage.setItem("provena_token", result.access_token);
    setUser(result.user);
  }, []);

  const refresh = useCallback(async () => {
    setUser(await api.me());
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Token may already be invalid; logout still proceeds locally.
    }
    localStorage.removeItem("provena_token");
    setUser(null);
  }, []);

  // A 401 from any non-login call means the session expired elsewhere.
  useEffect(() => {
    const onUnauthorized = () => {
      localStorage.removeItem("provena_token");
      setUser(null);
    };
    window.addEventListener("provena:unauthorized", onUnauthorized);
    return () => window.removeEventListener("provena:unauthorized", onUnauthorized);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used inside AuthProvider.");
  return state;
}
