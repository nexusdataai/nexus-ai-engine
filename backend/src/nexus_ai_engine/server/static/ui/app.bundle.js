/*
 * Nexus AI Engine — embedded Journey Studio UI
 *
 * Single-file React app loaded by /ui/index.html. No bundler: Babel Standalone
 * compiles the JSX in the browser. React + ReactDOM are loaded from unpkg
 * by index.html.
 *
 * Talks to the same-origin API at /api/v1/* (journeys, jobs, schedules,
 * prompts). Hash-based routing; no history API so it works under any
 * sub-path.
 */

const {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
  useReducer
} = React;

/* ─────────────────────── API client ─────────────────────── */

const api = {
  listJourneys(params = {}) {
    const qs = new URLSearchParams();
    if (params.q) qs.set('q', params.q);
    if (params.status) qs.set('status_filter', params.status);
    if (params.capability) qs.set('capability', params.capability);
    if (params.limit) qs.set('limit', params.limit);
    const s = qs.toString();
    return fetch('/api/v1/journeys/' + (s ? '?' + s : '')).then(requireOk).then(normalizeJourneyList);
  },
  // `idHint` is forwarded into normalizeJourney so the legacy GET (which
  // returns no id field anywhere in the body) still produces a journey
  // object with `id` populated. Default to the URL path's id.
  getJourney(id) {
    return fetch(`/api/v1/journeys/${id}`).then(requireOk).then(j => normalizeJourney(j, id));
  },
  createJourney(body) {
    return postJson('/api/v1/journeys/', body).then(j => normalizeJourney(j));
  },
  deleteJourney(id) {
    return fetch(`/api/v1/journeys/${id}`, {
      method: 'DELETE'
    }).then(requireOk);
  },
  cloneJourney(id, name) {
    return postJson(`/api/v1/journeys/${id}/clone`, name ? {
      name
    } : {}).then(j => normalizeJourney(j));
  },
  listJobs(jid) {
    return fetch(`/api/v1/journeys/${jid}/jobs`).then(requireOk).then(normalizeJobList);
  },
  getJob(jid, id) {
    return fetch(`/api/v1/journeys/${jid}/jobs/${id}`).then(requireOk).then(j => normalizeJob(j, id));
  },
  jobStatus(jid, id) {
    return fetch(`/api/v1/journeys/${jid}/jobs/${id}/status`).then(requireOk);
  },
  // The legacy router takes stage_id / triggered_by / reason as query
  // params (`POST /{jid}/jobs?stage_id=...`). The slim router takes them
  // as a JSON body (`JobRunRequest`). Sending BOTH satisfies both —
  // FastAPI's query-param parser ignores the body, and Pydantic's body
  // parser ignores the query string. The legacy router's response uses
  // `job_id` rather than `id`, so we run it through normalizeJob.
  runJob(jid, stageId, reason) {
    const qs = new URLSearchParams({
      stage_id: stageId,
      triggered_by: 'ui'
    });
    if (reason) qs.set('reason', reason);
    return postJson(`/api/v1/journeys/${jid}/jobs?${qs.toString()}`, {
      stage_id: stageId,
      triggered_by: 'ui',
      reason
    }).then(j => normalizeJob(j));
  },
  cancelJob(jid, id) {
    return postJson(`/api/v1/journeys/${jid}/jobs/${id}/cancel`, {}).then(j => normalizeJob(j, id));
  },
  retryJob(jid, id) {
    return postJson(`/api/v1/journeys/${jid}/jobs/${id}/retry`, {}).then(j => normalizeJob(j, id));
  },
  jobLogs(jid, id) {
    return fetch(`/api/v1/journeys/${jid}/jobs/${id}/logs`).then(requireOk).then(normalizeLogs);
  },
  aggregateReport(jid) {
    return fetch(`/api/v1/journeys/${jid}/aggregate-report`).then(requireOk);
  },
  listJobReports(jid, id) {
    return fetch(`/api/v1/journeys/${jid}/jobs/${id}/reports`).then(requireOk);
  },
  listSchedules(journeyId) {
    const q = journeyId ? `?journey_id=${encodeURIComponent(journeyId)}` : '';
    return fetch(`/api/v1/schedules/${q}`).then(requireOk);
  },
  createSchedule(body) {
    return postJson('/api/v1/schedules/', body);
  },
  updateSchedule(id, b) {
    return patchJson(`/api/v1/schedules/${id}`, b);
  },
  deleteSchedule(id) {
    return fetch(`/api/v1/schedules/${id}`, {
      method: 'DELETE'
    }).then(requireOk);
  },
  runScheduleNow(id) {
    return postJson(`/api/v1/schedules/${id}/run`, {});
  },
  listPrompts() {
    return fetch('/api/v1/prompts').then(requireOk);
  },
  updatePrompt(id, body) {
    return putJson(`/api/v1/prompts/${id}`, body);
  },
  resetPrompts() {
    return postJson('/api/v1/prompts/reset', {});
  },
  promptAudit(limit = 50) {
    return fetch(`/api/v1/prompts/audit/log?limit=${limit}`).then(requireOk);
  },
  // Lightweight read of every registered stage's metadata + step list.
  // Used by the v2 UI to enrich `journey.stages[].steps` because the
  // legacy DynamoDB router persists stage records without their steps
  // (steps are an inherent property of the registered stage class).
  // Returns: { count, stages: [{stage_id, name, description, steps:[...]}, ...] }
  listRegisteredStages() {
    return fetch('/api/v1/stages/registered').then(requireOk);
  }
};
function postJson(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json'
    },
    body: JSON.stringify(body)
  }).then(requireOk);
}
function putJson(url, body) {
  return fetch(url, {
    method: 'PUT',
    headers: {
      'content-type': 'application/json'
    },
    body: JSON.stringify(body)
  }).then(requireOk);
}
function patchJson(url, body) {
  return fetch(url, {
    method: 'PATCH',
    headers: {
      'content-type': 'application/json'
    },
    body: JSON.stringify(body)
  }).then(requireOk);
}
async function requireOk(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return null;
  const body = await res.json();
  return unwrapEnvelope(body);
}

// The slim routers (in-memory engine path) return raw Pydantic models
// (e.g. `Journey`, `Job`, `LogEntry[]`). The legacy routers (production
// DynamoDB-backed Engine) wrap every response in an envelope:
//   - List:   `{success, total, limit, offset, data: [...]}`
//   - Single: `{success, message, data: {...}}`
//   - Error:  `{success: false, message: "..."}`  (HTTP 200 with error inside)
// The same UI talks to both, so we strip the envelope here. When the body
// is already a raw model we pass it through untouched.
function unwrapEnvelope(body) {
  if (body == null || typeof body !== 'object' || Array.isArray(body)) return body;
  // Envelope shape detection: `success` is the unique marker.
  if (!('success' in body)) return body;
  if (body.success === false) {
    throw new Error(body.message || body.error || 'request failed');
  }
  // `data` may be missing for confirmation-only responses (e.g. delete);
  // fall back to the envelope itself so callers that only need the
  // success flag still get something useful.
  return 'data' in body ? body.data : body;
}

// Map a Journey object from either backend shape to the canonical slim
// shape the UI expects. The two backends return very different bodies:
//
//   Slim (in-memory engine):
//     {id, name, capability, status, created_at, updated_at, stages,
//      jobs_total, jobs_done, success_rate, avg_duration_seconds, ...}
//
//   Legacy GET /api/v1/journeys/{id} (DynamoDB engine):
//     {summary: {...}, stages: [], jobs: [], rules: [],
//      createdAt, updatedAt,
//      metadata: {name, status, odaComponentType, createdBy, ...}}
//     Note: NO journeyId / id field anywhere in the body — the ID is
//     only known from the URL path that fetched it.
//
//   Legacy GET /api/v1/journeys/ (list, per-row):
//     {journeyId, name, status, odaComponentType, createdAt, updatedAt,
//      totalJobs, completedJobs, failedJobs, overallProgress, ...}
//
// We harvest fields from wherever they live (top level, then nested
// `metadata`) and fall back to a caller-supplied `idHint` (the URL
// path's journeyId) for the missing-id case.
function normalizeJourney(raw, idHint) {
  if (raw == null || typeof raw !== 'object' || Array.isArray(raw)) return raw;
  const j = {
    ...raw
  };
  const meta = j.metadata && typeof j.metadata === 'object' ? j.metadata : {};

  // ID — try every shape, fall back to the URL hint.
  if (j.id == null) j.id = j.journeyId ?? meta.journeyId ?? meta.id ?? idHint ?? null;

  // Display fields — legacy GET puts these in metadata.
  if (j.name == null) j.name = meta.name ?? j.id ?? 'Journey';
  if (j.description == null) j.description = meta.description ?? j.description ?? '';
  if (j.status == null) j.status = meta.status ?? 'created';

  // Capability ← odaComponentType (top-level or nested).
  if (j.capability == null) {
    j.capability = j.odaComponentType ?? meta.odaComponentType ?? null;
  }

  // Timestamps.
  if (j.created_at == null) j.created_at = j.createdAt ?? meta.createdAt ?? null;
  if (j.updated_at == null) j.updated_at = j.updatedAt ?? meta.updatedAt ?? null;

  // Aggregate counters / rates — legacy may surface them under different
  // names (totalJobs, completedJobs, ...) on the LIST endpoint, or skip
  // them entirely on the detail endpoint. Default everything to 0 so the
  // cards never crash on missing fields.
  if (typeof j.jobs_total !== 'number') {
    j.jobs_total = j.totalJobs ?? meta.totalJobs ?? 0;
  }
  if (typeof j.jobs_done !== 'number') {
    j.jobs_done = j.completedJobs ?? meta.completedJobs ?? 0;
  }
  if (typeof j.jobs_running !== 'number') {
    j.jobs_running = j.runningJobs ?? meta.runningJobs ?? 0;
  }
  if (typeof j.jobs_failed !== 'number') {
    j.jobs_failed = j.failedJobs ?? meta.failedJobs ?? 0;
  }
  if (typeof j.success_rate !== 'number') j.success_rate = 0;
  if (typeof j.avg_duration_seconds !== 'number') j.avg_duration_seconds = 0;
  if (!Array.isArray(j.stages)) j.stages = [];
  return j;
}
function normalizeJourneyList(raw) {
  if (!Array.isArray(raw)) return raw;
  return raw.map(j => normalizeJourney(j));
}

