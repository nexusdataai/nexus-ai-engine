import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Icon } from "@/components/ds/Icon";
import { InlineError, Notice, SearchInput, StatusPill } from "@/components/ds/kit";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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

  const lineCount = yaml.split("\n").length;
  const displayName = yaml.match(/^\s*display_name:\s*(.+)$/m)?.[1]?.trim();
  const metaId = yaml.match(/^\s*id:\s*(.+)$/m)?.[1]?.trim();
  const paneHead = "flex h-10 shrink-0 items-center justify-between gap-2 border-b border-border px-3.5 text-sm font-medium text-foreground";

  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100dvh-var(--topbar-h)-3rem)] lg:min-h-[560px]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <Link to="/journeys" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
            <Icon name="chevron-left" className="h-3.5 w-3.5" />
            Journeys
          </Link>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 className="text-xl font-medium tracking-tight text-foreground">{displayName || (isNew ? "New DSL journey" : journeyId)}</h2>
            {metaId ? <span className="mono-id">{metaId}</span> : null}
            {isNew ? <StatusPill tone="neutral" variant="soft">Draft, not saved</StatusPill> : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => validateMut.mutate()}
            disabled={validateMut.isPending}
            data-testid="validate-dsl"
          >
            <Icon name={validateMut.isPending ? "spinner" : "shield-check"} className={validateMut.isPending ? "animate-spin" : undefined} />
            Validate
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => runMut.mutate()}
            disabled={runMut.isPending || isNew}
            title={isNew ? "Save the journey before running it" : undefined}
            data-testid="run-journey"
          >
            <Icon name="play" />
            Run
          </Button>
          <Button size="sm" onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
            <Icon name={saveMut.isPending ? "spinner" : "check"} className={saveMut.isPending ? "animate-spin" : undefined} />
            Save
          </Button>
        </div>
      </div>

      {validation ? (
        <Notice tone={validation.valid ? "success" : "danger"} data-testid="validation-result">
          {validation.valid
            ? "DSL is valid"
            : validation.errors.map((e) => `${e.path}: ${e.message}`).join("; ")}
        </Notice>
      ) : null}
      {saveMut.isError ? <InlineError>Could not save. {String(saveMut.error)}</InlineError> : null}
      {runMut.isError ? <InlineError>Could not start the run. {String(runMut.error)}</InlineError> : null}

      <div className="grid min-h-0 flex-1 overflow-hidden rounded-xl border border-border bg-card shadow-xs lg:grid-cols-[212px_minmax(0,1fr)_264px]">
        <section className="flex min-h-0 flex-col border-b border-border lg:border-b-0 lg:border-r">
          <div className={paneHead}>
            Stages
            <span className="num text-xs font-normal text-muted-foreground">{stages.length}</span>
          </div>
          <div className="scroll-thin max-h-40 min-h-0 flex-1 space-y-px overflow-y-auto p-2 lg:max-h-none">
            {stages.length === 0 ? (
              <p className="px-2 py-3 text-sm text-subtle-foreground">No stages parsed</p>
            ) : (
              stages.map((st, i) => (
                <button
                  key={st}
                  type="button"
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selectedStage === st ? "bg-accent font-medium text-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                  )}
                  onClick={() => setSelectedStage(st)}
                >
                  <span className="num flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-strong text-[11px]">{i + 1}</span>
                  <span className="truncate font-mono text-xs">{st}</span>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="flex min-h-[360px] min-w-0 flex-col">
          <div className={paneHead}>
            <span className="flex items-center gap-2">
              <Icon name="file-code" className="text-subtle-foreground" />
              DSL editor
            </span>
            <span className="num text-xs font-normal text-muted-foreground">YAML · {lineCount} lines</span>
          </div>
          <textarea
            className="scroll-thin min-h-[320px] w-full flex-1 resize-none bg-background p-4 font-mono text-[13px] leading-6 text-foreground focus-visible:outline-none focus-visible:ring-0"
            value={yaml}
            onChange={(e) => setYaml(e.target.value)}
            aria-label="Journey DSL YAML"
            spellCheck={false}
          />
        </section>

        <section className="flex min-h-0 flex-col border-t border-border lg:border-l lg:border-t-0" data-testid="tool-picker">
          <div className={paneHead}>
            Tool picker
            <span className="num text-xs font-normal text-muted-foreground">{filteredTools.length}</span>
          </div>
          <div className="border-b border-border p-2">
            <SearchInput value={toolFilter} onChange={setToolFilter} placeholder="Filter tools…" type="search" aria-label="Filter tools" className="sm:w-full" />
          </div>
          <ul className="scroll-thin max-h-56 min-h-0 flex-1 divide-y divide-border overflow-y-auto lg:max-h-none">
            {toolsQuery.isLoading ? (
              <li className="px-3.5 py-3 text-sm text-subtle-foreground">Loading…</li>
            ) : filteredTools.length === 0 ? (
              <li className="px-3.5 py-3 text-sm text-subtle-foreground">No tools published</li>
            ) : (
              filteredTools.map((t) => (
                <li key={`${t.id}-${t.version}`} className="px-3.5 py-2.5">
                  <div className="truncate text-sm font-medium text-foreground">{t.display_name || t.id}</div>
                  <div className="mono-id truncate">{t.id}</div>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
