import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { PageHeader } from "@/components/ds/kit";
import { AppDiagnosticsSection } from "@/components/operations/AppDiagnosticsSection";
import { AppTrendsSection } from "@/components/operations/AppTrendsSection";
import { ComingSoonPanel } from "@/components/operations/ComingSoonPanel";
import { InfraDiagnosticsSection } from "@/components/operations/InfraDiagnosticsSection";
import { MonitoringSection } from "@/components/operations/MonitoringSection";
import { AthenaSection } from "@/components/operations/AthenaSection";
import { DynamoDbSection } from "@/components/operations/DynamoDbSection";
import { RedisCacheSection } from "@/components/operations/RedisCacheSection";
import { ResourceMonitoringSection } from "@/components/operations/ResourceMonitoringSection";
import { RunbooksSection } from "@/components/operations/RunbooksSection";
import type { AppTrendsTab } from "@/types/appTrends";
import {
  DEFAULT_TAB_ID,
  MONITORING_SECTIONS,
  OPERATIONS_VIEWS,
  type MonitoringSection as MonitoringSectionId,
  type OperationsView,
  buildOperationsSearchParams,
  getTabLabel,
  getTabsForContext,
  isOperationsView,
  resolveNavigationFromTab,
  resolveNavigationFromView,
} from "@/config/operationsTabs";
import { cn } from "@/lib/utils";

function navEquals(
  a: Record<string, string>,
  searchParams: URLSearchParams,
): boolean {
  return Object.entries(a).every(([key, value]) => searchParams.get(key) === value);
}

