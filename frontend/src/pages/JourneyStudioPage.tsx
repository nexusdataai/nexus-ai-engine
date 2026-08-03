import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CheckCircle, Play, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { ToolDescriptor, ValidationResult } from "@/types/api";

const DEFAULT_YAML = `apiVersion: nexus.ai/v1
kind: Journey
metadata:
  id: demo-journey
  version: 1
  labels:
    domain: demo
spec:
  display_name: Demo Journey
  stages:
    - id: stage-1
      display_name: First stage
      steps:
        - id: step-1
          tool: echo
          capability: ping
          arguments: {}
`;

function parseStages(yaml: string): string[] {
  const stages: string[] = [];
  const re = /^\s*-\s*id:\s*(.+)$/gm;
  let m: RegExpExecArray | null;
  while ((m = re.exec(yaml)) !== null) {
    const id = m[1].trim();
    if (yaml.indexOf("stages:") < yaml.indexOf(m[0])) stages.push(id);
  }
  return stages.slice(0, 20);
}

export function JourneyStudioPage() {
  const { journeyId = "new" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const isNew = journeyId === "new";

  const exportQuery = useQuery({
    queryKey: ["journey-export", journeyId],
    queryFn: () => api.exportJourney(journeyId!),
    enabled: !isNew,
  });

  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: () => api.listTools(),
  });

  const [yaml, setYaml] = useState(DEFAULT_YAML);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [toolFilter, setToolFilter] = useState("");

  useEffect(() => {
    if (exportQuery.data?.yaml) setYaml(exportQuery.data.yaml);
  }, [exportQuery.data?.yaml]);

  const stages = useMemo(() => parseStages(yaml), [yaml]);

  const validateMut = useMutation({
    mutationFn: () => api.validateJourneyYaml(yaml),
    onSuccess: setValidation,
  });

  const saveMut = useMutation({
    mutationFn: () => api.createDslJourney(yaml),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["dsl-journeys"] });
      const id = (data as { metadata?: { id?: string } }).metadata?.id;
      if (id) nav(`/journeys/${id}/studio`);
    },
  });

  const runMut = useMutation({
    mutationFn: async () => {
      const meta = yaml.match(/^\s*id:\s*(.+)$/m);
      const id = meta?.[1]?.trim() ?? journeyId;
      return api.submitExecution({ journey_id: id, labels: { triggered_by: "journey-studio" } });
    },
    onSuccess: (res) => nav(`/executions/${res.execution_id}`),
  });

  const filteredTools = (toolsQuery.data?.tools ?? []).filter((t: ToolDescriptor) => {
    const q = toolFilter.toLowerCase();
    return !q || t.id.toLowerCase().includes(q) || t.display_name.toLowerCase().includes(q);
  });

  return (
    <div className="space-y-3 h-full flex flex-col">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" asChild>
          <Link to="/journeys">← Journeys</Link>
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => validateMut.mutate()}
          disabled={validateMut.isPending}
          data-testid="validate-dsl"
        >
          <CheckCircle className="h-4 w-4" />
          Validate
        </Button>
        <Button size="sm" onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
          <Save className="h-4 w-4" />
          Save
        </Button>
        <Button size="sm" onClick={() => runMut.mutate()} disabled={runMut.isPending || isNew} data-testid="run-journey">
          <Play className="h-4 w-4" />
          Run
        </Button>
      </div>

      {validation ? (
        <div
          className={`text-sm rounded-md border px-3 py-2 ${validation.valid ? "border-emerald-500/40 text-emerald-300" : "border-red-500/40 text-red-300"}`}
          data-testid="validation-result"
        >
          {validation.valid
            ? "DSL is valid"
            : validation.errors.map((e) => `${e.path}: ${e.message}`).join("; ")}
        </div>
      ) : null}

      <div className="grid flex-1 min-h-0 gap-3 lg:grid-cols-[200px_1fr_240px]">
        <Card className="overflow-hidden flex flex-col">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">Stages</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto space-y-1 pt-0">
            {stages.length === 0 ? (
              <p className="text-xs text-muted-foreground">No stages parsed</p>
            ) : (
              stages.map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`w-full text-left text-sm rounded px-2 py-1 ${selectedStage === s ? "bg-primary/15 text-primary" : "hover:bg-accent"}`}
                  onClick={() => setSelectedStage(s)}
                >
                  {s}
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="overflow-hidden flex flex-col min-h-[320px]">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">DSL editor</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 pt-0 min-h-0">
            <textarea
              className="w-full h-full min-h-[280px] font-mono text-xs rounded-md border border-input bg-background p-3 resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={yaml}
              onChange={(e) => setYaml(e.target.value)}
              aria-label="Journey DSL YAML"
              spellCheck={false}
            />
          </CardContent>
        </Card>

        <Card className="overflow-hidden flex flex-col" data-testid="tool-picker">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">Tool picker</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden flex flex-col pt-0 gap-2">
            <input
              type="search"
              placeholder="Filter tools…"
              className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
              value={toolFilter}
              onChange={(e) => setToolFilter(e.target.value)}
              aria-label="Filter tools"
            />
            <ul className="flex-1 overflow-y-auto text-xs space-y-1">
              {toolsQuery.isLoading ? (
                <li className="text-muted-foreground">Loading…</li>
              ) : filteredTools.length === 0 ? (
                <li className="text-muted-foreground">No tools published</li>
              ) : (
                filteredTools.map((t) => (
                  <li key={`${t.id}-${t.version}`} className="rounded border border-border px-2 py-1">
                    <div className="font-medium">{t.display_name || t.id}</div>
                    <div className="text-muted-foreground font-mono">{t.id}</div>
                  </li>
                ))
              )}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