// Map a Job object from either backend shape to the canonical slim shape.
//
//   Slim:   {id, journey_id, stage_id, status, progress, current_step_id,
//            step_results: [{step_id, status, progress, started_at, ended_at, ...}],
//            metrics: {...}, started_at, ended_at, duration_seconds, ...}
//
//   Legacy POST /jobs response (envelope-stripped):
//     {job_id, stage_id, triggered_by, status, status_url}
//
//   Legacy GET  /jobs/{id} response (envelope-stripped):
//     {jobId, stageId, status, progress, triggeredBy, startedAt, completedAt,
//      duration, steps: [{stepId, status, duration, ...}], metrics: {...}}
//
// `idHint` is the URL-path job_id used as a fallback when the body
// doesn't include the id.
function normalizeJob(raw, idHint) {
  if (raw == null || typeof raw !== 'object' || Array.isArray(raw)) return raw;
  const j = {
    ...raw
  };
  if (j.id == null) j.id = j.job_id ?? j.jobId ?? idHint ?? null;
  if (j.journey_id == null) j.journey_id = j.journeyId ?? null;
  if (j.stage_id == null) j.stage_id = j.stageId ?? null;
  if (j.status == null) j.status = 'queued';
  if (j.progress == null) j.progress = 0;
  if (j.current_step_id == null && j.currentStepId != null) j.current_step_id = j.currentStepId;
  if (j.started_at == null && j.startedAt != null) j.started_at = j.startedAt;
  if (j.ended_at == null && (j.completedAt != null || j.endedAt != null)) {
    j.ended_at = j.completedAt ?? j.endedAt;
  }
  if (j.duration_seconds == null && j.duration != null) {
    j.duration_seconds = typeof j.duration === 'number' ? j.duration : null;
  }
  if (!Array.isArray(j.step_results)) {
    // Legacy uses `steps`; map to slim's `step_results` shape.
    j.step_results = Array.isArray(j.steps) ? j.steps.map(s => ({
      step_id: s.step_id ?? s.stepId ?? null,
      status: s.status ?? 'queued',
      progress: s.progress ?? (s.status === 'completed' ? 100 : 0),
      started_at: s.started_at ?? s.startedAt ?? null,
      ended_at: s.ended_at ?? s.endedAt ?? s.completedAt ?? null,
      error: s.error ?? null,
      log_count: s.log_count ?? s.logCount ?? 0
    })) : [];
  }
  if (j.metrics == null || typeof j.metrics !== 'object') j.metrics = {};
  return j;
}
function normalizeJobList(raw) {
  // Legacy `GET /jobs` lists journey rows under `data.jobs`. The envelope
  // unwrap step exposes either an array of jobs or a wrapping dict.
  if (raw == null) return [];
  const jobs = Array.isArray(raw) ? raw : Array.isArray(raw.jobs) ? raw.jobs : [];
  return jobs.map(j => normalizeJob(j));
}

// Log entry shape:
//   Slim:   [{timestamp, level, message, step_id}]
//   Legacy: nested under `data.logs` or directly at the top, with field
//           names that vary (`step_name` vs `step_id`, `log_message` vs
//           `message`, etc.). The v2 UI streams logs via SSE in real time
//           anyway; this REST fallback just needs to not crash.
function normalizeLogs(raw) {
  if (raw == null) return [];
  let arr = raw;
  if (!Array.isArray(arr)) {
    if (Array.isArray(raw.logs)) arr = raw.logs;else if (raw.data && Array.isArray(raw.data.logs)) arr = raw.data.logs;else if (raw.data && Array.isArray(raw.data)) arr = raw.data;else return [];
  }
  return arr.map(l => ({
    timestamp: l.timestamp ?? l.time ?? l.created_at ?? null,
    level: (l.level ?? 'info').toString().toLowerCase(),
    message: l.message ?? l.log_message ?? l.text ?? '',
    step_id: l.step_id ?? l.stepId ?? l.step_name ?? null
  }));
}

// Normalise a single stage record from either backend shape into the
// canonical UI-facing shape `{id, name, description, status, steps}`.
function normalizeStage(raw) {
  if (raw == null || typeof raw !== 'object') return raw;
  const s = {
    ...raw
  };
  if (s.id == null && s.stage_id != null) s.id = s.stage_id;
  if (s.id == null && s.stageId != null) s.id = s.stageId;
  if (s.name == null && s.id != null) s.name = s.id;
  if (!Array.isArray(s.steps)) s.steps = [];
  // Per-step normalisation — legacy stage records may store steps under
  // `stepId` or omit fields entirely. The v2 UI reads `step.id` / `step.name`.
  s.steps = s.steps.map(st => {
    if (st == null || typeof st !== 'object') return st;
    const out = {
      ...st
    };
    if (out.id == null && out.stepId != null) out.id = out.stepId;
    if (out.id == null && out.step_id != null) out.id = out.step_id;
    if (out.name == null && out.id != null) out.name = out.id;
    return out;
  });
  return s;
}

// Merge step lists from the registered-stage map into a journey's
// stages: when a journey's stage has an empty `steps` array but its
// stage_id is in the registry, copy the registered steps over. Mutates
// nothing — returns a new journey object with new stages.
function enrichJourneyStagesFromRegistry(journey, registeredStages) {
  if (!journey || !Array.isArray(journey.stages)) return journey;
  if (!Array.isArray(registeredStages) || !registeredStages.length) {
    return {
      ...journey,
      stages: journey.stages.map(normalizeStage)
    };
  }
  const byId = new Map(registeredStages.map(r => [r.stage_id, r]));
  const enriched = journey.stages.map(rawStage => {
    const s = normalizeStage(rawStage);
    if (s.steps.length) return s; // journey already supplied steps
    const reg = byId.get(s.id);
    if (!reg) return s; // unregistered stage; nothing to copy
    return {
      ...s,
      // Backfill name / description from the registered class metadata
      // when the persisted stage record left them blank.
      name: s.name || reg.name,
      description: s.description || reg.description,
      steps: (reg.steps || []).map(st => ({
        id: st.id,
        name: st.name,
        description: st.description || ''
      }))
    };
  });
  return {
    ...journey,
    stages: enriched
  };
}

/* ─────────────────────── Utilities ─────────────────────── */

function fmtDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m ? `${m}m ${sec}s` : `${sec}s`;
}
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: '2-digit',
    year: 'numeric'
  });
}
function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  });
}
function fmtShortId(id, n = 8) {
  return id ? String(id).slice(0, n) + '…' : '';
}
function cx(...xs) {
  return xs.filter(Boolean).join(' ');
}

/* ─────────────────────── Toast system ─────────────────────── */

const ToastContext = React.createContext(null);
function ToastProvider({
  children
}) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, type = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, {
      id,
      message,
      type
    }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500);
  }, []);
  return /*#__PURE__*/React.createElement(ToastContext.Provider, {
    value: push
  }, children, /*#__PURE__*/React.createElement("div", {
    className: "toast-stack"
  }, toasts.map(t => /*#__PURE__*/React.createElement("div", {
    key: t.id,
    className: cx('toast', `toast--${t.type}`)
  }, t.message))));
}
function useToast() {
  return React.useContext(ToastContext);
}

