import { Calendar, ChevronLeft, ChevronRight, LayoutDashboard, Layers, PlayCircle, Route, Users, Wrench, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { NexusLogo } from "@/components/NexusLogo";
import { useSidebarChrome } from "@/components/SidebarChrome";
import { cn } from "@/lib/utils";

export const NAV_ITEMS = [
  { id: "dashboard", name: "Dashboard", icon: LayoutDashboard, path: "/" },
  { id: "executions", name: "Executions", icon: PlayCircle, path: "/executions" },
  { id: "queue", name: "Queue", icon: Layers, path: "/queue" },
  { id: "workers", name: "Workers", icon: Users, path: "/workers" },
  { id: "journeys", name: "Journeys", icon: Route, path: "/journeys" },
  { id: "schedules", name: "Schedules", icon: Calendar, path: "/schedules" },
  { id: "tools", name: "Tools", icon: Wrench, path: "/tools" },
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
