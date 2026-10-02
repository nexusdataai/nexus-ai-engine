import { useState, type ReactNode } from "react";
import {
  AlertCircle,
  CheckCircle,
  Cloud,
  Database,
  FolderOpen,
  HardDrive,
  Key,
  Layers,
  Monitor,
  Play,
  RefreshCw,
  Server,
  Shield,
  Table2,
  Users,
  XCircle,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type {
  DiagnosticCheckResult,
  DiagnosticCheckStatus,
  DiagnosticOverallStatus,
  InfraCategory,
  InfrastructureDiagnosticsResult,
} from "@/types/diagnostics";

const CATEGORY_SECTIONS: {
  label: string;
  apiCategory: InfraCategory;
  keys: string[];
  icon: ReactNode;
}[] = [
  { label: "Frontend Health", apiCategory: "frontend", keys: ["frontend_serving", "frontend_backend_proxy", "frontend_config"], icon: <Monitor className="h-4 w-4" /> },
  { label: "Backend Health", apiCategory: "backend", keys: ["backend_uptime", "iam_identity", "worker_pool", "ssm_access", "secrets_manager_access"], icon: <Server className="h-4 w-4" /> },
  { label: "DynamoDB (Read+Write)", apiCategory: "dynamodb", keys: ["dynamodb_tables"], icon: <Database className="h-4 w-4" /> },
  { label: "S3 Storage (Read+Write)", apiCategory: "s3", keys: ["s3_buckets"], icon: <HardDrive className="h-4 w-4" /> },
  { label: "Glue / Athena", apiCategory: "glue-athena", keys: ["glue_catalog", "athena_query"], icon: <Cloud className="h-4 w-4" /> },
  { label: "Redis Cache", apiCategory: "redis", keys: ["redis_ping", "redis_memory"], icon: <Zap className="h-4 w-4" /> },
];

const CHECK_ICONS: Record<string, ReactNode> = {
  frontend_serving: <Monitor className="h-4 w-4" />,
  frontend_backend_proxy: <Layers className="h-4 w-4" />,
  frontend_config: <FolderOpen className="h-4 w-4" />,
  backend_uptime: <Server className="h-4 w-4" />,
  iam_identity: <Shield className="h-4 w-4" />,
  worker_pool: <Users className="h-4 w-4" />,
  ssm_access: <Key className="h-4 w-4" />,
  secrets_manager_access: <Key className="h-4 w-4" />,
  dynamodb_tables: <Database className="h-4 w-4" />,
  s3_buckets: <HardDrive className="h-4 w-4" />,
  glue_catalog: <Table2 className="h-4 w-4" />,
  athena_query: <Cloud className="h-4 w-4" />,
  redis_ping: <Zap className="h-4 w-4" />,
  redis_memory: <Zap className="h-4 w-4" />,
};

function statusIcon(status: DiagnosticCheckStatus) {
  if (status === "pass") return <CheckCircle className="h-4 w-4 text-green-500" />;
  if (status === "fail") return <XCircle className="h-4 w-4 text-red-500" />;
  if (status === "warning") return <AlertCircle className="h-4 w-4 text-yellow-500" />;
  return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
}

function tileBorder(status: DiagnosticCheckStatus) {
  if (status === "pass") return "border-green-500/30 bg-green-500/5";
  if (status === "fail") return "border-red-500/30 bg-red-500/5";
  if (status === "warning") return "border-yellow-500/30 bg-yellow-500/5";
  return "border-muted";
}

function overallLabel(status: DiagnosticOverallStatus) {
  const map: Record<DiagnosticOverallStatus, string> = {
    healthy: "bg-green-500",
    degraded: "bg-yellow-500",
    unhealthy: "bg-red-500",
  };
  return (
    <span className="inline-flex items-center gap-2 rounded-full border px-2 py-0.5 text-xs">
      <span className={`h-2 w-2 rounded-full ${map[status] || "bg-muted-foreground"}`} />
      {status}
    </span>
  );
}

function renderSubItems(check: DiagnosticCheckResult, kind: "dynamodb" | "s3") {
  const container =
    kind === "dynamodb"
      ? ((check.details as Record<string, unknown> | undefined)?.tables as Record<string, Record<string, unknown>> | undefined)
      : ((check.details as Record<string, unknown> | undefined)?.buckets as Record<string, Record<string, unknown>> | undefined);
  if (!container) return null;
  return (
    <div className="mt-2 space-y-1">
      {Object.entries(container).map(([key, val]) => {
        const st = (val?.status === "pass" ? "pass" : val?.status === "fail" ? "fail" : "warning") as DiagnosticCheckStatus;
        const readable = val?.readable ?? val?.read_access;
        const writable = val?.writable ?? val?.write_access;
        return (
          <div key={key} className={`p-2 rounded border text-xs ${tileBorder(st)}`}>
            <div className="flex items-center justify-between">
              <span className="font-medium">{key}</span>
              {statusIcon(st)}
            </div>
            <div className="text-muted-foreground mt-0.5">
              {String(kind === "dynamodb" ? val?.table_name : val?.bucket || "")}
              {readable !== undefined && <span className="ml-2">R:{readable ? "OK" : "NO"}</span>}
              {writable !== undefined && <span className="ml-1">W:{writable ? "OK" : "NO"}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
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
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Server className="h-5 w-5" />
              Infrastructure Diagnostics
            </CardTitle>
            {result ? overallLabel(result.status) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={handleRunAll} disabled={isRunning || !!runningCategory} className="w-full">
            {isRunning ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Run All Diagnostics
          </Button>

          {CATEGORY_SECTIONS.map((section) => {
            const sectionChecks = result ? Object.entries(result.checks).filter(([k]) => section.keys.includes(k)) : [];
            return (
              <div key={section.apiCategory} className="border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-medium text-sm">
                    {section.icon}
                    {section.label}
                  </div>
                  <Button size="sm" variant="outline" disabled={isRunning || !!runningCategory} onClick={() => handleRunCategory(section.apiCategory)}>
                    {runningCategory === section.apiCategory ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                    Run
                  </Button>
                </div>
                {sectionChecks.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                    {sectionChecks.map(([key, check]) => (
                      <div key={key} className={`p-3 rounded-lg border ${tileBorder(check.status)}`}>
                        <div className="flex items-center gap-2 mb-1">
                          {CHECK_ICONS[key] || <Server className="h-4 w-4" />}
                          <span className="text-xs font-medium truncate">{key.replace(/_/g, " ")}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          {statusIcon(check.status)}
                          <span className="text-xs text-muted-foreground">{Number(check.latency_ms).toFixed(0)}ms</span>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1 truncate" title={check.message}>
                          {check.message}
                        </div>
                        {key === "dynamodb_tables" ? renderSubItems(check, "dynamodb") : null}
                        {key === "s3_buckets" ? renderSubItems(check, "s3") : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}

          <pre className="p-3 bg-muted rounded-lg text-xs overflow-auto max-h-64 font-mono whitespace-pre-wrap">{output}</pre>
        </CardContent>
      </Card>
    </div>
  );
}