/* ─────────────────────── Router ─────────────────────── */

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/');
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || '#/');
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return hash;
}
function navigate(hash) {
  window.location.hash = hash;
}
function parseRoute(hash) {
  const clean = (hash || '#/').replace(/^#/, '');
  const parts = clean.split('/').filter(Boolean);
  if (parts.length === 0) return {
    name: 'journeys'
  };
  if (parts[0] === 'journey' && parts[1] && parts[2] === 'jobs') {
    return {
      name: 'jobs',
      journeyId: parts[1]
    };
  }
  if (parts[0] === 'journey' && parts[1] && parts[2] === 'v2') {
    return {
      name: 'studio_v2',
      journeyId: parts[1]
    };
  }
  if (parts[0] === 'journey' && parts[1]) {
    return {
      name: 'studio',
      journeyId: parts[1]
    };
  }
  if (parts[0] === 'schedules') return {
    name: 'schedules'
  };
  if (parts[0] === 'prompts') return {
    name: 'prompts'
  };
  return {
    name: 'journeys'
  };
}

/* ─────────────────────── Theme (nexus-sre / nexus-ui parity) ─────────────────────── */

function useTheme() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('nexus-ai-engine-theme');
    return saved === 'light' ? 'light' : 'dark';
  });
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('light', 'dark');
    root.classList.add(theme);
    root.style.colorScheme = theme;
    localStorage.setItem('nexus-ai-engine-theme', theme);
  }, [theme]);
  const toggle = useCallback(() => setTheme(t => t === 'dark' ? 'light' : 'dark'), []);
  return {
    theme,
    toggle
  };
}
function NexusLogo({
  className = 'sidebar__logo-svg',
  gradId = 'neLogoGrad'
}) {
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 32 32",
    width: "28",
    height: "28",
    className: className,
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("linearGradient", {
    id: gradId,
    x1: "0%",
    y1: "0%",
    x2: "100%",
    y2: "100%"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0%",
    stopColor: "#7c3aed"
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "100%",
    stopColor: "#4f46e5"
  }))), /*#__PURE__*/React.createElement("path", {
    d: "M16 1 L29 8.5 L29 23.5 L16 31 L3 23.5 L3 8.5 Z",
    fill: `url(#${gradId})`
  }), /*#__PURE__*/React.createElement("path", {
    d: "M16 7 L12 12 L16 17 L20 12 Z",
    fill: "white",
    opacity: "0.9"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M12 14 L9 19 L16 25 L12 18 Z",
    fill: "white",
    opacity: "0.7"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M20 14 L23 19 L16 25 L20 18 Z",
    fill: "white",
    opacity: "0.7"
  }));
}
const ROUTE_TITLES = {
  journeys: 'Journeys',
  studio: 'Journey Studio',
  studio_v2: 'Live view',
  jobs: 'Job history',
  schedules: 'Schedules',
  prompts: 'Prompts'
};
const SIDEBAR_MENU = [{
  label: 'JOURNEY STUDIO',
  items: [{
    id: 'journeys',
    name: 'Journeys',
    hash: '#/',
    routes: ['journeys', 'studio', 'studio_v2', 'jobs'],
    icon: 'grid'
  }, {
    id: 'schedules',
    name: 'Schedules',
    hash: '#/schedules',
    routes: ['schedules'],
    icon: 'clock'
  }, {
    id: 'prompts',
    name: 'Prompts',
    hash: '#/prompts',
    routes: ['prompts'],
    icon: 'file'
  }]
}];
function SidebarIcon({
  name
}) {
  const paths = {
    grid: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
      x: "3",
      y: "3",
      width: "7",
      height: "7"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "14",
      y: "3",
      width: "7",
      height: "7"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "3",
      y: "14",
      width: "7",
      height: "7"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "14",
      y: "14",
      width: "7",
      height: "7"
    })),
    clock: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "9"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M12 7v5l3 2"
    })),
    file: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M14 2v6h6"
    })),
    settings: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "3"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
    })),
    help: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "9"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M9.5 9a2.5 2.5 0 1 1 4.2 1.8c-.8.7-1.7 1.5-1.7 2.7"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "17",
      r: "0.5",
      fill: "currentColor"
    })),
    chevronLeft: /*#__PURE__*/React.createElement("path", {
      d: "M15 6l-6 6 6 6"
    }),
    chevronRight: /*#__PURE__*/React.createElement("path", {
      d: "M9 6l6 6-6 6"
    }),
    sun: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "4"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
    })),
    moon: /*#__PURE__*/React.createElement("path", {
      d: "M21 14.5A8.5 8.5 0 1 1 9.5 3 7 7 0 0 0 21 14.5z"
    })
  };
  return /*#__PURE__*/React.createElement("svg", {
    className: "sidebar__icon",
    viewBox: "0 0 24 24",
    "aria-hidden": "true"
  }, paths[name]);
}
function Sidebar({
  route,
  mini,
  onToggleMini
}) {
  const [helpOpen, setHelpOpen] = useState(false);
  const helpRef = useRef(null);
  useEffect(() => {
    if (!helpOpen) return;
    const close = e => {
      if (helpRef.current && !helpRef.current.contains(e.target)) setHelpOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [helpOpen]);
  const isActive = item => item.routes.includes(route.name);
  return /*#__PURE__*/React.createElement("aside", {
    className: cx('sidebar', mini ? 'sidebar--mini' : 'sidebar--wide'),
    "aria-label": "Primary navigation"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sidebar__head"
  }, /*#__PURE__*/React.createElement(NexusLogo, {
    gradId: mini ? 'neLogoMini' : 'neLogoGrad'
  }), !mini && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "sidebar__brand"
  }, "Nexus AI Engine"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "sidebar__collapse",
    onClick: onToggleMini,
    "aria-label": "Collapse sidebar"
  }, /*#__PURE__*/React.createElement(SidebarIcon, {
    name: "chevronLeft"
  }))), mini && /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "sidebar__collapse sidebar__expand",
    onClick: onToggleMini,
    "aria-label": "Expand sidebar"
  }, /*#__PURE__*/React.createElement(SidebarIcon, {
    name: "chevronRight"
  }))), /*#__PURE__*/React.createElement("nav", {
    className: "sidebar__nav"
  }, SIDEBAR_MENU.map(section => /*#__PURE__*/React.createElement("div", {
    key: section.label
  }, mini ? /*#__PURE__*/React.createElement("div", {
    className: "sidebar__section-divider"
  }) : /*#__PURE__*/React.createElement("div", {
    className: "sidebar__section-label"
  }, section.label), section.items.map(item => /*#__PURE__*/React.createElement("a", {
    key: item.id,
    href: item.hash,
    className: cx('sidebar__item', isActive(item) && 'sidebar__item--active'),
    title: mini ? item.name : undefined
  }, /*#__PURE__*/React.createElement(SidebarIcon, {
    name: item.icon
  }), !mini && /*#__PURE__*/React.createElement("span", null, item.name)))))), /*#__PURE__*/React.createElement("div", {
    className: "sidebar__footer"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "sidebar__item",
    title: mini ? 'Settings' : undefined,
    onClick: () => window.alert('Settings are not available in the embedded dev UI (v0.2.0-alpha). Use port-forward for local testing.')
  }, /*#__PURE__*/React.createElement(SidebarIcon, {
    name: "settings"
  }), !mini && /*#__PURE__*/React.createElement("span", null, "Settings")), /*#__PURE__*/React.createElement("div", {
    className: "sidebar__help-wrap",
    ref: helpRef
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "sidebar__item",
    title: mini ? 'Help' : undefined,
    onClick: () => setHelpOpen(o => !o)
  }, /*#__PURE__*/React.createElement(SidebarIcon, {
    name: "help"
  }), !mini && /*#__PURE__*/React.createElement("span", null, "Help")), helpOpen && /*#__PURE__*/React.createElement("div", {
    className: "sidebar__popover"
  }, /*#__PURE__*/React.createElement("a", {
    href: "/health",
    target: "_blank",
    rel: "noopener noreferrer"
  }, "API health"), /*#__PURE__*/React.createElement("a", {
    href: "/version",
    target: "_blank",
    rel: "noopener noreferrer"
  }, "Version info"), /*#__PURE__*/React.createElement("a", {
    href: "/metrics",
    target: "_blank",
    rel: "noopener noreferrer"
  }, "Metrics")))));
}
function AppHeader({
  route,
  theme,
  onToggleTheme,
  version
}) {
  return /*#__PURE__*/React.createElement("header", {
    className: "app-header"
  }, /*#__PURE__*/React.createElement("h1", {
    className: "app-header__title"
  }, ROUTE_TITLES[route.name] || 'Journey Studio'), /*#__PURE__*/React.createElement("div", {
    className: "app-header__utilities"
  }, /*#__PURE__*/React.createElement("span", {
    className: "env-badge"
  }, "dev UI"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "app-header__btn",
    onClick: onToggleTheme,
    title: "Toggle theme",
    "aria-label": "Toggle theme"
  }, /*#__PURE__*/React.createElement(SidebarIcon, {
    name: theme === 'dark' ? 'sun' : 'moon'
  })), /*#__PURE__*/React.createElement("span", {
    className: "version-badge"
  }, "v", version)));
}
function AppShell({
  route,
  children
}) {
  const {
    theme,
    toggle
  } = useTheme();
  const [mini, setMini] = useState(() => localStorage.getItem('nexus-ai-engine-sidebar') === 'mini');
  const [version, setVersion] = useState('…');
  useEffect(() => {
    fetch('/version').then(r => r.json()).then(v => setVersion(v.version)).catch(() => {});
  }, []);
  useEffect(() => {
    localStorage.setItem('nexus-ai-engine-sidebar', mini ? 'mini' : 'wide');
  }, [mini]);
  return /*#__PURE__*/React.createElement("div", {
    className: "app-shell"
  }, /*#__PURE__*/React.createElement(Sidebar, {
    route: route,
    mini: mini,
    onToggleMini: () => setMini(m => !m)
  }), /*#__PURE__*/React.createElement("div", {
    className: "app-shell__body"
  }, /*#__PURE__*/React.createElement(AppHeader, {
    route: route,
    theme: theme,
    onToggleTheme: toggle,
    version: version
  }), /*#__PURE__*/React.createElement("main", {
    className: "app-main"
  }, children)));
}

/* ─────────────────────── Journeys list ─────────────────────── */

function JourneysListPage() {
  const [journeys, setJourneys] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [capabilityFilter, setCapabilityFilter] = useState('');
  const toast = useToast();
  const load = useCallback(() => {
    setError(null);
    api.listJourneys({}).then(data => setJourneys(data)).catch(e => setError(e.message));
  }, []);
  useEffect(load, [load]);
  const capabilities = useMemo(() => {
    const s = new Set();
    (journeys || []).forEach(j => j.capability && s.add(j.capability));
    return Array.from(s).sort();
  }, [journeys]);
  const filtered = useMemo(() => {
    if (!journeys) return [];
    const q = query.toLowerCase();
    return journeys.filter(j => {
      if (q && !`${j.name} ${j.id} ${j.capability || ''}`.toLowerCase().includes(q)) return false;
      if (statusFilter && j.status !== statusFilter) return false;
      if (capabilityFilter && j.capability !== capabilityFilter) return false;
      return true;
    });
  }, [journeys, query, statusFilter, capabilityFilter]);
  const onDelete = useCallback(j => {
    if (!window.confirm(`Delete journey "${j.name}"?`)) return;
    api.deleteJourney(j.id).then(() => {
      toast('Journey deleted', 'success');
      load();
    }).catch(e => toast(`Delete failed: ${e.message}`, 'error'));
  }, [load, toast]);
  const onClone = useCallback(j => {
    api.cloneJourney(j.id).then(() => {
      toast('Journey cloned', 'success');
      load();
    }).catch(e => toast(`Clone failed: ${e.message}`, 'error'));
  }, [load, toast]);
  const onNewJourney = useCallback(() => {
    const name = window.prompt('Journey name?');
    if (!name) return;
    api.createJourney({
      name,
      description: null,
      capability: 'custom'
    }).then(() => {
      toast('Journey created', 'success');
      load();
    }).catch(e => toast(`Create failed: ${e.message}`, 'error'));
  }, [load, toast]);
  if (error) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "Could not load journeys"), /*#__PURE__*/React.createElement("p", {
    className: "mono"
  }, error)));
  if (!journeys) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "Loading…"));
  return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "page-header"
  }, /*#__PURE__*/React.createElement("h1", {
    className: "page-header__title"
  }, "Journeys"), /*#__PURE__*/React.createElement("p", {
    className: "page-header__subtitle"
  }, "Browse, filter, and open DSL-defined execution journeys")), /*#__PURE__*/React.createElement("div", {
    className: "filter-bar"
  }, /*#__PURE__*/React.createElement("input", {
    className: "input",
    placeholder: "Search journeys…",
    value: query,
    onChange: e => setQuery(e.target.value)
  }), /*#__PURE__*/React.createElement("select", {
    className: "select",
    value: statusFilter,
    onChange: e => setStatusFilter(e.target.value)
  }, /*#__PURE__*/React.createElement("option", {
    value: ""
  }, "All statuses"), /*#__PURE__*/React.createElement("option", {
    value: "created"
  }, "Created"), /*#__PURE__*/React.createElement("option", {
    value: "running"
  }, "Running"), /*#__PURE__*/React.createElement("option", {
    value: "completed"
  }, "Completed"), /*#__PURE__*/React.createElement("option", {
    value: "failed"
  }, "Failed"), /*#__PURE__*/React.createElement("option", {
    value: "cancelled"
  }, "Cancelled")), /*#__PURE__*/React.createElement("select", {
    className: "select",
    value: capabilityFilter,
    onChange: e => setCapabilityFilter(e.target.value)
  }, /*#__PURE__*/React.createElement("option", {
    value: ""
  }, "All capabilities"), capabilities.map(c => /*#__PURE__*/React.createElement("option", {
    key: c,
    value: c
  }, c))), /*#__PURE__*/React.createElement("div", {
    className: "grow"
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--primary",
    onClick: onNewJourney
  }, "+ New Journey"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: load,
    title: "Refresh"
  }, "↻")), filtered.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "No journeys"), /*#__PURE__*/React.createElement("p", null, "Create one to get started.")) : /*#__PURE__*/React.createElement("div", {
    className: "cards-grid"
  }, filtered.map(j => /*#__PURE__*/React.createElement(JourneyCard, {
    key: j.id,
    journey: j,
    onOpen: () => navigate(`#/journey/${j.id}`),
    onDelete: () => onDelete(j),
    onClone: () => onClone(j)
  }))));
}
function JourneyCard({
  journey,
  onOpen,
  onDelete,
  onClone
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "card card--clickable",
    onClick: onOpen
  }, /*#__PURE__*/React.createElement("div", {
    className: "card__title"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "card__name"
  }, journey.name), /*#__PURE__*/React.createElement("div", {
    className: "card__id"
  }, fmtShortId(journey.id))), /*#__PURE__*/React.createElement("span", {
    className: cx('pill', `pill--${journey.status}`)
  }, journey.status)), /*#__PURE__*/React.createElement("div", {
    className: "card__metrics"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "metric__value"
  }, journey.jobs_total), /*#__PURE__*/React.createElement("div", {
    className: "metric__label"
  }, "Jobs")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "metric__value metric__value--done"
  }, journey.jobs_done), /*#__PURE__*/React.createElement("div", {
    className: "metric__label"
  }, "Done")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "metric__value metric__value--running"
  }, journey.jobs_running), /*#__PURE__*/React.createElement("div", {
    className: "metric__label"
  }, "Running")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "metric__value metric__value--failed"
  }, journey.jobs_failed), /*#__PURE__*/React.createElement("div", {
    className: "metric__label"
  }, "Failed"))), /*#__PURE__*/React.createElement("div", {
    className: "card__kpis"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "card__kpi--value"
  }, (journey.success_rate ?? 0).toFixed(0), "%"), " ", /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, "Success")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "card__kpi--value"
  }, fmtDuration(journey.avg_duration_seconds)), " ", /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, "Avg dur"))), /*#__PURE__*/React.createElement("div", {
    className: "card__footer"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, journey.capability || '—'), /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, " · ", fmtDate(journey.created_at))), /*#__PURE__*/React.createElement("div", {
    className: "row",
    onClick: e => e.stopPropagation()
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost btn--small",
    onClick: onClone,
    title: "Clone"
  }, "⧉"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--danger btn--small",
    onClick: onDelete,
    title: "Delete"
  }, "Delete"))));
}

