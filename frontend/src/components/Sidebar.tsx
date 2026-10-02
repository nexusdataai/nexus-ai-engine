import { useQuery } from "@tanstack/react-query";
import { Activity, Calendar, ChevronLeft, ChevronRight, CircleHelp, LayoutDashboard, Layers, PlayCircle, Route, Settings, Users, Wrench, X } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { NexusLogo } from "@/components/NexusLogo";
import { useSidebarChrome } from "@/components/SidebarChrome";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";

export const NAV_ITEMS = [
  { id: "dashboard", name: "Dashboard", icon: LayoutDashboard, path: "/" },
  { id: "executions", name: "Executions", icon: PlayCircle, path: "/executions" },
  { id: "queue", name: "Queue", icon: Layers, path: "/queue" },
  { id: "workers", name: "Workers", icon: Users, path: "/workers" },
  { id: "journeys", name: "Journeys", icon: Route, path: "/journeys" },
  { id: "schedules", name: "Schedules", icon: Calendar, path: "/schedules" },
  { id: "tools", name: "Tools", icon: Wrench, path: "/tools" },
  { id: "operations", name: "Operations", icon: Activity, path: "/operations" },
] as const;

export function activePath(pathname: string, path: string): boolean {
  if (path === "/") return pathname === "/";
  return pathname === path || pathname.startsWith(`${path}/`);
}

type SidebarPanelProps = {
  mini: boolean;
  onNavigate: (path: string) => void;
  onCollapse: () => void;
  onExpand: () => void;
  onCloseMobile?: () => void;
  showMobileClose?: boolean;
};

function SidebarPanel({
  mini,
  onNavigate,
  onCollapse,
  onExpand,
  onCloseMobile,
  showMobileClose,
}: SidebarPanelProps) {
  const loc = useLocation();

  return (
    <aside
      className={cn(
        "flex flex-col h-full border-r border-border bg-card shrink-0 transition-[width] duration-200",
        mini ? "w-[56px]" : "w-[220px]",
      )}
      aria-label="Main navigation"
    >
      <div
        className={cn(
          "flex items-center h-12 border-b border-border shrink-0",
          mini ? "justify-center px-1" : "gap-2 px-3",
        )}
      >
        {mini ? (
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Expand sidebar"
            onClick={onExpand}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        ) : (
          <>
            <NexusLogo className="h-7 w-7 shrink-0" />
            <span className="font-semibold text-sm truncate">Journey Studio</span>
            {!showMobileClose ? (
              <button
                type="button"
                className="ml-auto hidden md:inline-flex p-1 rounded hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Collapse sidebar"
                onClick={onCollapse}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            ) : null}
          </>
        )}
        {showMobileClose ? (
          <button
            type="button"
            className="ml-auto p-1 rounded hover:bg-accent"
            aria-label="Close menu"
            onClick={onCloseMobile}
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>
      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = activePath(loc.pathname, item.path);
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.path)}
              title={item.name}
              aria-current={active ? "page" : undefined}
              className={cn(
                "w-full flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active ? "bg-primary/15 text-primary font-medium" : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!mini ? <span className="truncate">{item.name}</span> : null}
            </button>
          );
        })}
      </nav>
      <SidebarFooter mini={mini} settingsActive={activePath(loc.pathname, "/settings")} onNavigate={onNavigate} />
      {mini ? (
        <div className="hidden md:flex shrink-0 border-t border-border p-2 justify-center">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Expand sidebar"
            onClick={onExpand}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      ) : null}
    </aside>
  );
}

function SidebarFooter({
  mini,
  settingsActive,
  onNavigate,
}: {
  mini: boolean;
  settingsActive: boolean;
  onNavigate: (path: string) => void;
}) {
  const [helpOpen, setHelpOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <div className="relative shrink-0 border-t border-border p-2 space-y-1">
      <button
        type="button"
        onClick={() => onNavigate("/settings")}
        title="Settings"
        aria-current={settingsActive ? "page" : undefined}
        className={cn(
          "w-full flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          settingsActive ? "bg-primary/15 text-primary font-medium" : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )}
      >
        <Settings className="h-4 w-4 shrink-0" />
        {!mini ? <span className="truncate">Settings</span> : null}
      </button>
      <button
        type="button"
        onClick={() => setHelpOpen((open) => !open)}
        title="Help"
        aria-expanded={helpOpen}
        className="w-full flex items-center gap-2 rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <CircleHelp className="h-4 w-4 shrink-0" />
        {!mini ? <span className="truncate">Help</span> : null}
      </button>
      {helpOpen ? (
        <div className="absolute bottom-12 left-2 z-20 min-w-[160px] rounded-md border bg-background py-1 shadow-lg">
          <button
            type="button"
            className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
            onClick={() => {
              setHelpOpen(false);
              setAboutOpen(true);
            }}
          >
            About
          </button>
        </div>
      ) : null}
      {aboutOpen ? <AboutDialog onClose={() => setAboutOpen(false)} /> : null}
    </div>
  );
}

function AboutDialog({ onClose }: { onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.getSettings(),
  });
  const info = data?.version;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-lg border bg-background shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h3 className="text-lg font-semibold">About</h3>
            <p className="text-sm text-muted-foreground">ai-engine version currently deployed</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            ✕
          </Button>
        </div>
        <div className="space-y-2 px-6 py-4 text-sm">
          {isLoading ? (
            <p className="text-muted-foreground">Loading…</p>
          ) : error ? (
            <p className="text-red-500">{String(error)}</p>
          ) : (
            <>
              <div>
                <div className="text-xs text-muted-foreground">Product</div>
                <div className="font-medium">{info?.name ?? "nexus-ai-engine"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Version</div>
                <div className="font-mono text-base">{info?.version ?? "—"}</div>
              </div>
              {info?.env ? (
                <div>
                  <div className="text-xs text-muted-foreground">Environment</div>
                  <div>{info.env}</div>
                </div>
              ) : null}
              {info?.git_sha && info.git_sha !== "unknown" ? (
                <div>
                  <div className="text-xs text-muted-foreground">Git</div>
                  <div className="font-mono text-xs">{info.git_sha}</div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function Sidebar() {
  const nav = useNavigate();
  const { mini, setMini, mobileOpen, setMobileOpen } = useSidebarChrome();

  const go = (path: string) => {
    nav(path);
    setMobileOpen(false);
  };

  return (
    <>
      <div className="hidden md:flex h-full">
        <SidebarPanel
          mini={mini}
          onNavigate={go}
          onCollapse={() => setMini(true)}
          onExpand={() => setMini(false)}
        />
      </div>
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close menu overlay"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 shadow-xl">
            <SidebarPanel
              mini={false}
              onNavigate={go}
              onCollapse={() => setMini(true)}
              onExpand={() => setMini(false)}
              onCloseMobile={() => setMobileOpen(false)}
              showMobileClose
            />
          </div>
        </div>
      ) : null}
    </>
  );
}
