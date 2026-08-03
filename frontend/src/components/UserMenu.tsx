import { useSyncExternalStore } from "react";
import { LogIn, LogOut, Moon, Sun, User } from "lucide-react";

import { Button } from "@/components/ui/button";
import { authStore } from "@/services/authStore";

export function UserMenu() {
  const user = useSyncExternalStore(authStore.subscribe, authStore.get, () => null);
  const cognitoUrl = authStore.cognitoLoginUrl();

  if (!user) {
    return (
      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => authStore.loginLocal()}
          aria-label="Sign in locally"
        >
          <User className="h-4 w-4 mr-1" />
          Local
        </Button>
        {cognitoUrl ? (
          <Button type="button" variant="outline" size="sm" asChild>
            <a href={cognitoUrl} aria-label="Sign in with Cognito">
              <LogIn className="h-4 w-4 mr-1" />
              Cognito
            </a>
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <User className="h-4 w-4" />
      <span className="hidden sm:inline max-w-[120px] truncate">{user.sub}</span>
      <Button type="button" variant="ghost" size="icon" aria-label="Sign out" onClick={() => authStore.clear()}>
        <LogOut className="h-4 w-4" />
      </Button>
    </div>
  );
}

export function ThemeToggle({ theme, toggle }: { theme: "dark" | "light"; toggle: () => void }) {
  return (
    <Button type="button" variant="ghost" size="icon" onClick={toggle} title="Toggle theme" aria-label="Toggle theme">
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
