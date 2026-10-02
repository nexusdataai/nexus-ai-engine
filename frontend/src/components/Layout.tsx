import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Menu, PanelLeft } from "lucide-react";
import { useLocation } from "react-router-dom";

import { Sidebar } from "@/components/Sidebar";
import { SidebarChromeProvider, useSidebarChrome } from "@/components/SidebarChrome";
import { InactivityGuard } from "@/components/InactivityGuard";
import { ThemeToggle, UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";
import { api } from "@/services/api";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/journeys": "Journeys",
  "/executions": "Executions",
  "/queue": "Queue",
  "/workers": "Workers",
  "/schedules": "Schedules",
  "/settings": "Settings",
  "/tools": "Tools Catalog",
  "/operations": "Operations",
};

function resolveTitle(pathname: string): string {
  if (pathname.startsWith("/executions/stage/")) return "Stage Job";
  if (pathname.startsWith("/journeys/") && pathname.endsWith("/studio")) return "DSL Studio";
  if (pathname.startsWith("/journeys/")) return "Journey Detail";
  if (pathname.startsWith("/executions/")) return "Execution Detail";
  return TITLES[pathname] ?? "Journey Studio";
}

function LayoutInner({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { setMobileOpen, mini, setMini } = useSidebarChrome();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: () => api.getSettings() });
  const title = resolveTitle(loc.pathname);

  return (
    <div className="min-h-screen h-screen flex overflow-hidden bg-background text-foreground">
      <InactivityGuard />
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <header className="flex items-center justify-between px-3 sm:px-5 h-12 shrink-0 border-b border-border bg-card">
          <div className="flex items-center gap-2 min-w-0">
            {mini ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="hidden md:inline-flex shrink-0"
                aria-label="Expand sidebar"
                onClick={() => setMini(false)}
              >
                <PanelLeft className="h-4 w-4" />
              </Button>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden shrink-0"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="h-4 w-4" />
            </Button>
            <h1 className="text-[15px] font-semibold truncate">{title}</h1>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <ThemeToggle theme={theme} toggle={toggleTheme} />
            <UserMenu />
            <span className="hidden sm:inline text-xs text-muted-foreground pl-1">v{data?.version?.version ?? "…"}</span>
          </div>
        </header>
        <main id="main-content" className="flex-1 overflow-auto relative p-4" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <SidebarChromeProvider>
      <LayoutInner>{children}</LayoutInner>
    </SidebarChromeProvider>
  );
}

export default Layout;