/* ─────────────────────── Journey studio (detail) ─────────────────────── */

function JourneyStudioPage({
  journeyId
}) {
  const [journey, setJourney] = useState(null);
  const [aggregate, setAggregate] = useState(null);
  const [activeStageId, setActiveStageId] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [error, setError] = useState(null);
  const [logsJobId, setLogsJobId] = useState(null);
  const toast = useToast();
  const load = useCallback(async () => {
    try {
      const [j, agg, sch, registry] = await Promise.all([api.getJourney(journeyId), api.aggregateReport(journeyId).catch(() => null), api.listSchedules(journeyId).catch(() => []), api.listRegisteredStages().catch(() => ({
        stages: []
      }))]);
      const enriched = enrichJourneyStagesFromRegistry(j, registry?.stages || []);
      setJourney(enriched);
      setAggregate(agg);
      setSchedules(sch);
      if (enriched.stages.length && !activeStageId) setActiveStageId(enriched.stages[0].id);
    } catch (e) {
      setError(e.message);
    }
  }, [journeyId, activeStageId]);
  useEffect(() => {
    load();
  }, [load]);
  const activeStage = useMemo(() => (journey?.stages || []).find(s => s.id === activeStageId) || null, [journey, activeStageId]);
  const scheduleForStage = useMemo(() => schedules.find(s => s.stage_id === activeStageId), [schedules, activeStageId]);
  const onStartStage = useCallback(async () => {
    if (!activeStage) return;
    try {
      const job = await api.runJob(journey.id, activeStage.id, 'manual run from studio');
      toast(`Job ${fmtShortId(job.id)} started`, 'success');
      setLogsJobId(job.id);
      load();
    } catch (e) {
      toast(`Run failed: ${e.message}`, 'error');
    }
  }, [activeStage, journey, toast, load]);
  if (error) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "Could not load journey"), /*#__PURE__*/React.createElement("p", {
    className: "mono"
  }, error)));
  if (!journey) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "Loading…"));
  return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "row mt-12",
    style: {
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: () => navigate('#/')
  }, "← Back"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 20,
      fontWeight: 700
    }
  }, journey.name), /*#__PURE__*/React.createElement("span", {
    className: "mono muted",
    style: {
      marginLeft: 10
    }
  }, fmtShortId(journey.id, 12)))), /*#__PURE__*/React.createElement("div", {
    className: "row"
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn--primary",
    onClick: () => navigate(`#/journey/${journey.id}/v2`),
    title: "GitHub-Actions-style live view (preview)"
  }, "↗ Open v2 view"), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => navigate(`#/journey/${journey.id}/jobs`)
  }, "View All Jobs"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: load
  }, "↻ Refresh"))), /*#__PURE__*/React.createElement("div", {
    className: "stats-row mt-20"
  }, /*#__PURE__*/React.createElement(StatCard, {
    label: "Total Jobs",
    value: journey.jobs_total ?? 0
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Success Rate",
    value: `${(journey.success_rate ?? 0).toFixed(0)}%`
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Avg Duration",
    value: fmtDuration(journey.avg_duration_seconds)
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Calls Processed",
    value: aggregate ? aggregate.total_calls_processed : '—'
  })), /*#__PURE__*/React.createElement("div", {
    className: "studio mt-20"
  }, /*#__PURE__*/React.createElement("div", {
    className: "studio__sidebar"
  }, /*#__PURE__*/React.createElement("h3", null, "Processing Stages"), journey.stages.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.id,
    className: cx('stage-entry', s.id === activeStageId && 'stage-entry--active'),
    onClick: () => setActiveStageId(s.id)
  }, /*#__PURE__*/React.createElement("div", {
    className: "stage-entry__name"
  }, s.name), /*#__PURE__*/React.createElement("div", {
    className: "stage-entry__meta"
  }, /*#__PURE__*/React.createElement("span", {
    className: cx('pill', `pill--${s.status}`)
  }, s.status), /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, " · ", s.steps.length, " step", s.steps.length === 1 ? '' : 's'))))), /*#__PURE__*/React.createElement("div", {
    className: "studio__main"
  }, !activeStage ? /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "No stages yet")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "stage-header"
  }, /*#__PURE__*/React.createElement("div", {
    className: "stage-header__title"
  }, activeStage.name), activeStage.description && /*#__PURE__*/React.createElement("div", {
    className: "stage-header__desc"
  }, activeStage.description), /*#__PURE__*/React.createElement("div", {
    className: "stage-header__actions"
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn--primary",
    onClick: onStartStage
  }, "▶ Start Processing"), scheduleForStage ? /*#__PURE__*/React.createElement("span", {
    className: cx('pill', scheduleForStage.enabled ? 'pill--running' : 'pill--paused')
  }, "Every ", scheduleForStage.interval_minutes, "m · next ", fmtTime(scheduleForStage.next_run_at)) : /*#__PURE__*/React.createElement("span", {
    className: "pill pill--pending"
  }, "No schedule"), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => navigate(`#/journey/${journey.id}/jobs`)
  }, "View All Jobs"))), /*#__PURE__*/React.createElement("div", {
    className: "steps-list"
  }, /*#__PURE__*/React.createElement("div", {
    className: "steps-list__header"
  }, "Stage Steps"), activeStage.steps.map((step, i) => /*#__PURE__*/React.createElement("div", {
    key: step.id,
    className: "step-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "step-row__num"
  }, i + 1), /*#__PURE__*/React.createElement("div", {
    className: "step-row__body"
  }, /*#__PURE__*/React.createElement("div", {
    className: "step-row__name"
  }, step.name), step.description && /*#__PURE__*/React.createElement("div", {
    className: "step-row__desc"
  }, step.description)), /*#__PURE__*/React.createElement("div", {
    className: "muted mono"
  }, step.id))))))), logsJobId && /*#__PURE__*/React.createElement(LogsDrawer, {
    journeyId: journey.id,
    jobId: logsJobId,
    onClose: () => {
      setLogsJobId(null);
      load();
    }
  }));
}
function StatCard({
  label,
  value
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "stat-card"
  }, /*#__PURE__*/React.createElement("div", {
    className: "stat-card__label"
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "stat-card__value"
  }, value));
}

/* ─────────────────────── Job history ─────────────────────── */

function JobHistoryPage({
  journeyId
}) {
  const [journey, setJourney] = useState(null);
  const [jobs, setJobs] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [activeStageId, setActiveStageId] = useState(null);
  const [logsJobId, setLogsJobId] = useState(null);
  const [error, setError] = useState(null);
  const toast = useToast();
  const load = useCallback(async () => {
    try {
      const [j, js, ss, registry] = await Promise.all([api.getJourney(journeyId), api.listJobs(journeyId), api.listSchedules(journeyId).catch(() => []), api.listRegisteredStages().catch(() => ({
        stages: []
      }))]);
      const enriched = enrichJourneyStagesFromRegistry(j, registry?.stages || []);
      setJourney(enriched);
      setJobs(js);
      setSchedules(ss);
      if (enriched.stages.length && !activeStageId) setActiveStageId(enriched.stages[0].id);
    } catch (e) {
      setError(e.message);
    }
  }, [journeyId, activeStageId]);
  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh while any job is running
  useEffect(() => {
    if (!jobs) return;
    const hasRunning = jobs.some(j => j.status === 'running' || j.status === 'queued');
    if (!hasRunning) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [jobs, load]);
  const filteredJobs = useMemo(() => (jobs || []).filter(j => !activeStageId || j.stage_id === activeStageId), [jobs, activeStageId]);
  const onCancel = useCallback(async job => {
    try {
      await api.cancelJob(journeyId, job.id);
      toast('Cancelled', 'success');
      load();
    } catch (e) {
      toast(`Cancel failed: ${e.message}`, 'error');
    }
  }, [journeyId, toast, load]);
  const onRetry = useCallback(async job => {
    try {
      const newJob = await api.retryJob(journeyId, job.id);
      toast(`Retry started: ${fmtShortId(newJob.id)}`, 'success');
      setLogsJobId(newJob.id);
      load();
    } catch (e) {
      toast(`Retry failed: ${e.message}`, 'error');
    }
  }, [journeyId, toast, load]);
  if (error) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "Could not load jobs"), /*#__PURE__*/React.createElement("p", {
    className: "mono"
  }, error)));
  if (!journey || !jobs) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "Loading…"));
  return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "row mt-12",
    style: {
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: () => navigate(`#/journey/${journey.id}`)
  }, "← Back to Studio"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 12,
      fontSize: 18,
      fontWeight: 700
    }
  }, journey.name, ": Jobs")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: load
  }, "↻ Refresh")), /*#__PURE__*/React.createElement("div", {
    className: "studio mt-20"
  }, /*#__PURE__*/React.createElement("div", {
    className: "studio__sidebar"
  }, /*#__PURE__*/React.createElement("h3", null, "Processing Stages"), journey.stages.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.id,
    className: cx('stage-entry', s.id === activeStageId && 'stage-entry--active'),
    onClick: () => setActiveStageId(s.id)
  }, /*#__PURE__*/React.createElement("div", {
    className: "stage-entry__name"
  }, s.name), /*#__PURE__*/React.createElement("div", {
    className: "stage-entry__meta"
  }, /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, jobs.filter(j => j.stage_id === s.id).length, " jobs"))))), /*#__PURE__*/React.createElement("div", {
    className: "studio__main"
  }, /*#__PURE__*/React.createElement("div", {
    className: "table-wrap"
  }, /*#__PURE__*/React.createElement("h3", null, "Job history"), /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Run"), /*#__PURE__*/React.createElement("th", null, "Started"), /*#__PURE__*/React.createElement("th", {
    className: "numeric"
  }, "Calls"), /*#__PURE__*/React.createElement("th", {
    className: "numeric"
  }, "Errors"), /*#__PURE__*/React.createElement("th", {
    className: "numeric"
  }, "Warnings"), /*#__PURE__*/React.createElement("th", {
    className: "numeric"
  }, "Duration"), /*#__PURE__*/React.createElement("th", null, "Status"), /*#__PURE__*/React.createElement("th", null))), /*#__PURE__*/React.createElement("tbody", null, filteredJobs.length === 0 ? /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
    colSpan: "8",
    className: "muted",
    style: {
      padding: 30,
      textAlign: 'center'
    }
  }, "No jobs yet for this stage.")) : filteredJobs.map(job => /*#__PURE__*/React.createElement("tr", {
    key: job.id,
    className: "row--clickable",
    onClick: () => setLogsJobId(job.id)
  }, /*#__PURE__*/React.createElement("td", {
    className: "mono"
  }, "#", job.execution_number), /*#__PURE__*/React.createElement("td", {
    className: "muted"
  }, fmtDate(job.started_at), " ", fmtTime(job.started_at)), /*#__PURE__*/React.createElement("td", {
    className: "numeric"
  }, job.metrics?.calls_processed ?? 0), /*#__PURE__*/React.createElement("td", {
    className: cx('numeric', job.metrics?.errors ? 'red' : 'muted')
  }, job.metrics?.errors ?? 0), /*#__PURE__*/React.createElement("td", {
    className: cx('numeric', job.metrics?.warnings ? 'orange' : 'muted')
  }, job.metrics?.warnings ?? 0), /*#__PURE__*/React.createElement("td", {
    className: "numeric"
  }, fmtDuration(job.duration_seconds)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
    className: cx('pill', `pill--${job.status}`)
  }, job.status)), /*#__PURE__*/React.createElement("td", {
    className: "row",
    style: {
      gap: 6
    },
    onClick: e => e.stopPropagation()
  }, (job.status === 'running' || job.status === 'queued') && /*#__PURE__*/React.createElement("button", {
    className: "btn btn--small btn--danger",
    onClick: () => onCancel(job)
  }, "Cancel"), (job.status === 'failed' || job.status === 'cancelled') && /*#__PURE__*/React.createElement("button", {
    className: "btn btn--small",
    onClick: () => onRetry(job)
  }, "Retry"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--small btn--ghost",
    onClick: () => setLogsJobId(job.id)
  }, "Logs"))))))), /*#__PURE__*/React.createElement(SchedulesPanel, {
    journey: journey,
    schedules: schedules,
    onChange: load
  }))), logsJobId && /*#__PURE__*/React.createElement(LogsDrawer, {
    journeyId: journey.id,
    jobId: logsJobId,
    onClose: () => {
      setLogsJobId(null);
      load();
    }
  }));
}

