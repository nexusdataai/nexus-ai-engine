import { Fragment, useState } from "react";

import { Icon, type IconName } from "@/components/ds/Icon";
import { CodeBlock, Panel, StatusPill, SubHeading, type Tone } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import type {
  DiagnosticCheckResult,
  DiagnosticCheckStatus,
  DiagnosticOverallStatus,
  InfraCategory,
  InfrastructureDiagnosticsResult,
} from "@/types/diagnostics";

import { SectionHeader } from "./parts";

const CATEGORY_SECTIONS: {
  label: string;
  apiCategory: InfraCategory;
  keys: string[];
  icon: IconName;
}[] = [
  { label: "Frontend Health", apiCategory: "frontend", keys: ["frontend_serving", "frontend_backend_proxy", "frontend_config"], icon: "globe" },
  { label: "Backend Health", apiCategory: "backend", keys: ["backend_uptime", "iam_identity", "worker_pool", "ssm_access", "secrets_manager_access"], icon: "server" },
  { label: "DynamoDB (Read+Write)", apiCategory: "dynamodb", keys: ["dynamodb_tables"], icon: "table" },
  { label: "S3 Storage (Read+Write)", apiCategory: "s3", keys: ["s3_buckets"], icon: "folder" },
  { label: "Glue / Athena", apiCategory: "glue-athena", keys: ["glue_catalog", "athena_query"], icon: "cloud" },
  { label: "Redis Cache", apiCategory: "redis", keys: ["redis_ping", "redis_memory"], icon: "bolt" },
];

const CHECK_TONE: Record<string, Tone> = { pass: "success", fail: "danger", warning: "warning" };
const OVERALL_TONE: Record<DiagnosticOverallStatus, Tone> = { healthy: "success", degraded: "warning", unhealthy: "danger" };

function CheckStatus({ status }: { status: DiagnosticCheckStatus }) {
  return <StatusPill tone={CHECK_TONE[status] ?? "neutral"}>{status}</StatusPill>;
}

function renderSubItems(check: DiagnosticCheckResult, kind: "dynamodb" | "s3") {
  const container =
    kind === "dynamodb"
      ? ((check.details as Record<string, unknown> | undefined)?.tables as Record<string, Record<string, unknown>> | undefined)
      : ((check.details as Record<string, unknown> | undefined)?.buckets as Record<string, Record<string, unknown>> | undefined);
  if (!container) return null;
  return Object.entries(container).map(([key, val]) => {
    const st = (val?.status === "pass" ? "pass" : val?.status === "fail" ? "fail" : "warning") as DiagnosticCheckStatus;
    const readable = val?.readable ?? val?.read_access;
    const writable = val?.writable ?? val?.write_access;
    return (
      <tr key={key}>
        <td className="pl-9 text-foreground">{key}</td>
        <td>
          <CheckStatus status={st} />
        </td>
        <td className="r" />
        <td className="text-xs text-muted-foreground">
          <span className="font-mono">{String(kind === "dynamodb" ? val?.table_name : val?.bucket || "")}</span>
          {readable !== undefined && <span className="ml-2">R:{readable ? "OK" : "NO"}</span>}
          {writable !== undefined && <span className="ml-1">W:{writable ? "OK" : "NO"}</span>}
        </td>
      </tr>
    );
  });
}

export function InfraDiagnosticsSection() {
  const [result, setResult] = useState<InfrastructureDiagnosticsResult | null>(null);
  const [output, setOutput] = useState("Run diagnostics to check infrastructure health...");
  const [isRunning, setIsRunning] = useState(false);
  const [runningCategory, setRunningCategory] = useState<string | null>(null);

  const formatOutput = (data: InfrastructureDiagnosticsResult) => {
    const lines = Object.entries(data.checks).map(([key, check]) => {
      const icon = check.status === "pass" ? "✅" : check.status === "fail" ? "❌" : check.status === "warning" ? "⚠️" : "⏭";
      return `${icon} ${key}: ${check.message} (${Number(check.latency_ms).toFixed(1)}ms)`;
    });
    setOutput(`Infrastructure Diagnostics\n\nOverall Status: ${data.status.toUpperCase()}\nTimestamp: ${data.timestamp}\n\nChecks:\n${lines.join("\n")}`);
  };

  const handleRunAll = async () => {
    setIsRunning(true);
    setOutput("Running all infrastructure diagnostics...");
    try {
      const data = await api.runInfraDiagnostics();
      setResult(data);
      formatOutput(data);
    } catch (error) {
      setOutput(`Error: ${(error as Error).message}`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleRunCategory = async (category: InfraCategory) => {
    setRunningCategory(category);
    try {
      const data = await api.runInfraCategory(category);
      setResult((prev) => (prev ? { ...prev, status: data.status, checks: { ...prev.checks, ...data.checks } } : data));
      formatOutput(data);
    } catch (error) {
      setOutput(`Error: ${(error as Error).message}`);
    } finally {
      setRunningCategory(null);
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Infrastructure Diagnostics"
        meta={
          result ? (
            <StatusPill variant="soft" tone={OVERALL_TONE[result.status] ?? "neutral"}>
              {result.status}
            </StatusPill>
          ) : null
        }
        actions={
          <Button size="sm" onClick={handleRunAll} disabled={isRunning || !!runningCategory}>
            <Icon name={isRunning ? "refresh" : "play"} className={isRunning ? "animate-spin" : undefined} />
            Run All Diagnostics
          </Button>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel flush>
          {CATEGORY_SECTIONS.map((section) => {
            const sectionChecks = result ? Object.entries(result.checks).filter(([k]) => section.keys.includes(k)) : [];
            return (
              <div key={section.apiCategory} className="border-b border-border last:border-b-0">
                <div className="flex items-center justify-between gap-3 px-4 py-3 sm:px-5">
                  <div className="flex min-w-0 items-center gap-2.5 text-sm font-medium text-foreground">
                    <Icon name={section.icon} className="text-subtle-foreground" />
                    <span className="truncate">{section.label}</span>
                  </div>
                  <Button size="sm" variant="outline" disabled={isRunning || !!runningCategory} onClick={() => handleRunCategory(section.apiCategory)}>
                    <Icon
                      name={runningCategory === section.apiCategory ? "refresh" : "play"}
                      className={runningCategory === section.apiCategory ? "animate-spin" : undefined}
                    />
                    Run
                  </Button>
                </div>
                {sectionChecks.length > 0 ? (
                  <div className="scroll-thin overflow-x-auto border-t border-border">
                    <table className="tbl">
                      <thead>
                        <tr>
                          <th className="w-[30%]">Check</th>
                          <th>Status</th>
                          <th className="r">Latency</th>
                          <th>Message</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sectionChecks.map(([key, check]) => (
                          <Fragment key={key}>
                            <tr>
                              <td className="font-medium text-foreground">{key.replace(/_/g, " ")}</td>
                              <td>
                                <CheckStatus status={check.status} />
                              </td>
                              <td className="r num whitespace-nowrap text-muted-foreground">{Number(check.latency_ms).toFixed(0)}ms</td>
                              <td className="max-w-[360px] truncate text-xs text-muted-foreground" title={check.message}>
                                {check.message}
                              </td>
                            </tr>
                            {key === "dynamodb_tables" ? renderSubItems(check, "dynamodb") : null}
                            {key === "s3_buckets" ? renderSubItems(check, "s3") : null}
                          </Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            );
          })}
        </Panel>

        <div className="min-w-0">
          <SubHeading>Output</SubHeading>
          <CodeBlock wrap maxHeight={480}>{output}</CodeBlock>
        </div>
      </div>
    </div>
  );
}