export function OperationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const resolved = useMemo(() => {
    const tabParam = searchParams.get("tab");
    if (tabParam) {
      return resolveNavigationFromTab(tabParam);
    }
    const viewParam = searchParams.get("view");
    if (isOperationsView(viewParam)) {
      const sectionParam = searchParams.get("section") as MonitoringSectionId | null;
      return resolveNavigationFromView(viewParam, sectionParam);
    }
    return resolveNavigationFromView("monitoring", "infra");
  }, [searchParams]);

  const [activeView, setActiveView] = useState<OperationsView>(resolved.view);
  const [activeSection, setActiveSection] = useState<MonitoringSectionId | null>(resolved.section);
  const [activeTab, setActiveTab] = useState(resolved.tab);

  const sectionTabs = useMemo(
    () => getTabsForContext(activeView, activeSection),
    [activeView, activeSection],
  );

  const syncUrl = useCallback(
    (view: OperationsView, section: MonitoringSectionId | null, tabId: string) => {
      setSearchParams(buildOperationsSearchParams(view, section, tabId), { replace: true });
    },
    [setSearchParams],
  );

  useEffect(() => {
    setActiveView(resolved.view);
    setActiveSection(resolved.section);
    setActiveTab(resolved.tab);
    const desired = buildOperationsSearchParams(resolved.view, resolved.section, resolved.tab);
    if (!navEquals(desired, searchParams)) {
      setSearchParams(desired, { replace: true });
    }
  }, [resolved, searchParams, setSearchParams]);

  const handleViewChange = (view: OperationsView) => {
    const next = resolveNavigationFromView(view, view === "monitoring" ? "infra" : null);
    setActiveView(next.view);
    setActiveSection(next.section);
    setActiveTab(next.tab);
    syncUrl(next.view, next.section, next.tab);
  };

  const handleSectionChange = (section: MonitoringSectionId) => {
    const tabsInContext = getTabsForContext("monitoring", section);
    const tab = tabsInContext[0]?.id ?? DEFAULT_TAB_ID;
    setActiveSection(section);
    setActiveTab(tab);
    syncUrl("monitoring", section, tab);
  };

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    syncUrl(activeView, activeSection, tabId);
  };

  const renderContent = () => {
    if (activeTab === "monitoring") {
      return <MonitoringSection />;
    }
    if (activeTab === "executions" || activeTab === "queue" || activeTab === "schedules") {
      return <AppTrendsSection tab={activeTab as AppTrendsTab} />;
    }
    if (activeTab === "resources") {
      return <ResourceMonitoringSection />;
    }
    if (activeTab === "redis-cache") {
      return <RedisCacheSection />;
    }
    if (activeTab === "dynamodb") {
      return <DynamoDbSection />;
    }
    if (activeTab === "athena") {
      return <AthenaSection />;
    }
    if (activeTab === "infrastructure") {
      return <InfraDiagnosticsSection />;
    }
    if (activeTab === "diagnostics") {
      return <AppDiagnosticsSection />;
    }
    if (activeTab === "stale-jobs" || activeTab === "crash-analyzer" || activeTab === "dlq") {
      return <RunbooksSection tab={activeTab} />;
    }
    if (activeView === "ai-governance") {
      return <ComingSoonPanel title="AI Governance" />;
    }
    return <ComingSoonPanel title={getTabLabel(activeTab) || "This area"} />;
  };

  const showSections = activeView === "monitoring" && !!activeSection;
  const hasRail = showSections || sectionTabs.length > 0;
  const focusRing = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations"
        description="Monitor infrastructure health and system SLAs for this ai-engine."
      />

      {/* Level 1: operation views (underline row). */}
      <nav aria-label="Operation Views" className="scrollbar-hide flex gap-6 overflow-x-auto border-b border-border">
        {OPERATIONS_VIEWS.map((view) => {
          const active = activeView === view.id;
          return (
            <button
              key={view.id}
              type="button"
              aria-current={active ? "page" : undefined}
              onClick={() => handleViewChange(view.id)}
              className={cn(
                "relative flex h-10 shrink-0 items-center gap-2 whitespace-nowrap text-sm font-medium transition-colors duration-200",
                focusRing,
                active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon name={view.icon} className={active ? "text-primary dark:text-brand-hi" : "text-subtle-foreground"} />
              {view.label}
              <span
                aria-hidden="true"
                className={cn(
                  "absolute inset-x-0 bottom-0 h-0.5 origin-center rounded-full bg-primary transition-transform duration-300 ease-brand-out",
                  active ? "scale-x-100" : "scale-x-0",
                )}
              />
            </button>
          );
        })}
      </nav>

      <div className={cn("grid gap-6", hasRail && "lg:grid-cols-[13rem_minmax(0,1fr)]")}>
        {/* Levels 2 and 3: a rail on desktop, a scrolling row on phones. */}
        {hasRail ? (
          <aside className="min-w-0 space-y-3 lg:sticky lg:top-[calc(var(--topbar-h,4rem)+1.5rem)] lg:self-start">
            {showSections ? (
              <div
                role="group"
                aria-label="Section"
                className="inline-flex w-full items-center gap-0.5 rounded-lg border border-border bg-surface-2/60 p-0.5 sm:w-64 lg:w-full"
              >
                {MONITORING_SECTIONS.map((section) => {
                  const active = activeSection === section.id;
                  return (
                    <button
                      key={section.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => handleSectionChange(section.id)}
                      className={cn(
                        "flex h-7 flex-1 items-center justify-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors duration-150",
                        focusRing,
                        active ? "bg-card text-foreground shadow-xs ring-1 ring-border" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      <Icon name={section.icon} className="h-3.5 w-3.5" />
                      {section.label}
                    </button>
                  );
                })}
              </div>
            ) : null}

            {sectionTabs.length > 0 ? (
              <nav
                aria-label={`${OPERATIONS_VIEWS.find((v) => v.id === activeView)?.label ?? "Operations"} pages`}
                className="scrollbar-hide flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible"
              >
                {sectionTabs.map((tab) => {
                  const active = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      aria-current={active ? "page" : undefined}
                      onClick={() => handleTabChange(tab.id)}
                      className={cn(
                        "flex h-9 shrink-0 items-center gap-2.5 whitespace-nowrap rounded-md px-2.5 text-left text-sm transition-colors duration-150",
                        focusRing,
                        active
                          ? "bg-accent font-medium text-foreground"
                          : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
                      )}
                    >
                      <Icon name={tab.icon} className={active ? "text-primary dark:text-brand-hi" : "text-subtle-foreground"} />
                      {tab.label}
                    </button>
                  );
                })}
              </nav>
            ) : null}
          </aside>
        ) : null}

        <div className="min-h-[400px] min-w-0">{renderContent()}</div>
      </div>
    </div>
  );
}
