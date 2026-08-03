import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { authStore } from "@/services/authStore";

/** Parse Cognito implicit-grant tokens from URL hash. */
export function AuthCallbackPage() {
  const nav = useNavigate();

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const token = params.get("access_token");
    const expiresIn = Number(params.get("expires_in") ?? "3600");
    if (token) {
      authStore.set({
        sub: params.get("username") ?? "cognito-user",
        role: "operator",
        access_token: token,
        expires_at: Date.now() + expiresIn * 1000,
      });
    }
    nav("/", { replace: true });
  }, [nav]);

  return <p className="text-sm text-muted-foreground">Completing sign-in…</p>;
}
