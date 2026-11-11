import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { KeyValues, Modal, SkeletonRows } from "@/components/ds/kit";
import { Logo } from "@/components/ds/Logo";
import { useSidebarChrome } from "@/components/SidebarChrome";
import { NAV_GROUPS, NAV_ITEMS, SETTINGS_ITEM, activePath, type NavItem } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";

export { NAV_ITEMS, activePath };

const rowBase =
  "group flex h-8 w-full items-center rounded-md text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const rowIdle = "text-sidebar-foreground hover:bg-accent/70 hover:text-foreground";
const rowActive = "bg-accent font-medium text-foreground";

type SidebarNavProps = {
  /** Icon-only rail. */
  mini?: boolean;
  onNavigate: (path: string) => void;
};

/** Navigation content. Rendered inside the desktop rail and the mobile drawer. */
function SidebarNav({ mini, onNavigate }: SidebarNavProps) {
  const loc = useLocation();
  const [aboutOpen, setAboutOpen] = useState(false);

  const layout = mini ? "justify-center" : "gap-2.5 px-2";
  const iconCls = (on: boolean) =>
    cn(
      "h-[17px] w-[17px] transition-colors",
      on ? "text-primary dark:text-brand-hi" : "text-subtle-foreground group-hover:text-foreground",
    );

  const renderItem = (item: NavItem) => {
    const on = activePath(loc.pathname, item.path);
    return (
      <button
        key={item.id}
        type="button"
        onClick={() => onNavigate(item.path)}
        title={mini ? item.name : undefined}
        aria-current={on ? "page" : undefined}
        aria-label={mini ? item.name : undefined}
        className={cn(rowBase, layout, on ? rowActive : rowIdle)}
      >
        <Icon name={item.icon} className={iconCls(on)} />
        {!mini && <span className="truncate">{item.name}</span>}
      </button>
    );
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <nav aria-label="Main navigation" className={cn("scrollbar-hide min-h-0 flex-1 overflow-y-auto pb-3", mini ? "px-2" : "px-3")}>
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={cn(gi > 0 && "mt-5")}>
            {mini
              ? gi > 0 && <div className="mx-1.5 mb-3 border-t border-sidebar-border" />
              : <div className="eyebrow px-2 pb-1.5">{group.label}</div>}
            <div className="space-y-px">{group.items.map(renderItem)}</div>
          </div>
        ))}
      </nav>

      <div className={cn("space-y-px border-t border-sidebar-border py-2.5", mini ? "px-2" : "px-3")}>
        {renderItem(SETTINGS_ITEM)}
        <button
          type="button"
          onClick={() => setAboutOpen(true)}
          title={mini ? "About" : undefined}
          aria-label={mini ? "About" : undefined}
          className={cn(rowBase, layout, rowIdle)}
        >
          <Icon name="info" className={iconCls(false)} />
          {!mini && <span className="truncate">About</span>}
        </button>
      </div>
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}

function AboutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.getSettings(),
    enabled: open,
  });
  const info = data?.version;

  return (
    <Modal open={open} onClose={onClose} title="About" description="The engine version currently deployed.">
      {isLoading ? (
        <SkeletonRows rows={3} className="p-0" />
      ) : error ? (
        <p className="text-sm text-destructive">{String(error)}</p>
      ) : (
        <KeyValues
          items={[
            { label: "Product", value: info?.name ?? "nexus-ai-engine" },
            { label: "Version", value: info?.version ?? "—", mono: true },
            ...(info?.env ? [{ label: "Environment", value: info.env }] : []),
            ...(info?.git_sha && info.git_sha !== "unknown" ? [{ label: "Git", value: info.git_sha, mono: true }] : []),
          ]}
        />
      )}
    </Modal>
  );
}

function Brand({ mini }: { mini?: boolean }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <Logo markOnly={mini} />
      {!mini && (
        <span className="rounded border border-border-strong px-1.5 py-px text-[11px] font-medium leading-4 text-muted-foreground">
          Engine
        </span>
      )}
    </span>
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
      {/* Desktop rail */}
      <aside
        className={cn(
          "relative hidden h-full shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-300 ease-brand-out md:flex",
          mini ? "w-[var(--sidebar-w-mini)]" : "w-[var(--sidebar-w)]",
        )}
      >
        <div className={cn("flex h-[var(--topbar-h)] shrink-0 items-center", mini ? "justify-center px-2" : "justify-between pl-5 pr-2.5")}>
          <button type="button" onClick={() => go("/")} aria-label="Nexus AI Engine home" className="rounded-md">
            <Brand mini={mini} />
          </button>
          {!mini && (
            <button
              type="button"
              onClick={() => setMini(true)}
              aria-label="Collapse sidebar"
              className="flex h-7 w-7 items-center justify-center rounded-md text-subtle-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <Icon name="chevron-left" />
            </button>
          )}
        </div>

        <div className="min-h-0 flex-1 pt-3">
          <SidebarNav mini={mini} onNavigate={go} />
        </div>

        {mini && (
          <button
            type="button"
            onClick={() => setMini(false)}
            aria-label="Expand sidebar"
            className="absolute -right-3 top-[14px] z-10 flex h-6 w-6 items-center justify-center rounded-full border border-border-strong bg-card text-muted-foreground shadow-xs transition-colors hover:text-foreground"
          >
            <Icon name="chevron-right" className="h-3.5 w-3.5" />
          </button>
        )}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 animate-fade-in bg-black/55 backdrop-blur-[2px]"
            aria-label="Close menu overlay"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-[272px] max-w-[86vw] flex-col border-r border-sidebar-border bg-sidebar shadow-lg">
            <div className="flex h-[var(--topbar-h)] shrink-0 items-center justify-between pl-5 pr-2.5">
              <Brand />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                <Icon name="close" className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 pt-3">
              <SidebarNav onNavigate={go} />
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
