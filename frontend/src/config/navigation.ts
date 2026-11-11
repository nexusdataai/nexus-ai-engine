/**
 * Single source of truth for product navigation.
 * Used by the sidebar, the mobile drawer and the breadcrumbs.
 * Add a new screen here and it appears in all three.
 */
import type { IconName } from "@/components/ds/Icon";

export interface NavItem {
  id: string;
  name: string;
  path: string;
  icon: IconName;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [{ id: "dashboard", name: "Dashboard", path: "/", icon: "dashboard" }],
  },
  {
    label: "Runtime",
    items: [
      { id: "executions", name: "Executions", path: "/executions", icon: "play" },
      { id: "queue", name: "Queue", path: "/queue", icon: "layers" },
      { id: "workers", name: "Workers", path: "/workers", icon: "server" },
    ],
  },
  {
    label: "Automation",
    items: [
      { id: "journeys", name: "Journeys", path: "/journeys", icon: "route" },
      { id: "schedules", name: "Schedules", path: "/schedules", icon: "calendar" },
      { id: "tools", name: "Tools", path: "/tools", icon: "wrench" },
    ],
  },
  {
    label: "AI Ops",
    items: [{ id: "operations", name: "Operations", path: "/operations", icon: "heartbeat" }],
  },
];

export const SETTINGS_ITEM: NavItem = { id: "settings", name: "Settings", path: "/settings", icon: "settings" };

/** Flat list (kept for callers that iterate every destination). */
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export function activePath(pathname: string, path: string): boolean {
  if (path === "/") return pathname === "/";
  return pathname === path || pathname.startsWith(`${path}/`);
}

export interface Crumb {
  label: string;
  path?: string;
}

/** Breadcrumb trail for a pathname: Group / Page / Sub-page. */
export function getBreadcrumbs(pathname: string): Crumb[] {
  if (pathname === "/") return [{ label: "Overview" }, { label: "Dashboard" }];
  if (activePath(pathname, "/settings")) return [{ label: "Settings" }];
  if (pathname.startsWith("/auth/")) return [{ label: "Signing in" }];

  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (item.path === "/" || !activePath(pathname, item.path)) continue;
      const crumbs: Crumb[] = [{ label: group.label }, { label: item.name, path: item.path }];
      if (pathname !== item.path) {
        if (pathname.startsWith("/executions/stage/")) crumbs.push({ label: "Stage job" });
        else if (pathname.startsWith("/executions/")) crumbs.push({ label: "Execution" });
        else if (pathname.startsWith("/journeys/") && pathname.endsWith("/studio")) crumbs.push({ label: "DSL studio" });
        else if (pathname.startsWith("/journeys/")) crumbs.push({ label: "Journey" });
      }
      return crumbs;
    }
  }
  return [{ label: "Nexus AI Engine" }];
}

export function getPageTitle(pathname: string): string {
  const crumbs = getBreadcrumbs(pathname);
  return crumbs[crumbs.length - 1]?.label ?? "Nexus AI Engine";
}