/* ─────────────────────── Schedules ─────────────────────── */

function SchedulesPanel({
  journey,
  schedules,
  onChange
}) {
  const toast = useToast();
  const onToggle = useCallback(s => {
    api.updateSchedule(s.id, {
      enabled: !s.enabled
    }).then(() => {
      toast(!s.enabled ? 'Schedule enabled' : 'Schedule paused', 'success');
      onChange();
    }).catch(e => toast(`Update failed: ${e.message}`, 'error'));
  }, [onChange, toast]);
  const onRunNow = useCallback(s => {
    api.runScheduleNow(s.id).then(() => {
      toast('Triggered', 'success');
      onChange();
    }).catch(e => toast(`Run failed: ${e.message}`, 'error'));
  }, [onChange, toast]);
  const onDelete = useCallback(s => {
    if (!window.confirm('Delete this schedule?')) return;
    api.deleteSchedule(s.id).then(() => {
      toast('Deleted', 'success');
      onChange();
    }).catch(e => toast(`Delete failed: ${e.message}`, 'error'));
  }, [onChange, toast]);
  const onNew = useCallback(() => {
    if (!journey || !journey.stages.length) return;
    const stage = journey.stages[0];
    const mins = parseInt(window.prompt(`Interval in minutes for stage "${stage.name}"?`, '15'), 10);
    if (!mins) return;
    api.createSchedule({
      journey_id: journey.id,
      stage_id: stage.id,
      interval_minutes: mins,
      enabled: true
    }).then(() => {
      toast('Schedule created', 'success');
      onChange();
    }).catch(e => toast(`Create failed: ${e.message}`, 'error'));
  }, [journey, onChange, toast]);
  return /*#__PURE__*/React.createElement("div", {
    className: "table-wrap mt-20"
  }, /*#__PURE__*/React.createElement("div", {
    className: "row",
    style: {
      justifyContent: 'space-between',
      padding: '14px 16px',
      borderBottom: '1px solid var(--border)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 700
    }
  }, "Batch Schedules"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--small",
    onClick: onNew
  }, "+ New Schedule")), /*#__PURE__*/React.createElement("div", {
    className: "schedules-grid schedules-grid--head"
  }, /*#__PURE__*/React.createElement("div", null, "Stage"), /*#__PURE__*/React.createElement("div", null, "Interval"), /*#__PURE__*/React.createElement("div", null, "Last run"), /*#__PURE__*/React.createElement("div", null, "Next run"), /*#__PURE__*/React.createElement("div", null, "Status"), /*#__PURE__*/React.createElement("div", null, "Actions")), schedules.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "muted",
    style: {
      padding: 20,
      textAlign: 'center'
    }
  }, "No schedules.") : schedules.map(s => {
    const stage = journey?.stages.find(x => x.id === s.stage_id);
    return /*#__PURE__*/React.createElement("div", {
      key: s.id,
      className: "schedules-grid"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", null, stage?.name || s.stage_id), /*#__PURE__*/React.createElement("div", {
      className: "muted mono",
      style: {
        fontSize: 11
      }
    }, fmtShortId(s.id, 10))), /*#__PURE__*/React.createElement("div", null, "Every ", s.interval_minutes, "m"), /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, s.last_run_at ? `${fmtDate(s.last_run_at)} ${fmtTime(s.last_run_at)}` : '—'), /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, s.next_run_at ? `${fmtDate(s.next_run_at)} ${fmtTime(s.next_run_at)}` : '—'), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("button", {
      className: cx('toggle', s.enabled && 'toggle--on'),
      title: s.enabled ? 'Enabled' : 'Paused',
      onClick: () => onToggle(s)
    })), /*#__PURE__*/React.createElement("div", {
      className: "row",
      style: {
        gap: 6
      }
    }, /*#__PURE__*/React.createElement("button", {
      className: "btn btn--small",
      onClick: () => onRunNow(s)
    }, "Run now"), /*#__PURE__*/React.createElement("button", {
      className: "btn btn--small btn--danger",
      onClick: () => onDelete(s)
    }, "Delete")));
  }));
}
function SchedulesPage() {
  const [journeys, setJourneys] = useState([]);
  const [schedules, setSchedules] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(async () => {
    try {
      const [js, ss] = await Promise.all([api.listJourneys({}), api.listSchedules()]);
      setJourneys(js);
      setSchedules(ss);
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  if (error) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "Could not load schedules"), /*#__PURE__*/React.createElement("p", {
    className: "mono"
  }, error)));
  if (!schedules) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "Loading…"));
  if (schedules.length === 0) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "No schedules"), /*#__PURE__*/React.createElement("p", null, "Create one from a journey's Job History page.")));
  const grouped = journeys.map(j => ({
    j,
    items: schedules.filter(s => s.journey_id === j.id)
  })).filter(g => g.items.length);
  return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "page-header"
  }, /*#__PURE__*/React.createElement("h1", {
    className: "page-header__title"
  }, "Schedules"), /*#__PURE__*/React.createElement("p", {
    className: "page-header__subtitle"
  }, "Batch schedules across all journeys")), /*#__PURE__*/React.createElement("div", {
    className: "row",
    style: {
      justifyContent: 'flex-end'
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost btn--small",
    onClick: load
  }, "↻ Refresh")), /*#__PURE__*/React.createElement("div", {
    className: "col mt-20"
  }, grouped.map(({
    j,
    items
  }) => /*#__PURE__*/React.createElement("div", {
    key: j.id
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      margin: '18px 0 8px 0',
      fontWeight: 700
    }
  }, j.name), /*#__PURE__*/React.createElement(SchedulesPanel, {
    journey: j,
    schedules: items,
    onChange: load
  })))));
}

/* ─────────────────────── Prompts ─────────────────────── */

function PromptsPage() {
  const [prompts, setPrompts] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [draft, setDraft] = useState('');
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState(null);
  const toast = useToast();
  const load = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([api.listPrompts(), api.promptAudit(50).catch(() => [])]);
      setPrompts(p);
      setAudit(a);
      if (p.length && !activeId) setActiveId(p[0].id);
    } catch (e) {
      setError(e.message);
    }
  }, [activeId]);
  useEffect(() => {
    load();
  }, [load]);
  const active = useMemo(() => (prompts || []).find(p => p.id === activeId), [prompts, activeId]);
  useEffect(() => {
    setDraft(active?.content || '');
  }, [active?.id, active?.content]);
  const onSave = useCallback(async () => {
    if (!active) return;
    try {
      await api.updatePrompt(active.id, {
        content: draft,
        note: 'edit via UI'
      });
      toast('Prompt saved', 'success');
      load();
    } catch (e) {
      toast(`Save failed: ${e.message}`, 'error');
    }
  }, [active, draft, load, toast]);
  const onReset = useCallback(async () => {
    if (!window.confirm('Reset ALL prompts to defaults?')) return;
    try {
      await api.resetPrompts();
      toast('Prompts reset', 'success');
      load();
    } catch (e) {
      toast(`Reset failed: ${e.message}`, 'error');
    }
  }, [load, toast]);
  if (error) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "Could not load prompts"), /*#__PURE__*/React.createElement("p", {
    className: "mono"
  }, error)));
  if (!prompts) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "Loading…"));
  return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "page-header row",
    style: {
      justifyContent: 'space-between',
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    className: "page-header__title"
  }, "Prompts"), /*#__PURE__*/React.createElement("p", {
    className: "page-header__subtitle"
  }, "System prompt templates and version history")), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--danger btn--small",
    onClick: onReset
  }, "Reset all to defaults")), /*#__PURE__*/React.createElement("div", {
    className: "prompt-editor mt-20"
  }, /*#__PURE__*/React.createElement("div", {
    className: "prompt-list"
  }, prompts.map(p => /*#__PURE__*/React.createElement("div", {
    key: p.id,
    className: cx('prompt-list__item', p.id === activeId && 'prompt-list__item--active'),
    onClick: () => setActiveId(p.id)
  }, /*#__PURE__*/React.createElement("div", {
    className: "prompt-list__name"
  }, p.name), /*#__PURE__*/React.createElement("div", {
    className: "prompt-list__desc"
  }, p.type, " · v", p.version, p.is_default ? ' · default' : '')))), /*#__PURE__*/React.createElement("div", {
    className: "prompt-editor__main"
  }, active ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "row",
    style: {
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 700
    }
  }, active.name), /*#__PURE__*/React.createElement("div", {
    className: "muted",
    style: {
      fontSize: 12
    }
  }, active.description)), /*#__PURE__*/React.createElement("div", {
    className: "muted mono",
    style: {
      fontSize: 12
    }
  }, active.type, " · v", active.version, " · updated ", fmtDate(active.updated_at))), /*#__PURE__*/React.createElement("textarea", {
    className: "prompt-content",
    value: draft,
    onChange: e => setDraft(e.target.value)
  }), /*#__PURE__*/React.createElement("div", {
    className: "row",
    style: {
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "muted",
    style: {
      fontSize: 12
    }
  }, draft.length, " chars · ", draft !== active.content ? 'unsaved changes' : 'no changes'), /*#__PURE__*/React.createElement("div", {
    className: "row"
  }, /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => setDraft(active.content),
    disabled: draft === active.content
  }, "Discard"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--primary",
    onClick: onSave,
    disabled: draft === active.content
  }, "Save"))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 24,
      fontSize: 13,
      fontWeight: 700
    }
  }, "Audit log"), /*#__PURE__*/React.createElement("div", {
    className: "col gap-sm",
    style: {
      maxHeight: 220,
      overflowY: 'auto'
    }
  }, audit.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "muted"
  }, "No audit entries.") : audit.map((a, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "muted mono",
    style: {
      fontSize: 11
    }
  }, fmtDate(a.timestamp), " ", fmtTime(a.timestamp), " · ", a.action, " · ", a.prompt_id, a.note && ` · ${a.note}`)))) : /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "No prompt selected."))));
}

