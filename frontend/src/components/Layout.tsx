import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import { useLocation } from "react-router-dom";

import { Sidebar } from "@/components/Sidebar";
import { SidebarChromeProvider, useSidebarChrome } from "@/components/SidebarChrome";
import { ThemeToggle, UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";
import { fetchVersion } from "@/services/api";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/journeys": "Journeys",
  "/executions": "Executions",
  "/schedules": "Schedules",
  "/tools": "Tools Catalog",
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
  const { setMobileOpen } = useSidebarChrome();
  const { data } = useQuery({ queryKey: ["version"], queryFn: fetchVersion });
  const title = resolveTitle(loc.pathname);

  return (
    <div className="min-h-screen h-screen flex overflow-hidden bg-background text-foreground">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <header className="flex items-center justify-between px-3 sm:px-5 h-12 shrink-0 border-b border-border bg-card">
          <div className="flex items-center gap-2 min-w-0">
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
            <span className="hidden sm:inline text-xs text-muted-foreground pl-1">v{data?.version ?? "…"}</span>
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
