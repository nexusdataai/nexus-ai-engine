import { useSyncExternalStore } from "react";

import { Icon } from "@/components/ds/Icon";
import { Button } from "@/components/ui/button";
import { authStore } from "@/services/authStore";

const iconBtn =
  "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function UserMenu() {
  const user = useSyncExternalStore(authStore.subscribe, authStore.get, () => null);
  const cognitoUrl = authStore.cognitoLoginUrl();

  if (!user) {
    return (
      <div className="flex items-center gap-1.5">
        <Button type="button" variant="outline" size="sm" onClick={() => authStore.loginLocal()} aria-label="Sign in locally">
          <Icon name="user" />
          Local
        </Button>
        {cognitoUrl ? (
          <Button type="button" size="sm" asChild>
            <a href={cognitoUrl} aria-label="Sign in with Cognito">
              Sign in
            </a>
          </Button>
        ) : null}
      </div>
    );
  }

  const initial = (user.sub || "?").trim().charAt(0).toUpperCase();
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-xs font-medium text-primary dark:text-brand-hi" aria-hidden="true">
        {initial}
      </span>
      <span className="hidden max-w-[140px] truncate text-sm text-muted-foreground sm:inline">{user.sub}</span>
      <button type="button" className={iconBtn} aria-label="Sign out" title="Sign out" onClick={() => authStore.clear()}>
        <Icon name="logout" />
      </button>
    </div>
  );
}

export function ThemeToggle({ theme, toggle }: { theme: "dark" | "light"; toggle: () => void }) {
  return (
    <button
      type="button"
      className={iconBtn}
      onClick={toggle}
      title="Toggle theme"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      <span key={theme} className="animate-scale-in">
        <Icon name={theme === "dark" ? "sun" : "moon"} className="h-[18px] w-[18px]" />
      </span>
    </button>
  );
}