/* ─────────────────────── Logs drawer (SSE) ─────────────────────── */

function LogsDrawer({
  journeyId,
  jobId,
  onClose
}) {
  const [logs, setLogs] = useState([]);
  const [job, setJob] = useState(null);
  const [status, setStatus] = useState('connecting');
  const endRef = useRef(null);
  useEffect(() => {
    let cancelled = false;
    api.getJob(journeyId, jobId).then(j => !cancelled && setJob(j)).catch(() => {});
    api.jobLogs(journeyId, jobId).then(ls => !cancelled && setLogs(ls)).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [journeyId, jobId]);

  // Poll status, and (if running) open an EventSource for live events.
  useEffect(() => {
    if (!job) return;
    if (job.status !== 'running' && job.status !== 'queued') {
      setStatus(job.status);
      return;
    }
    setStatus('running');
    const es = new EventSource(`/api/v1/journeys/${journeyId}/jobs/${jobId}/stream`);
    es.onmessage = evt => {
      try {
        const payload = JSON.parse(evt.data);
        if (payload.type === 'task_progress' && payload.data && payload.data.message) {
          setLogs(prev => [...prev, {
            timestamp: payload.timestamp,
            level: 'INFO',
            message: payload.data.message,
            step_id: payload.step_id
          }]);
        } else if (payload.type === 'step_status') {
          setLogs(prev => [...prev, {
            timestamp: payload.timestamp,
            level: payload.data?.status === 'failed' ? 'ERROR' : 'INFO',
            message: `step ${payload.step_id}: ${payload.data?.status}${payload.data?.error ? ` (${payload.data.error})` : ''}`,
            step_id: payload.step_id
          }]);
        } else if (payload.type === 'job_complete') {
          setStatus(payload.data?.status || 'completed');
          es.close();
          api.jobLogs(journeyId, jobId).then(setLogs).catch(() => {});
          api.getJob(journeyId, jobId).then(setJob).catch(() => {});
        }
      } catch (_) {}
    };
    es.onerror = () => {
      setStatus('disconnected');
      es.close();
    };
    return () => es.close();
  }, [job, journeyId, jobId]);
  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: 'smooth'
    });
  }, [logs.length]);
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "drawer__backdrop",
    onClick: onClose
  }), /*#__PURE__*/React.createElement("div", {
    className: "drawer"
  }, /*#__PURE__*/React.createElement("div", {
    className: "drawer__header"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "drawer__title"
  }, "Job logs · ", /*#__PURE__*/React.createElement("span", {
    className: "mono"
  }, fmtShortId(jobId, 14))), /*#__PURE__*/React.createElement("div", {
    className: "drawer__subtitle"
  }, job ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: cx('pill', `pill--${status}`)
  }, status), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 8
    }
  }, job.stage_name), job.duration_seconds != null && /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, " · ", fmtDuration(job.duration_seconds))) : 'Loading…')), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: onClose
  }, "Close")), /*#__PURE__*/React.createElement("div", {
    className: "drawer__body"
  }, logs.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "muted"
  }, "No log lines yet.") : logs.map((l, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: cx('log-line', l.level === 'ERROR' && 'log-line--error', l.level === 'WARNING' && 'log-line--warning')
  }, /*#__PURE__*/React.createElement("span", {
    className: "log-line__time"
  }, fmtTime(l.timestamp)), ' ', l.step_id && /*#__PURE__*/React.createElement("span", {
    className: "log-line__step"
  }, "[", l.step_id, "]"), ' ', l.message)), /*#__PURE__*/React.createElement("div", {
    ref: endRef
  }))));
}

/* ─────────────────────── Journey studio V2 (GitHub-Actions style) ─────────────────────── */

const STEP_STATUS_PENDING = 'pending';
const STEP_STATUS_RUNNING = 'running';
const STEP_STATUS_COMPLETED = 'completed';
const STEP_STATUS_FAILED = 'failed';
const LEVEL_ORDER = ['debug', 'info', 'warn', 'warning', 'error'];
function fmtTimeMs(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  const ms = String(d.getMilliseconds()).padStart(3, '0');
  return `${hh}:${mm}:${ss}.${ms}`;
}
function normalizeLevel(level) {
  const l = (level || 'info').toLowerCase();
  if (l === 'warning') return 'warn';
  return l;
}

/* StepConsoleV2 — GitHub-Actions-style inline terminal for one step's logs.
 * Pure presentational; parent owns log state and passes it in. */
