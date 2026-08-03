/** Cognito JWT + local dev identity (spec 070). */

const STORAGE_KEY = "nexus-ai-engine-auth";

export type AuthUser = {
  sub: string;
  role: string;
  access_token: string;
  expires_at: number;
};

type Listener = () => void;

let current: AuthUser | null = load();
const listeners = new Set<Listener>();

function load(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthUser;
    if (parsed.expires_at && parsed.expires_at < Date.now()) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function persist(user: AuthUser | null) {
  current = user;
  if (user) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  else sessionStorage.removeItem(STORAGE_KEY);
  listeners.forEach((l) => l());
}

export const authStore = {
  get(): AuthUser | null {
    return current;
  },
  set(user: AuthUser) {
    persist(user);
  },
  clear() {
    persist(null);
  },
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  loginLocal(sub = "studio-user", role = "operator") {
    const token = (import.meta.env.VITE_DEV_TOKEN as string | undefined) || "";
    persist({
      sub,
      role,
      access_token: token,
      expires_at: Date.now() + 8 * 3600_000,
    });
  },
  cognitoLoginUrl(): string {
    const domain = import.meta.env.VITE_COGNITO_DOMAIN as string | undefined;
    const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined;
    const redirect =
      (import.meta.env.VITE_COGNITO_REDIRECT_URI as string | undefined) ??
      `${window.location.origin}/auth/callback`;
    if (!domain || !clientId) return "";
    const params = new URLSearchParams({
      client_id: clientId,
      response_type: "token",
      scope: "openid email profile",
      redirect_uri: redirect,
    });
    return `https://${domain}/login?${params.toString()}`;
  },
};
