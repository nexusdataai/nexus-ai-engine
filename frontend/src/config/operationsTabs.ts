import type { IconName } from "@/components/ds/Icon";

export type OperationsView = "monitoring" | "diagnostics" | "runbooks" | "ai-governance";
export type MonitoringSection = "infra" | "app";

export interface OperationsTabDef {
  id: string;
  label: string;
  icon: IconName;
  view: OperationsView;
  section?: MonitoringSection;
}

export const OPERATIONS_VIEWS: { id: OperationsView; label: string; icon: IconName }[] = [
  { id: "monitoring", label: "Monitoring", icon: "heartbeat" },
  { id: "diagnostics", label: "Diagnostics", icon: "stethoscope" },
  { id: "runbooks", label: "Runbooks", icon: "clipboard" },
  { id: "ai-governance", label: "AI Governance", icon: "shield-check" },
];

export const MONITORING_SECTIONS: { id: MonitoringSection; label: string; icon: IconName }[] = [
  { id: "app", label: "App", icon: "apps" },
  { id: "infra", label: "Infra", icon: "server" },
];

export const DEFAULT_MONITORING_SECTION: MonitoringSection = "infra";
export const DEFAULT_TAB_ID = "monitoring";

export const OPERATIONS_TABS: OperationsTabDef[] = [
  { id: "monitoring", label: "System SLAs", icon: "target", view: "monitoring", section: "infra" },
  { id: "resources", label: "Resource Monitoring", icon: "chart-bar", view: "monitoring", section: "infra" },
  { id: "redis-cache", label: "Redis Cache", icon: "bolt", view: "monitoring", section: "infra" },
  { id: "dynamodb", label: "DynamoDB", icon: "table", view: "monitoring", section: "infra" },
  { id: "athena", label: "Athena Database", icon: "database", view: "monitoring", section: "infra" },
  { id: "cost", label: "Cost", icon: "trend-up", view: "monitoring", section: "infra" },
  { id: "data-protection", label: "Data Protection", icon: "lock", view: "monitoring", section: "infra" },
  { id: "executions", label: "Executions", icon: "play", view: "monitoring", section: "app" },
  { id: "queue", label: "Queue", icon: "layers", view: "monitoring", section: "app" },
  { id: "schedules", label: "Schedules", icon: "calendar", view: "monitoring", section: "app" },
  { id: "infrastructure", label: "Infra", icon: "server", view: "diagnostics" },
  { id: "diagnostics", label: "App", icon: "apps", view: "diagnostics" },
  { id: "stale-jobs", label: "Stale Job Manager", icon: "clock", view: "runbooks" },
  { id: "dlq", label: "Dead Letter Queue", icon: "box", view: "runbooks" },
  { id: "crash-analyzer", label: "Crash Analyzer", icon: "alert-triangle", view: "runbooks" },
];

const VIEW_IDS = new Set<OperationsView>(OPERATIONS_VIEWS.map((v) => v.id));

export function isOperationsView(value: string | null): value is OperationsView {
  return !!value && VIEW_IDS.has(value as OperationsView);
}

export function getTabById(tabId: string): OperationsTabDef | undefined {
  return OPERATIONS_TABS.find((tab) => tab.id === tabId);
}

export function getTabsForContext(
  view: OperationsView,
  section: MonitoringSection | null,
): OperationsTabDef[] {
  if (view === "ai-governance") return [];
  return OPERATIONS_TABS.filter((tab) => {
    if (tab.view !== view) return false;
    if (view === "monitoring") return tab.section === section;
    return true;
  });
}

export function resolveNavigationFromTab(
  tabId: string,
): { view: OperationsView; section: MonitoringSection | null; tab: string } {
  const tab = getTabById(tabId);
  if (tab) {
    return {
      view: tab.view,
      section: tab.section ?? null,
      tab: tab.id,
    };
  }
  return { view: "monitoring", section: DEFAULT_MONITORING_SECTION, tab: DEFAULT_TAB_ID };
}

export function resolveNavigationFromView(
  view: OperationsView,
  sectionParam: MonitoringSection | null,
): { view: OperationsView; section: MonitoringSection | null; tab: string } {
  if (view === "ai-governance") {
    return { view, section: null, tab: "" };
  }
  const section: MonitoringSection | null =
    view === "monitoring"
      ? sectionParam === "app" || sectionParam === "infra"
        ? sectionParam
        : DEFAULT_MONITORING_SECTION
      : null;
  const tabsInContext = getTabsForContext(view, section);
  const tab = tabsInContext[0]?.id ?? DEFAULT_TAB_ID;
  return { view, section, tab };
}

export function buildOperationsSearchParams(
  view: OperationsView,
  section: MonitoringSection | null,
  tabId: string,
): Record<string, string> {
  if (view === "ai-governance") {
    return { view };
  }
  const params: Record<string, string> = { view, tab: tabId };
  if (view === "monitoring" && section) {
    params.section = section;
  }
  return params;
}

export function getTabLabel(tabId: string): string {
  return getTabById(tabId)?.label ?? tabId;
}
