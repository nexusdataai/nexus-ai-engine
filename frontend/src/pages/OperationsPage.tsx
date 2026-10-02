import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

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

  return (
    <div className="w-full max-w-7xl mx-auto space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Operations</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Monitor infrastructure health and system SLAs for this ai-engine.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
            Operation Views
          </p>
          <div className="flex flex-wrap gap-2">
            {OPERATIONS_VIEWS.map((view) => {
              const Icon = view.icon;
              const active = activeView === view.id;
              return (
                <button
                  key={view.id}
                  type="button"
                  onClick={() => handleViewChange(view.id)}
                  className={cn(
                    "inline-flex h-11 items-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors",
                    active
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-muted text-muted-foreground hover:text-foreground",
                  )}
                >
                  <Icon className="h-5 w-5 shrink-0" />
                  {view.label}
                </button>
              );
            })}
          </div>
        </div>

        {activeView === "monitoring" && activeSection ? (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
              Section
            </p>
            <div className="flex flex-wrap gap-2">
              {MONITORING_SECTIONS.map((section) => {
                const Icon = section.icon;
                const active = activeSection === section.id;
                return (
                  <button
                    key={section.id}
                    type="button"
                    onClick={() => handleSectionChange(section.id)}
                    className={cn(
                      "inline-flex h-12 min-w-[8rem] items-center gap-2 rounded-xl px-5 text-base font-semibold transition-colors",
                      active
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "bg-muted text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    {section.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        {sectionTabs.length > 0 ? (
          <div className="border-b">
            <div className="flex gap-1 -mb-px overflow-x-auto">
              {sectionTabs.map((tab) => {
                const Icon = tab.icon;
                const active = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => handleTabChange(tab.id)}
                    className={cn(
                      "flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold transition-colors",
                      active
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30",
                    )}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      <div className="min-h-[400px]">{renderContent()}</div>
    </div>
  );
}
