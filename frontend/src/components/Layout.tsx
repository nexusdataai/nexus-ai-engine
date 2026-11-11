import { useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { LogoMark } from "@/components/ds/Logo";
import { InactivityGuard } from "@/components/InactivityGuard";
import { Sidebar } from "@/components/Sidebar";
import { SidebarChromeProvider, useSidebarChrome } from "@/components/SidebarChrome";
import { ThemeToggle, UserMenu } from "@/components/UserMenu";
import { getBreadcrumbs, getPageTitle } from "@/config/navigation";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";

const iconBtn =
  "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/**
 * App shell: sidebar (desktop rail, mobile drawer), top bar with breadcrumbs,
 * and the scrolling content area. Every routed page renders inside this.
 */
function LayoutInner({ children }: { children: ReactNode }) {
  const loc = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { setMobileOpen } = useSidebarChrome();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: () => api.getSettings() });
  const crumbs = getBreadcrumbs(loc.pathname);
  const env = data?.version?.env;

  useEffect(() => {
    document.title = `${getPageTitle(loc.pathname)} · Nexus AI Engine`;
  }, [loc.pathname]);

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <InactivityGuard />
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-[var(--topbar-h)] shrink-0 items-center gap-3 border-b border-border bg-header px-3 sm:px-5 lg:px-8">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <button type="button" onClick={() => setMobileOpen(true)} aria-label="Open menu" className={cn(iconBtn, "md:hidden")}>
              <Icon name="menu" className="h-[18px] w-[18px]" />
            </button>
            <Link to="/" aria-label="Nexus AI Engine home" className="mr-1 md:hidden">
              <LogoMark className="h-6 w-6 [--logo-bg:var(--header)]" />
            </Link>

            <nav aria-label="Breadcrumb" className="min-w-0">
              <ol className="flex min-w-0 items-center gap-1.5 text-sm">
                {crumbs.map((c, i) => {
                  const last = i === crumbs.length - 1;
                  return (
                    <li key={`${c.label}-${i}`} className={cn("flex min-w-0 items-center gap-1.5", !last && "hidden sm:flex")}>
                      {i > 0 && <span className="hidden text-subtle-foreground sm:block" aria-hidden="true">/</span>}
                      {c.path && !last ? (
                        <Link to={c.path} className="truncate text-muted-foreground transition-colors hover:text-foreground">
                          {c.label}
                        </Link>
                      ) : (
                        <span className={cn("truncate", last ? "font-medium text-foreground" : "text-muted-foreground")} aria-current={last ? "page" : undefined}>
                          {c.label}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <span className="mr-1 hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
              {env ? <span className="rounded border border-border-strong px-1.5 py-px font-medium">{env}</span> : null}
              <span className="num font-mono">v{data?.version?.version ?? "…"}</span>
            </span>
            <ThemeToggle theme={theme} toggle={toggleTheme} />
            <div className="ml-1">
              <UserMenu />
            </div>
          </div>
        </header>

        <main id="main-content" className="scroll-thin relative min-h-0 flex-1 overflow-auto focus:outline-none" tabIndex={-1}>
          <div key={loc.pathname} className="page animate-fade-in">
            {children}
          </div>
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