function StepConsoleV2({
  stepId,
  stepName,
  status,
  logs,
  levelFilter,
  onLevelFilterChange
}) {
  const scrollRef = useRef(null);
  const [followTail, setFollowTail] = useState(true);
  const [copyState, setCopyState] = useState('idle');
  const filtered = useMemo(() => {
    if (!levelFilter || levelFilter === 'all') return logs;
    return logs.filter(l => {
      const lv = normalizeLevel(l.level);
      if (levelFilter === 'warn') return lv === 'warn';
      if (levelFilter === 'error') return lv === 'error';
      if (levelFilter === 'info') return lv === 'info' || lv === 'debug';
      return true;
    });
  }, [logs, levelFilter]);
  useEffect(() => {
    if (!followTail) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [filtered.length, followTail]);
  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 12;
    setFollowTail(atBottom);
  }, []);
  const onCopy = useCallback(() => {
    const text = filtered.map(l => `${fmtTimeMs(l.timestamp)} [${(l.level || 'INFO').toUpperCase()}] ${l.message}`).join('\n');
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopyState('copied');
        setTimeout(() => setCopyState('idle'), 1200);
      }, () => setCopyState('idle'));
    }
  }, [filtered]);
  const onDownload = useCallback(() => {
    const text = filtered.map(l => `${fmtTimeMs(l.timestamp)} [${(l.level || 'INFO').toUpperCase()}] ${l.message}`).join('\n');
    const blob = new Blob([text], {
      type: 'text/plain'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(stepName || stepId || 'step').toLowerCase().replace(/[^a-z0-9-_]+/g, '-')}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filtered, stepId, stepName]);
  const jumpToLatest = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    setFollowTail(true);
  }, []);
  return /*#__PURE__*/React.createElement("div", {
    className: "console-v2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "console-v2__head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "console-v2__title"
  }, /*#__PURE__*/React.createElement("span", {
    className: "console-v2__dot",
    "data-status": status
  }), /*#__PURE__*/React.createElement("span", {
    className: "console-v2__name"
  }, stepName || stepId), /*#__PURE__*/React.createElement("span", {
    className: "console-v2__count"
  }, logs.length, " line", logs.length === 1 ? '' : 's')), /*#__PURE__*/React.createElement("div", {
    className: "console-v2__filters"
  }, ['all', 'info', 'warn', 'error'].map(lv => /*#__PURE__*/React.createElement("button", {
    key: lv,
    className: cx('chip', levelFilter === lv && 'chip--active', `chip--${lv}`),
    onClick: () => onLevelFilterChange(lv),
    title: `Show ${lv}`
  }, lv)), /*#__PURE__*/React.createElement("button", {
    className: "chip chip--ghost",
    onClick: onCopy,
    title: "Copy all log lines"
  }, copyState === 'copied' ? 'copied' : 'copy'), /*#__PURE__*/React.createElement("button", {
    className: "chip chip--ghost",
    onClick: onDownload,
    title: "Download .log"
  }, "download"))), /*#__PURE__*/React.createElement("div", {
    className: "console-v2__body",
    ref: scrollRef,
    onScroll: onScroll
  }, filtered.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "console-v2__empty"
  }, status === STEP_STATUS_RUNNING ? 'Waiting for output…' : status === STEP_STATUS_PENDING ? 'Step has not started yet.' : 'No logs.') : filtered.map((l, i) => {
    const lv = normalizeLevel(l.level);
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: cx('console-v2__line', `console-v2__line--${lv}`)
    }, /*#__PURE__*/React.createElement("span", {
      className: "console-v2__time"
    }, fmtTimeMs(l.timestamp)), /*#__PURE__*/React.createElement("span", {
      className: cx('console-v2__lvl', `console-v2__lvl--${lv}`)
    }, (l.level || 'INFO').toUpperCase()), /*#__PURE__*/React.createElement("span", {
      className: "console-v2__msg"
    }, l.message));
  })), !followTail && filtered.length > 0 && /*#__PURE__*/React.createElement("button", {
    className: "console-v2__jump",
    onClick: jumpToLatest
  }, "↓ Jump to latest"));
}
function JourneyStudioV2Page({
  journeyId
}) {
  const [journey, setJourney] = useState(null);
  const [activeStageId, setActiveStageId] = useState(null);
  const [error, setError] = useState(null);

  // Live job state (one job at a time on this page)
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // 'running' | 'completed' | ...
  const [currentStepId, setCurrentStepId] = useState(null);
  const [stepStates, setStepStates] = useState({}); // {stepId: {status, progress, current, total}}
  const [stepLogs, setStepLogs] = useState({}); // {stepId: LogEntry[]}
  const [expanded, setExpanded] = useState({}); // {stepId: bool}
  const [levelFilter, setLevelFilter] = useState({}); // {stepId: 'all'|'info'|'warn'|'error'}
  const [sseStatus, setSseStatus] = useState('idle'); // 'idle'|'connecting'|'connected'|'disconnected'

  const stepRefs = useRef({});
  const esRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const restPollersRef = useRef({
    status: null,
    logs: null
  });
  const lastFocusedStepRef = useRef(null);
  // GitHub-Actions UX: only one step's console is open at a time by default.
  // When the SSE stream advances to a new running step we collapse the
  // previous one. The user clicking "Expand all" pins this off so manual
  // expansion sticks; "Collapse all" or starting a new job resets to true.
  const autoCollapseRef = useRef(true);
  const toast = useToast();

  // ── Load journey + restore the most recent job on mount ──────────
  const loadJourney = useCallback(async () => {
    try {
      // Fetch journey + registered-stages map in parallel; the legacy
      // DynamoDB router persists stages without their step list, so we
      // backfill steps from the registered stage class metadata here.
      // listRegisteredStages() failures are non-fatal — the journey
      // still renders, just without enriched steps.
      const [j, registry] = await Promise.all([api.getJourney(journeyId), api.listRegisteredStages().catch(() => ({
        stages: []
      }))]);
      const enriched = enrichJourneyStagesFromRegistry(j, registry?.stages || []);
      setJourney(enriched);
      setActiveStageId(prev => prev || (enriched.stages[0]?.id ?? null));
    } catch (e) {
      setError(e.message);
    }
  }, [journeyId]);
  useEffect(() => {
    loadJourney();
  }, [loadJourney]);
  const activeStage = useMemo(() => (journey?.stages || []).find(s => s.id === activeStageId) || null, [journey, activeStageId]);

  // Initialize per-step state when the active stage changes.
  useEffect(() => {
    if (!activeStage) return;
    const initStates = {};
    const initFilters = {};
    activeStage.steps.forEach(s => {
      initStates[s.id] = {
        status: STEP_STATUS_PENDING,
        progress: 0
      };
      initFilters[s.id] = 'all';
    });
    setStepStates(initStates);
    setLevelFilter(initFilters);
    setStepLogs({});
    setExpanded({});
    setCurrentStepId(null);
    setJob(null);
    setJobStatus(null);
  }, [activeStage?.id]);

  // ── SSE wiring (named events) ────────────────────────────────────
  const closeStream = useCallback(() => {
    if (esRef.current) {
      try {
        esRef.current.close();
      } catch (_) {}
      esRef.current = null;
    }
    if (restPollersRef.current.status) clearInterval(restPollersRef.current.status);
    if (restPollersRef.current.logs) clearInterval(restPollersRef.current.logs);
    restPollersRef.current = {
      status: null,
      logs: null
    };
  }, []);
  const refetchCanonicalLogs = useCallback(async jid => {
    // Two backends, two log shapes:
    //   - Slim:   GET /logs returns the entire flat array in one shot.
    //   - Legacy: GET /logs is a per-(stage, step) endpoint — without
    //             stage_name+step_name query params it returns [].
    // The legacy backend is what the production deploy hits, so we fan
    // out one request per step and merge with what we've already got
    // from the SSE stream. Empty REST responses don't wipe the in-memory
    // streamed lines.
    if (!jid || !activeStage) return;
    try {
      const grouped = {};
      await Promise.all(activeStage.steps.map(async step => {
        const url = `/api/v1/journeys/${journeyId}/jobs/${jid}/logs` + `?stage_name=${encodeURIComponent(activeStage.id)}` + `&step_name=${encodeURIComponent(step.id)}`;
        try {
          const r = await fetch(url, {
            cache: 'no-store'
          });
          if (!r.ok) return;
          const body = await r.json().catch(() => ({}));
          // Legacy: {data: {logs: [...]}}; slim: [...]; defensive on both.
          const arr = Array.isArray(body) ? body : body?.data?.logs ?? body?.logs ?? [];
          if (!Array.isArray(arr) || arr.length === 0) return;
          grouped[step.id] = arr.map(l => ({
            timestamp: l.timestamp ?? l.time ?? null,
            level: (l.level ?? 'info').toString().toLowerCase(),
            message: l.message ?? l.log_message ?? '',
            step_id: l.step_id ?? l.stepId ?? l.step_name ?? step.id
          }));
        } catch (_) {}
      }));
      // Merge: REST wins per-step when it has data, otherwise keep the
      // SSE-streamed lines that are already in state.
      if (Object.keys(grouped).length > 0) {
        setStepLogs(prev => ({
          ...prev,
          ...grouped
        }));
      }
    } catch (_) {}
  }, [journeyId, activeStage]);
  const refetchJob = useCallback(async jid => {
    if (!jid) return;
    try {
      const j = await api.getJob(journeyId, jid);
      setJob(j);
      setJobStatus(j.status);
      setCurrentStepId(j.current_step_id || null);
    } catch (_) {}
  }, [journeyId]);
  const startRestFallback = useCallback(jid => {
    if (restPollersRef.current.status || restPollersRef.current.logs) return;
    restPollersRef.current.status = setInterval(() => refetchJob(jid), 2000);
    restPollersRef.current.logs = setInterval(() => refetchCanonicalLogs(jid), 3000);
  }, [refetchJob, refetchCanonicalLogs]);

  // SSE payload normalizer.
  //
  // Two server-side formats coexist in the wider Nexus stack:
  //   • SimpleSSEManager (in-engine demo): JobEvent shape
  //     `{type, job_id, step_id, data: {...kwargs}, timestamp}`
  //   • Production SSEManager: flat shape
  //     `{step_id, status, step_index, progress, message, timestamp}`
  // We pick fields from `data.data` first (wrapped) then fall back to `data`
  // so the same v2 page works against either backend.
  const pick = (evt, key) => {
    if (evt == null) return undefined;
    if (evt.data && typeof evt.data === 'object' && key in evt.data) return evt.data[key];
    return evt[key];
  };
  const onStepStatus = useCallback(evt => {
    const sid = evt.step_id ?? pick(evt, 'step_id');
    if (!sid) return;
    const rawStatus = pick(evt, 'status') ?? evt.status;
    const status = rawStatus === 'in_progress' ? STEP_STATUS_RUNNING : rawStatus;
    const progress = pick(evt, 'progress');
    setStepStates(prev => {
      const next = {
        ...prev
      };
      next[sid] = {
        ...(next[sid] || {}),
        status,
        progress: progress ?? next[sid]?.progress ?? 0
      };
      // When this step starts, mark all prior steps in the active stage completed.
      if (status === STEP_STATUS_RUNNING && activeStage) {
        const idx = activeStage.steps.findIndex(s => s.id === sid);
        activeStage.steps.forEach((s, i) => {
          if (i < idx) {
            const ps = next[s.id]?.status;
            if (ps !== STEP_STATUS_FAILED && ps !== STEP_STATUS_COMPLETED) {
              next[s.id] = {
                ...(next[s.id] || {}),
                status: STEP_STATUS_COMPLETED,
                progress: 100
              };
            }
          }
        });
      }
      if (status === STEP_STATUS_COMPLETED) {
        next[sid] = {
          ...(next[sid] || {}),
          status,
          progress: 100
        };
      }
      return next;
    });
    if (status === STEP_STATUS_RUNNING) {
      setCurrentStepId(sid);
      setExpanded(prev => autoCollapseRef.current
      // Only one step open at a time — prior consoles auto-collapse.
      ? {
        [sid]: true
      } : {
        ...prev,
        [sid]: true
      });
    }
    if (status === STEP_STATUS_FAILED) {
      // Always keep the failed step's console open so the user sees the
      // error context, regardless of auto-collapse mode.
      setExpanded(prev => ({
        ...prev,
        [sid]: true
      }));
    }
  }, [activeStage]);
  const onLog = useCallback(evt => {
    const sid = evt.step_id ?? pick(evt, 'step_id') ?? '__unstepped__';
    const entry = {
      timestamp: evt.timestamp || pick(evt, 'timestamp') || new Date().toISOString(),
      level: pick(evt, 'level') ?? evt.level ?? 'info',
      message: pick(evt, 'message') ?? evt.message ?? '',
      step_id: evt.step_id ?? pick(evt, 'step_id')
    };
    setStepLogs(prev => {
      const cur = prev[sid] || [];
      return {
        ...prev,
        [sid]: [...cur, entry]
      };
    });
  }, []);
  const onTaskProgress = useCallback(evt => {
    const sid = evt.step_id ?? pick(evt, 'step_id');
    if (!sid) return;
    const progress = pick(evt, 'progress') ?? pick(evt, 'percentage');
    const current = pick(evt, 'current');
    const total = pick(evt, 'total');
    setStepStates(prev => ({
      ...prev,
      [sid]: {
        ...(prev[sid] || {}),
        status: prev[sid]?.status === STEP_STATUS_COMPLETED ? STEP_STATUS_COMPLETED : STEP_STATUS_RUNNING,
        progress: progress ?? prev[sid]?.progress ?? 0,
        current: current ?? prev[sid]?.current,
        total: total ?? prev[sid]?.total
      }
    }));
  }, []);
  const connectStream = useCallback(jid => {
    closeStream();
    setSseStatus('connecting');
    let es;
    try {
      es = new EventSource(`/api/v1/journeys/${journeyId}/jobs/${jid}/stream`);
    } catch (e) {
      setSseStatus('disconnected');
      startRestFallback(jid);
      return;
    }
    esRef.current = es;
    es.onopen = () => {
      setSseStatus('connected');
      reconnectAttemptsRef.current = 0;
    };
    es.addEventListener('step_status', e => {
      try {
        onStepStatus(JSON.parse(e.data));
      } catch (_) {}
    });
    es.addEventListener('log', e => {
      try {
        onLog(JSON.parse(e.data));
      } catch (_) {}
    });
    es.addEventListener('task_progress', e => {
      try {
        onTaskProgress(JSON.parse(e.data));
      } catch (_) {}
    });
    es.addEventListener('job_complete', e => {
      // Close over `jid` directly — `jobId` from React state may be stale
      // when this listener fires because connectStream runs synchronously
      // right after setJobId() but before the re-render commits.
      try {
        const evt = JSON.parse(e.data);
        const status = pick(evt, 'status') ?? evt.status ?? 'completed';
        setJobStatus(status);
        // Production `TransformationJobExecutor` only emits
        // `step_status:in_progress` events — never an explicit
        // `step_status:completed` for the running step. Our normal
        // heuristic (mark step N completed when step N+1 fires running)
        // therefore leaves the LAST step stuck on Active/0% forever.
        // Fix: when the job terminates successfully, sweep every step
        // in the active stage that isn't already failed and mark it
        // completed. Failed steps stay as-is so error context is preserved.
        if (status === 'completed' && activeStage) {
          setStepStates(prev => {
            const next = {
              ...prev
            };
            activeStage.steps.forEach(s => {
              const cur = next[s.id]?.status;
              if (cur !== STEP_STATUS_FAILED) {
                next[s.id] = {
                  ...(next[s.id] || {}),
                  status: STEP_STATUS_COMPLETED,
                  progress: 100
                };
              }
            });
            return next;
          });
        }
        setCurrentStepId(null);
        closeStream();
        refetchCanonicalLogs(jid);
        refetchJob(jid);
      } catch (_) {}
    });
    es.onerror = () => {
      setSseStatus('disconnected');
      try {
        es.close();
      } catch (_) {}
      esRef.current = null;
      reconnectAttemptsRef.current += 1;
      if (reconnectAttemptsRef.current <= 5) {
        const delay = Math.min(8000, 500 * Math.pow(2, reconnectAttemptsRef.current));
        setTimeout(() => {
          if (jobStatus !== 'completed' && jobStatus !== 'failed' && jobStatus !== 'cancelled') {
            connectStream(jid);
          }
        }, delay);
      } else {
        startRestFallback(jid);
      }
    };
  }, [journeyId, closeStream, onStepStatus, onLog, onTaskProgress, refetchCanonicalLogs, refetchJob, startRestFallback, jobStatus, activeStage]);

  // Auto-scroll the active step into the center of the viewport.
  useEffect(() => {
    if (!currentStepId) return;
    if (lastFocusedStepRef.current === currentStepId) return;
    lastFocusedStepRef.current = currentStepId;
    const el = stepRefs.current[currentStepId];
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({
        block: 'center',
        behavior: 'smooth'
      });
    }
  }, [currentStepId]);

  // Cleanup stream on unmount or job change.
  useEffect(() => () => closeStream(), [closeStream]);
  const onStart = useCallback(async () => {
    if (!activeStage) return;
    try {
      const newJob = await api.runJob(journey.id, activeStage.id, 'manual run from v2 view');
      lastFocusedStepRef.current = null;
      // Reset auto-collapse mode for the new run so the open-current-only
      // behaviour kicks in even if the user had pinned Expand all on a
      // previous run.
      autoCollapseRef.current = true;
      setStepLogs({});
      setStepStates(prev => {
        const next = {};
        activeStage.steps.forEach(s => {
          next[s.id] = {
            status: STEP_STATUS_PENDING,
            progress: 0
          };
        });
        return next;
      });
      // Pre-expand the first step's console so the user sees a
      // "Waiting for output…" placeholder immediately. Without this, the
      // console only opens when the SSE `step_status:running` event for
      // step 1 arrives, which is several hundred ms later — the user reads
      // that delay as the first step "taking time to open".
      const firstStepId = activeStage.steps[0]?.id;
      setExpanded(firstStepId ? {
        [firstStepId]: true
      } : {});
      setCurrentStepId(firstStepId || null);
      setJobId(newJob.id);
      setJob(newJob);
      setJobStatus(newJob.status);
      connectStream(newJob.id);
      toast(`Job ${fmtShortId(newJob.id)} started`, 'success');
    } catch (e) {
      toast(`Run failed: ${e.message}`, 'error');
    }
  }, [activeStage, journey, connectStream, toast]);
  const onCancel = useCallback(async () => {
    if (!jobId) return;
    try {
      await api.cancelJob(journeyId, jobId);
      toast('Cancel requested', 'success');
    } catch (e) {
      toast(`Cancel failed: ${e.message}`, 'error');
    }
  }, [jobId, journeyId, toast]);
  const toggleExpanded = useCallback(sid => {
    setExpanded(prev => ({
      ...prev,
      [sid]: !prev[sid]
    }));
  }, []);
  const expandAll = useCallback(() => {
    if (!activeStage) return;
    // Pin auto-collapse off so the next step_status:running event doesn't
    // immediately tear down the user's manual expansion.
    autoCollapseRef.current = false;
    const next = {};
    activeStage.steps.forEach(s => {
      next[s.id] = true;
    });
    setExpanded(next);
  }, [activeStage]);
  const collapseAll = useCallback(() => {
    // Re-enable auto-collapse so subsequent live runs revert to the
    // GitHub-Actions-style single-open behaviour.
    autoCollapseRef.current = true;
    setExpanded({});
  }, []);
  if (error) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "Could not load journey"), /*#__PURE__*/React.createElement("p", {
    className: "mono"
  }, error)));
  if (!journey) return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, "Loading…"));
  const stepCount = activeStage?.steps.length || 0;
  const currentIdx = activeStage ? activeStage.steps.findIndex(s => s.id === currentStepId) : -1;
  const isRunning = jobStatus === 'running' || jobStatus === 'queued';
  return /*#__PURE__*/React.createElement("div", {
    className: "page"
  }, /*#__PURE__*/React.createElement("div", {
    className: "row mt-12",
    style: {
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: () => navigate('#/')
  }, "← Back"), /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 20,
      fontWeight: 700
    }
  }, journey.name), /*#__PURE__*/React.createElement("span", {
    className: "pill pill--created",
    style: {
      marginLeft: 10
    }
  }, "v2 preview"), /*#__PURE__*/React.createElement("span", {
    className: "mono muted",
    style: {
      marginLeft: 10
    }
  }, fmtShortId(journey.id, 12)))), /*#__PURE__*/React.createElement("div", {
    className: "row"
  }, /*#__PURE__*/React.createElement("span", {
    className: cx('pill', sseStatus === 'connected' ? 'pill--running' : sseStatus === 'connecting' ? 'pill--queued' : sseStatus === 'disconnected' ? 'pill--failed' : 'pill--pending')
  }, "sse: ", sseStatus), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => navigate(`#/journey/${journey.id}`)
  }, "← v1 view"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost",
    onClick: loadJourney
  }, "↻ Refresh"))), /*#__PURE__*/React.createElement("div", {
    className: "studio mt-20"
  }, /*#__PURE__*/React.createElement("div", {
    className: "studio__sidebar"
  }, /*#__PURE__*/React.createElement("h3", null, "Processing Stages"), journey.stages.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.id,
    className: cx('stage-entry', s.id === activeStageId && 'stage-entry--active'),
    onClick: () => setActiveStageId(s.id)
  }, /*#__PURE__*/React.createElement("div", {
    className: "stage-entry__name"
  }, s.name), /*#__PURE__*/React.createElement("div", {
    className: "stage-entry__meta"
  }, /*#__PURE__*/React.createElement("span", {
    className: cx('pill', `pill--${s.status}`)
  }, s.status), /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, " · ", s.steps.length, " step", s.steps.length === 1 ? '' : 's'))))), /*#__PURE__*/React.createElement("div", {
    className: "studio__main"
  }, !activeStage ? /*#__PURE__*/React.createElement("div", {
    className: "empty"
  }, /*#__PURE__*/React.createElement("h3", null, "No stages yet")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "stage-header"
  }, /*#__PURE__*/React.createElement("div", {
    className: "stage-header__title"
  }, activeStage.name), activeStage.description && /*#__PURE__*/React.createElement("div", {
    className: "stage-header__desc"
  }, activeStage.description), /*#__PURE__*/React.createElement("div", {
    className: "stage-header__actions"
  }, !isRunning && /*#__PURE__*/React.createElement("button", {
    className: "btn btn--primary",
    onClick: onStart
  }, "▶ Start Processing"), isRunning && /*#__PURE__*/React.createElement("button", {
    className: "btn btn--danger",
    onClick: onCancel
  }, "■ Cancel"), /*#__PURE__*/React.createElement("button", {
    className: "btn",
    onClick: () => navigate(`#/journey/${journey.id}/jobs`)
  }, "View All Jobs"), /*#__PURE__*/React.createElement("div", {
    className: "grow"
  }), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost btn--small",
    onClick: expandAll
  }, "Expand all"), /*#__PURE__*/React.createElement("button", {
    className: "btn btn--ghost btn--small",
    onClick: collapseAll
  }, "Collapse all"))), isRunning && currentStepId && currentIdx >= 0 && /*#__PURE__*/React.createElement("div", {
    className: "run-banner"
  }, /*#__PURE__*/React.createElement("span", {
    className: "run-banner__spinner"
  }), /*#__PURE__*/React.createElement("span", null, "Processing step ", /*#__PURE__*/React.createElement("strong", null, currentIdx + 1), " of ", /*#__PURE__*/React.createElement("strong", null, stepCount), ":", ' ', /*#__PURE__*/React.createElement("strong", null, activeStage.steps[currentIdx]?.name)), /*#__PURE__*/React.createElement("div", {
    className: "grow"
  }), (() => {
    const st = stepStates[currentStepId];
    const pct = Math.max(0, Math.min(100, st?.progress ?? 0));
    return /*#__PURE__*/React.createElement(React.Fragment, null, st?.current != null && st?.total != null && /*#__PURE__*/React.createElement("span", {
      className: "muted mono",
      style: {
        marginRight: 8
      }
    }, st.current, "/", st.total), /*#__PURE__*/React.createElement("div", {
      className: "progress"
    }, /*#__PURE__*/React.createElement("div", {
      className: "progress__bar",
      style: {
        width: `${pct}%`
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "muted mono",
      style: {
        marginLeft: 8,
        minWidth: 36,
        textAlign: 'right'
      }
    }, pct, "%"));
  })()), /*#__PURE__*/React.createElement("div", {
    className: "stepper"
  }, activeStage.steps.map((step, i) => {
    const st = stepStates[step.id] || {
      status: STEP_STATUS_PENDING,
      progress: 0
    };
    const isCurrent = step.id === currentStepId;
    const isLast = i === activeStage.steps.length - 1;
    const logs = stepLogs[step.id] || [];
    const isExpanded = !!expanded[step.id];
    const lf = levelFilter[step.id] || 'all';
    return /*#__PURE__*/React.createElement("div", {
      key: step.id,
      className: cx('stepper__row', `stepper__row--${st.status}`, isCurrent && 'stepper__row--current'),
      ref: el => {
        stepRefs.current[step.id] = el;
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "stepper__rail"
    }, /*#__PURE__*/React.createElement("div", {
      className: cx('stepper__node', `stepper__node--${st.status}`)
    }, st.status === STEP_STATUS_COMPLETED ? '✓' : st.status === STEP_STATUS_FAILED ? '!' : st.status === STEP_STATUS_RUNNING ? /*#__PURE__*/React.createElement("span", {
      className: "stepper__spinner"
    }) : i + 1), !isLast && /*#__PURE__*/React.createElement("div", {
      className: cx('stepper__line', `stepper__line--${st.status}`)
    })), /*#__PURE__*/React.createElement("div", {
      className: "stepper__card"
    }, /*#__PURE__*/React.createElement("div", {
      className: "stepper__cardhead"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "stepper__name"
    }, step.name, st.status === STEP_STATUS_RUNNING && /*#__PURE__*/React.createElement("span", {
      className: "badge badge--running"
    }, "Active"), st.status === STEP_STATUS_COMPLETED && /*#__PURE__*/React.createElement("span", {
      className: "badge badge--done"
    }, "Done"), st.status === STEP_STATUS_FAILED && /*#__PURE__*/React.createElement("span", {
      className: "badge badge--failed"
    }, "Failed"), st.status === STEP_STATUS_PENDING && /*#__PURE__*/React.createElement("span", {
      className: "badge badge--pending"
    }, "Pending")), step.description && /*#__PURE__*/React.createElement("div", {
      className: "stepper__desc"
    }, step.description)), /*#__PURE__*/React.createElement("button", {
      className: cx('btn btn--small', st.status === STEP_STATUS_RUNNING && 'btn--primary'),
      onClick: () => toggleExpanded(step.id)
    }, isExpanded ? '▾' : '▸', " Logs (", logs.length, ")")), st.status === STEP_STATUS_RUNNING && /*#__PURE__*/React.createElement("div", {
      className: "stepper__progress"
    }, /*#__PURE__*/React.createElement("div", {
      className: "progress"
    }, /*#__PURE__*/React.createElement("div", {
      className: "progress__bar",
      style: {
        width: `${Math.max(0, Math.min(100, st.progress || 0))}%`
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "muted mono"
    }, Math.max(0, Math.min(100, st.progress || 0)), "%")), isExpanded && /*#__PURE__*/React.createElement(StepConsoleV2, {
      stepId: step.id,
      stepName: step.name,
      status: st.status,
      logs: logs,
      levelFilter: lf,
      onLevelFilterChange: v => setLevelFilter(prev => ({
        ...prev,
        [step.id]: v
      }))
    })));
  }))))));
}

