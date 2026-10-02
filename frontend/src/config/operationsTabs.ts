import {
  Activity,
  AppWindow,
  Briefcase,
  BookOpen,
  Clock,
  Database,
  DollarSign,
  HardDrive,
  ListChecks,
  Table2,
  Warehouse,
  Monitor,
  Scale,
  Server,
  ServerCrash,
  Shield,
  Stethoscope,
  Inbox,
  type LucideIcon,
} from "lucide-react";

export type OperationsView = "monitoring" | "diagnostics" | "runbooks" | "ai-governance";
export type MonitoringSection = "infra" | "app";

export interface OperationsTabDef {
  id: string;
  label: string;
  icon: LucideIcon;
  view: OperationsView;
  section?: MonitoringSection;
}

export const OPERATIONS_VIEWS: { id: OperationsView; label: string; icon: LucideIcon }[] = [
  { id: "monitoring", label: "Monitoring", icon: Monitor },
  { id: "diagnostics", label: "Diagnostics", icon: Stethoscope },
  { id: "runbooks", label: "Runbooks", icon: BookOpen },
  { id: "ai-governance", label: "AI Governance", icon: Scale },
];

export const MONITORING_SECTIONS: { id: MonitoringSection; label: string; icon: LucideIcon }[] = [
  { id: "app", label: "App", icon: AppWindow },
  { id: "infra", label: "Infra", icon: Server },
];

export const DEFAULT_MONITORING_SECTION: MonitoringSection = "infra";
export const DEFAULT_TAB_ID = "monitoring";

export const OPERATIONS_TABS: OperationsTabDef[] = [
  { id: "monitoring", label: "System SLAs", icon: Activity, view: "monitoring", section: "infra" },
  { id: "resources", label: "Resource Monitoring", icon: HardDrive, view: "monitoring", section: "infra" },
  { id: "redis-cache", label: "Redis Cache", icon: Database, view: "monitoring", section: "infra" },
  { id: "dynamodb", label: "DynamoDB", icon: Table2, view: "monitoring", section: "infra" },
  { id: "athena", label: "Athena Database", icon: Warehouse, view: "monitoring", section: "infra" },
  { id: "cost", label: "Cost", icon: DollarSign, view: "monitoring", section: "infra" },
  { id: "data-protection", label: "Data Protection", icon: Shield, view: "monitoring", section: "infra" },
  { id: "executions", label: "Executions", icon: ListChecks, view: "monitoring", section: "app" },
  { id: "queue", label: "Queue", icon: Briefcase, view: "monitoring", section: "app" },
  { id: "schedules", label: "Schedules", icon: Clock, view: "monitoring", section: "app" },
  { id: "infrastructure", label: "Infra", icon: Server, view: "diagnostics" },
  { id: "diagnostics", label: "App", icon: Stethoscope, view: "diagnostics" },
  { id: "stale-jobs", label: "Stale Job Manager", icon: Clock, view: "runbooks" },
  { id: "dlq", label: "Dead Letter Queue", icon: Inbox, view: "runbooks" },
  { id: "crash-analyzer", label: "Crash Analyzer", icon: ServerCrash, view: "runbooks" },
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