/* ─────────────────────── App shell ─────────────────────── */

function App() {
  const hash = useHashRoute();
  const route = useMemo(() => parseRoute(hash), [hash]);
  let view;
  switch (route.name) {
    case 'journeys':
      view = /*#__PURE__*/React.createElement(JourneysListPage, null);
      break;
    case 'studio':
      view = /*#__PURE__*/React.createElement(JourneyStudioPage, {
        journeyId: route.journeyId
      });
      break;
    case 'studio_v2':
      view = /*#__PURE__*/React.createElement(JourneyStudioV2Page, {
        journeyId: route.journeyId
      });
      break;
    case 'jobs':
      view = /*#__PURE__*/React.createElement(JobHistoryPage, {
        journeyId: route.journeyId
      });
      break;
    case 'schedules':
      view = /*#__PURE__*/React.createElement(SchedulesPage, null);
      break;
    case 'prompts':
      view = /*#__PURE__*/React.createElement(PromptsPage, null);
      break;
    default:
      view = /*#__PURE__*/React.createElement(JourneysListPage, null);
  }
  return /*#__PURE__*/React.createElement(ToastProvider, null, /*#__PURE__*/React.createElement(AppShell, {
    route: route
  }, view));
}
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(/*#__PURE__*/React.createElement(App, null));
