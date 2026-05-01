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

const { useState, useEffect, useMemo, useCallback, useRef, useReducer } = React;

/* ─────────────────────── API client ─────────────────────── */

const api = {
  listJourneys(params = {}) {
    const qs = new URLSearchParams();
    if (params.q) qs.set('q', params.q);
    if (params.status) qs.set('status_filter', params.status);
    if (params.capability) qs.set('capability', params.capability);
    if (params.limit) qs.set('limit', params.limit);
    const s = qs.toString();
    return fetch('/api/v1/journeys/' + (s ? '?' + s : '')).then(requireOk);
  },
  getJourney(id)          { return fetch(`/api/v1/journeys/${id}`).then(requireOk); },
  createJourney(body)     { return postJson('/api/v1/journeys/', body); },
  deleteJourney(id)       { return fetch(`/api/v1/journeys/${id}`, { method: 'DELETE' }).then(requireOk); },
  cloneJourney(id, name)  { return postJson(`/api/v1/journeys/${id}/clone`, name ? { name } : {}); },

  listJobs(jid)           { return fetch(`/api/v1/journeys/${jid}/jobs`).then(requireOk); },
  getJob(jid, id)         { return fetch(`/api/v1/journeys/${jid}/jobs/${id}`).then(requireOk); },
  jobStatus(jid, id)      { return fetch(`/api/v1/journeys/${jid}/jobs/${id}/status`).then(requireOk); },
  runJob(jid, stageId, reason) {
    return postJson(`/api/v1/journeys/${jid}/jobs`, { stage_id: stageId, triggered_by: 'ui', reason });
  },
  cancelJob(jid, id)      { return postJson(`/api/v1/journeys/${jid}/jobs/${id}/cancel`, {}); },
  retryJob(jid, id)       { return postJson(`/api/v1/journeys/${jid}/jobs/${id}/retry`, {}); },
  jobLogs(jid, id)        { return fetch(`/api/v1/journeys/${jid}/jobs/${id}/logs`).then(requireOk); },

  aggregateReport(jid)    { return fetch(`/api/v1/journeys/${jid}/aggregate-report`).then(requireOk); },
  listJobReports(jid, id) { return fetch(`/api/v1/journeys/${jid}/jobs/${id}/reports`).then(requireOk); },

  listSchedules(journeyId) {
    const q = journeyId ? `?journey_id=${encodeURIComponent(journeyId)}` : '';
    return fetch(`/api/v1/schedules/${q}`).then(requireOk);
  },
  createSchedule(body)    { return postJson('/api/v1/schedules/', body); },
  updateSchedule(id, b)   { return patchJson(`/api/v1/schedules/${id}`, b); },
  deleteSchedule(id)      { return fetch(`/api/v1/schedules/${id}`, { method: 'DELETE' }).then(requireOk); },
  runScheduleNow(id)      { return postJson(`/api/v1/schedules/${id}/run`, {}); },

  listPrompts()           { return fetch('/api/v1/prompts').then(requireOk); },
  updatePrompt(id, body)  { return putJson(`/api/v1/prompts/${id}`, body); },
  resetPrompts()          { return postJson('/api/v1/prompts/reset', {}); },
  promptAudit(limit = 50) { return fetch(`/api/v1/prompts/audit/log?limit=${limit}`).then(requireOk); },
};

function postJson(url, body) {
  return fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(requireOk);
}
function putJson(url, body) {
  return fetch(url, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(requireOk);
}
function patchJson(url, body) {
  return fetch(url, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(requireOk);
}
async function requireOk(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
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
  return d.toLocaleDateString(undefined, { month: 'short', day: '2-digit', year: 'numeric' });
}
function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function fmtShortId(id, n = 8) { return id ? String(id).slice(0, n) + '…' : ''; }
function cx(...xs) { return xs.filter(Boolean).join(' '); }

/* ─────────────────────── Toast system ─────────────────────── */

const ToastContext = React.createContext(null);

function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, type = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, { id, message, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-stack">
        {toasts.map(t => (
          <div key={t.id} className={cx('toast', `toast--${t.type}`)}>{t.message}</div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
function useToast() { return React.useContext(ToastContext); }

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
function navigate(hash) { window.location.hash = hash; }

function parseRoute(hash) {
  const clean = (hash || '#/').replace(/^#/, '');
  const parts = clean.split('/').filter(Boolean);
  if (parts.length === 0) return { name: 'journeys' };
  if (parts[0] === 'journey' && parts[1] && parts[2] === 'jobs') {
    return { name: 'jobs', journeyId: parts[1] };
  }
  if (parts[0] === 'journey' && parts[1]) {
    return { name: 'studio', journeyId: parts[1] };
  }
  if (parts[0] === 'schedules') return { name: 'schedules' };
  if (parts[0] === 'prompts')   return { name: 'prompts' };
  return { name: 'journeys' };
}

/* ─────────────────────── Top bar ─────────────────────── */

function TopBar({ route }) {
  const [version, setVersion] = useState('…');
  useEffect(() => {
    fetch('/version').then(r => r.json()).then(v => setVersion(v.version)).catch(() => {});
  }, []);
  const navItem = (hash, name, label) => (
    <a href={hash} className={route.name === name ? 'active' : ''}>{label}</a>
  );
  return (
    <div className="top-bar">
      <div className="top-bar__logo">
        <div className="top-bar__logo-badge">NE</div>
        <div>Nexus AI Engine</div>
      </div>
      <div className="top-bar__nav">
        {navItem('#/', 'journeys', 'Journeys')}
        {navItem('#/schedules', 'schedules', 'Schedules')}
        {navItem('#/prompts', 'prompts', 'Prompts')}
      </div>
      <div className="top-bar__right">
        <span className="pf-badge">port-forward dev UI</span>
        <span className="mono">v{version}</span>
      </div>
    </div>
  );
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
    api.listJourneys({})
      .then(data => setJourneys(data))
      .catch(e => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const capabilities = useMemo(() => {
    const s = new Set();
    (journeys || []).forEach(j => j.capability && s.add(j.capability));
    return Array.from(s);
  }, [journeys]);

  const filtered = useMemo(() => {
    if (!journeys) return [];
    const q = query.toLowerCase();
    return journeys.filter(j => {
      if (q && !(`${j.name} ${j.id}`.toLowerCase().includes(q))) return false;
      if (statusFilter && j.status !== statusFilter) return false;
      if (capabilityFilter && j.capability !== capabilityFilter) return false;
      return true;
    });
  }, [journeys, query, statusFilter, capabilityFilter]);

  const onDelete = useCallback((j) => {
    if (!window.confirm(`Delete journey "${j.name}"?`)) return;
    api.deleteJourney(j.id)
      .then(() => { toast('Journey deleted', 'success'); load(); })
      .catch(e => toast(`Delete failed: ${e.message}`, 'error'));
  }, [load, toast]);

  const onClone = useCallback((j) => {
    api.cloneJourney(j.id)
      .then(() => { toast('Journey cloned', 'success'); load(); })
      .catch(e => toast(`Clone failed: ${e.message}`, 'error'));
  }, [load, toast]);

  const onNewJourney = useCallback(() => {
    const name = window.prompt('Journey name?');
    if (!name) return;
    api.createJourney({ name, description: null, capability: 'custom' })
      .then(() => { toast('Journey created', 'success'); load(); })
      .catch(e => toast(`Create failed: ${e.message}`, 'error'));
  }, [load, toast]);

  if (error) return <div className="page"><div className="empty"><h3>Could not load journeys</h3><p className="mono">{error}</p></div></div>;
  if (!journeys) return <div className="page"><div className="empty">Loading…</div></div>;

  return (
    <div className="page">
      <div className="filter-bar">
        <input
          className="input"
          placeholder="Search journeys…"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <select className="select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="created">Created</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select className="select" value={capabilityFilter} onChange={e => setCapabilityFilter(e.target.value)}>
          <option value="">All capabilities</option>
          {capabilities.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <div className="grow" />
        <button className="btn btn--primary" onClick={onNewJourney}>+ New Journey</button>
        <button className="btn btn--ghost" onClick={load} title="Refresh">↻</button>
      </div>

      {filtered.length === 0 ? (
        <div className="empty"><h3>No journeys</h3><p>Create one to get started.</p></div>
      ) : (
        <div className="cards-grid">
          {filtered.map(j => (
            <JourneyCard key={j.id} journey={j} onOpen={() => navigate(`#/journey/${j.id}`)} onDelete={() => onDelete(j)} onClone={() => onClone(j)} />
          ))}
        </div>
      )}
    </div>
  );
}

function JourneyCard({ journey, onOpen, onDelete, onClone }) {
  return (
    <div className="card card--clickable" onClick={onOpen}>
      <div className="card__title">
        <div>
          <div className="card__name">{journey.name}</div>
          <div className="card__id">{fmtShortId(journey.id)}</div>
        </div>
        <span className={cx('pill', `pill--${journey.status}`)}>{journey.status}</span>
      </div>
      <div className="card__metrics">
        <div><div className="metric__value">{journey.jobs_total}</div><div className="metric__label">Jobs</div></div>
        <div><div className="metric__value metric__value--done">{journey.jobs_done}</div><div className="metric__label">Done</div></div>
        <div><div className="metric__value metric__value--running">{journey.jobs_running}</div><div className="metric__label">Running</div></div>
        <div><div className="metric__value metric__value--failed">{journey.jobs_failed}</div><div className="metric__label">Failed</div></div>
      </div>
      <div className="card__kpis">
        <div><span className="card__kpi--value">{journey.success_rate.toFixed(0)}%</span> <span className="muted">Success</span></div>
        <div><span className="card__kpi--value">{fmtDuration(journey.avg_duration_seconds)}</span> <span className="muted">Avg dur</span></div>
      </div>
      <div className="card__footer">
        <div>
          <span className="mono">{journey.capability || '—'}</span>
          <span className="muted"> · {fmtDate(journey.created_at)}</span>
        </div>
        <div className="row" onClick={e => e.stopPropagation()}>
          <button className="btn btn--ghost btn--small" onClick={onClone} title="Clone">⧉</button>
          <button className="btn btn--danger btn--small" onClick={onDelete} title="Delete">Delete</button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────── Journey studio (detail) ─────────────────────── */

function JourneyStudioPage({ journeyId }) {
  const [journey, setJourney] = useState(null);
  const [aggregate, setAggregate] = useState(null);
  const [activeStageId, setActiveStageId] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [error, setError] = useState(null);
  const [logsJobId, setLogsJobId] = useState(null);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      const [j, agg, sch] = await Promise.all([
        api.getJourney(journeyId),
        api.aggregateReport(journeyId).catch(() => null),
        api.listSchedules(journeyId).catch(() => []),
      ]);
      setJourney(j);
      setAggregate(agg);
      setSchedules(sch);
      if (j.stages.length && !activeStageId) setActiveStageId(j.stages[0].id);
    } catch (e) {
      setError(e.message);
    }
  }, [journeyId, activeStageId]);

  useEffect(() => { load(); }, [load]);

  const activeStage = useMemo(
    () => (journey?.stages || []).find(s => s.id === activeStageId) || null,
    [journey, activeStageId]
  );
  const scheduleForStage = useMemo(
    () => schedules.find(s => s.stage_id === activeStageId),
    [schedules, activeStageId]
  );

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

  if (error) return <div className="page"><div className="empty"><h3>Could not load journey</h3><p className="mono">{error}</p></div></div>;
  if (!journey) return <div className="page"><div className="empty">Loading…</div></div>;

  return (
    <div className="page">
      <div className="row mt-12" style={{ justifyContent: 'space-between' }}>
        <div>
          <button className="btn btn--ghost" onClick={() => navigate('#/')}>← Back</button>
          <span style={{ marginLeft: 12 }}>
            <span style={{ fontSize: 20, fontWeight: 700 }}>{journey.name}</span>
            <span className="mono muted" style={{ marginLeft: 10 }}>{fmtShortId(journey.id, 12)}</span>
          </span>
        </div>
        <div className="row">
          <button className="btn" onClick={() => navigate(`#/journey/${journey.id}/jobs`)}>View All Jobs</button>
          <button className="btn btn--ghost" onClick={load}>↻ Refresh</button>
        </div>
      </div>

      <div className="stats-row mt-20">
        <StatCard label="Total Jobs" value={journey.jobs_total} />
        <StatCard label="Success Rate" value={`${journey.success_rate.toFixed(0)}%`} />
        <StatCard label="Avg Duration" value={fmtDuration(journey.avg_duration_seconds)} />
        <StatCard label="Calls Processed" value={aggregate ? aggregate.total_calls_processed : '—'} />
      </div>

      <div className="studio mt-20">
        <div className="studio__sidebar">
          <h3>Processing Stages</h3>
          {journey.stages.map(s => (
            <div
              key={s.id}
              className={cx('stage-entry', s.id === activeStageId && 'stage-entry--active')}
              onClick={() => setActiveStageId(s.id)}
            >
              <div className="stage-entry__name">{s.name}</div>
              <div className="stage-entry__meta">
                <span className={cx('pill', `pill--${s.status}`)}>{s.status}</span>
                <span className="muted"> · {s.steps.length} step{s.steps.length === 1 ? '' : 's'}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="studio__main">
          {!activeStage ? (
            <div className="empty"><h3>No stages yet</h3></div>
          ) : (
            <>
              <div className="stage-header">
                <div className="stage-header__title">{activeStage.name}</div>
                {activeStage.description && <div className="stage-header__desc">{activeStage.description}</div>}
                <div className="stage-header__actions">
                  <button className="btn btn--primary" onClick={onStartStage}>▶ Start Processing</button>
                  {scheduleForStage ? (
                    <span className={cx('pill', scheduleForStage.enabled ? 'pill--running' : 'pill--paused')}>
                      Every {scheduleForStage.interval_minutes}m · next {fmtTime(scheduleForStage.next_run_at)}
                    </span>
                  ) : (
                    <span className="pill pill--pending">No schedule</span>
                  )}
                  <button className="btn" onClick={() => navigate(`#/journey/${journey.id}/jobs`)}>View All Jobs</button>
                </div>
              </div>

              <div className="steps-list">
                <div className="steps-list__header">Stage Steps</div>
                {activeStage.steps.map((step, i) => (
                  <div key={step.id} className="step-row">
                    <div className="step-row__num">{i + 1}</div>
                    <div className="step-row__body">
                      <div className="step-row__name">{step.name}</div>
                      {step.description && <div className="step-row__desc">{step.description}</div>}
                    </div>
                    <div className="muted mono">{step.id}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {logsJobId && (
        <LogsDrawer
          journeyId={journey.id}
          jobId={logsJobId}
          onClose={() => { setLogsJobId(null); load(); }}
        />
      )}
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-card__label">{label}</div>
      <div className="stat-card__value">{value}</div>
    </div>
  );
}

/* ─────────────────────── Job history ─────────────────────── */

function JobHistoryPage({ journeyId }) {
  const [journey, setJourney] = useState(null);
  const [jobs, setJobs] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [activeStageId, setActiveStageId] = useState(null);
  const [logsJobId, setLogsJobId] = useState(null);
  const [error, setError] = useState(null);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      const [j, js, ss] = await Promise.all([
        api.getJourney(journeyId),
        api.listJobs(journeyId),
        api.listSchedules(journeyId).catch(() => []),
      ]);
      setJourney(j);
      setJobs(js);
      setSchedules(ss);
      if (j.stages.length && !activeStageId) setActiveStageId(j.stages[0].id);
    } catch (e) {
      setError(e.message);
    }
  }, [journeyId, activeStageId]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh while any job is running
  useEffect(() => {
    if (!jobs) return;
    const hasRunning = jobs.some(j => j.status === 'running' || j.status === 'queued');
    if (!hasRunning) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [jobs, load]);

  const filteredJobs = useMemo(
    () => (jobs || []).filter(j => !activeStageId || j.stage_id === activeStageId),
    [jobs, activeStageId]
  );

  const onCancel = useCallback(async (job) => {
    try { await api.cancelJob(journeyId, job.id); toast('Cancelled', 'success'); load(); }
    catch (e) { toast(`Cancel failed: ${e.message}`, 'error'); }
  }, [journeyId, toast, load]);

  const onRetry = useCallback(async (job) => {
    try {
      const newJob = await api.retryJob(journeyId, job.id);
      toast(`Retry started: ${fmtShortId(newJob.id)}`, 'success');
      setLogsJobId(newJob.id);
      load();
    } catch (e) { toast(`Retry failed: ${e.message}`, 'error'); }
  }, [journeyId, toast, load]);

  if (error) return <div className="page"><div className="empty"><h3>Could not load jobs</h3><p className="mono">{error}</p></div></div>;
  if (!journey || !jobs) return <div className="page"><div className="empty">Loading…</div></div>;

  return (
    <div className="page">
      <div className="row mt-12" style={{ justifyContent: 'space-between' }}>
        <div>
          <button className="btn btn--ghost" onClick={() => navigate(`#/journey/${journey.id}`)}>← Back to Studio</button>
          <span style={{ marginLeft: 12, fontSize: 18, fontWeight: 700 }}>{journey.name}: Jobs</span>
        </div>
        <button className="btn btn--ghost" onClick={load}>↻ Refresh</button>
      </div>

      <div className="studio mt-20">
        <div className="studio__sidebar">
          <h3>Processing Stages</h3>
          {journey.stages.map(s => (
            <div
              key={s.id}
              className={cx('stage-entry', s.id === activeStageId && 'stage-entry--active')}
              onClick={() => setActiveStageId(s.id)}
            >
              <div className="stage-entry__name">{s.name}</div>
              <div className="stage-entry__meta">
                <span className="muted">{jobs.filter(j => j.stage_id === s.id).length} jobs</span>
              </div>
            </div>
          ))}
        </div>

        <div className="studio__main">
          <div className="table-wrap">
            <h3>Job history</h3>
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Started</th>
                  <th className="numeric">Calls</th>
                  <th className="numeric">Errors</th>
                  <th className="numeric">Warnings</th>
                  <th className="numeric">Duration</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.length === 0 ? (
                  <tr><td colSpan="8" className="muted" style={{ padding: 30, textAlign: 'center' }}>No jobs yet for this stage.</td></tr>
                ) : filteredJobs.map(job => (
                  <tr key={job.id} className="row--clickable" onClick={() => setLogsJobId(job.id)}>
                    <td className="mono">#{job.execution_number}</td>
                    <td className="muted">{fmtDate(job.started_at)} {fmtTime(job.started_at)}</td>
                    <td className="numeric">{job.metrics?.calls_processed ?? 0}</td>
                    <td className={cx('numeric', job.metrics?.errors ? 'red' : 'muted')}>{job.metrics?.errors ?? 0}</td>
                    <td className={cx('numeric', job.metrics?.warnings ? 'orange' : 'muted')}>{job.metrics?.warnings ?? 0}</td>
                    <td className="numeric">{fmtDuration(job.duration_seconds)}</td>
                    <td><span className={cx('pill', `pill--${job.status}`)}>{job.status}</span></td>
                    <td className="row" style={{ gap: 6 }} onClick={e => e.stopPropagation()}>
                      {(job.status === 'running' || job.status === 'queued') && (
                        <button className="btn btn--small btn--danger" onClick={() => onCancel(job)}>Cancel</button>
                      )}
                      {(job.status === 'failed' || job.status === 'cancelled') && (
                        <button className="btn btn--small" onClick={() => onRetry(job)}>Retry</button>
                      )}
                      <button className="btn btn--small btn--ghost" onClick={() => setLogsJobId(job.id)}>Logs</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <SchedulesPanel journey={journey} schedules={schedules} onChange={load} />
        </div>
      </div>

      {logsJobId && (
        <LogsDrawer
          journeyId={journey.id}
          jobId={logsJobId}
          onClose={() => { setLogsJobId(null); load(); }}
        />
      )}
    </div>
  );
}

/* ─────────────────────── Schedules ─────────────────────── */

function SchedulesPanel({ journey, schedules, onChange }) {
  const toast = useToast();

  const onToggle = useCallback((s) => {
    api.updateSchedule(s.id, { enabled: !s.enabled })
      .then(() => { toast(!s.enabled ? 'Schedule enabled' : 'Schedule paused', 'success'); onChange(); })
      .catch(e => toast(`Update failed: ${e.message}`, 'error'));
  }, [onChange, toast]);

  const onRunNow = useCallback((s) => {
    api.runScheduleNow(s.id)
      .then(() => { toast('Triggered', 'success'); onChange(); })
      .catch(e => toast(`Run failed: ${e.message}`, 'error'));
  }, [onChange, toast]);

  const onDelete = useCallback((s) => {
    if (!window.confirm('Delete this schedule?')) return;
    api.deleteSchedule(s.id)
      .then(() => { toast('Deleted', 'success'); onChange(); })
      .catch(e => toast(`Delete failed: ${e.message}`, 'error'));
  }, [onChange, toast]);

  const onNew = useCallback(() => {
    if (!journey || !journey.stages.length) return;
    const stage = journey.stages[0];
    const mins = parseInt(window.prompt(`Interval in minutes for stage "${stage.name}"?`, '15'), 10);
    if (!mins) return;
    api.createSchedule({ journey_id: journey.id, stage_id: stage.id, interval_minutes: mins, enabled: true })
      .then(() => { toast('Schedule created', 'success'); onChange(); })
      .catch(e => toast(`Create failed: ${e.message}`, 'error'));
  }, [journey, onChange, toast]);

  return (
    <div className="table-wrap mt-20">
      <div className="row" style={{ justifyContent: 'space-between', padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ fontWeight: 700 }}>Batch Schedules</div>
        <button className="btn btn--small" onClick={onNew}>+ New Schedule</button>
      </div>
      <div className="schedules-grid schedules-grid--head">
        <div>Stage</div>
        <div>Interval</div>
        <div>Last run</div>
        <div>Next run</div>
        <div>Status</div>
        <div>Actions</div>
      </div>
      {schedules.length === 0 ? (
        <div className="muted" style={{ padding: 20, textAlign: 'center' }}>No schedules.</div>
      ) : schedules.map(s => {
        const stage = journey?.stages.find(x => x.id === s.stage_id);
        return (
          <div key={s.id} className="schedules-grid">
            <div>
              <div>{stage?.name || s.stage_id}</div>
              <div className="muted mono" style={{ fontSize: 11 }}>{fmtShortId(s.id, 10)}</div>
            </div>
            <div>Every {s.interval_minutes}m</div>
            <div className="muted">{s.last_run_at ? `${fmtDate(s.last_run_at)} ${fmtTime(s.last_run_at)}` : '—'}</div>
            <div className="muted">{s.next_run_at ? `${fmtDate(s.next_run_at)} ${fmtTime(s.next_run_at)}` : '—'}</div>
            <div>
              <button
                className={cx('toggle', s.enabled && 'toggle--on')}
                title={s.enabled ? 'Enabled' : 'Paused'}
                onClick={() => onToggle(s)}
              />
            </div>
            <div className="row" style={{ gap: 6 }}>
              <button className="btn btn--small" onClick={() => onRunNow(s)}>Run now</button>
              <button className="btn btn--small btn--danger" onClick={() => onDelete(s)}>Delete</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SchedulesPage() {
  const [journeys, setJourneys] = useState([]);
  const [schedules, setSchedules] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const [js, ss] = await Promise.all([api.listJourneys({}), api.listSchedules()]);
      setJourneys(js); setSchedules(ss);
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error) return <div className="page"><div className="empty"><h3>Could not load schedules</h3><p className="mono">{error}</p></div></div>;
  if (!schedules) return <div className="page"><div className="empty">Loading…</div></div>;
  if (schedules.length === 0) return <div className="page"><div className="empty"><h3>No schedules</h3><p>Create one from a journey's Job History page.</p></div></div>;

  const grouped = journeys.map(j => ({ j, items: schedules.filter(s => s.journey_id === j.id) })).filter(g => g.items.length);

  return (
    <div className="page">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div style={{ fontSize: 18, fontWeight: 700 }}>All schedules</div>
        <button className="btn btn--ghost" onClick={load}>↻ Refresh</button>
      </div>
      <div className="col mt-20">
        {grouped.map(({ j, items }) => (
          <div key={j.id}>
            <div style={{ margin: '18px 0 8px 0', fontWeight: 700 }}>{j.name}</div>
            <SchedulesPanel journey={j} schedules={items} onChange={load} />
          </div>
        ))}
      </div>
    </div>
  );
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
    } catch (e) { setError(e.message); }
  }, [activeId]);

  useEffect(() => { load(); }, [load]);

  const active = useMemo(() => (prompts || []).find(p => p.id === activeId), [prompts, activeId]);
  useEffect(() => { setDraft(active?.content || ''); }, [active?.id, active?.content]);

  const onSave = useCallback(async () => {
    if (!active) return;
    try {
      await api.updatePrompt(active.id, { content: draft, note: 'edit via UI' });
      toast('Prompt saved', 'success');
      load();
    } catch (e) { toast(`Save failed: ${e.message}`, 'error'); }
  }, [active, draft, load, toast]);

  const onReset = useCallback(async () => {
    if (!window.confirm('Reset ALL prompts to defaults?')) return;
    try { await api.resetPrompts(); toast('Prompts reset', 'success'); load(); }
    catch (e) { toast(`Reset failed: ${e.message}`, 'error'); }
  }, [load, toast]);

  if (error) return <div className="page"><div className="empty"><h3>Could not load prompts</h3><p className="mono">{error}</p></div></div>;
  if (!prompts) return <div className="page"><div className="empty">Loading…</div></div>;

  return (
    <div className="page">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div style={{ fontSize: 18, fontWeight: 700 }}>Prompts catalog</div>
        <button className="btn btn--danger" onClick={onReset}>Reset all to defaults</button>
      </div>

      <div className="prompt-editor mt-20">
        <div className="prompt-list">
          {prompts.map(p => (
            <div
              key={p.id}
              className={cx('prompt-list__item', p.id === activeId && 'prompt-list__item--active')}
              onClick={() => setActiveId(p.id)}
            >
              <div className="prompt-list__name">{p.name}</div>
              <div className="prompt-list__desc">{p.type} · v{p.version}{p.is_default ? ' · default' : ''}</div>
            </div>
          ))}
        </div>

        <div className="prompt-editor__main">
          {active ? (
            <>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontWeight: 700 }}>{active.name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{active.description}</div>
                </div>
                <div className="muted mono" style={{ fontSize: 12 }}>
                  {active.type} · v{active.version} · updated {fmtDate(active.updated_at)}
                </div>
              </div>
              <textarea className="prompt-content" value={draft} onChange={e => setDraft(e.target.value)} />
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div className="muted" style={{ fontSize: 12 }}>
                  {draft.length} chars · {draft !== active.content ? 'unsaved changes' : 'no changes'}
                </div>
                <div className="row">
                  <button className="btn" onClick={() => setDraft(active.content)} disabled={draft === active.content}>Discard</button>
                  <button className="btn btn--primary" onClick={onSave} disabled={draft === active.content}>Save</button>
                </div>
              </div>

              <div style={{ marginTop: 24, fontSize: 13, fontWeight: 700 }}>Audit log</div>
              <div className="col gap-sm" style={{ maxHeight: 220, overflowY: 'auto' }}>
                {audit.length === 0 ? <div className="muted">No audit entries.</div> :
                  audit.map((a, i) => (
                    <div key={i} className="muted mono" style={{ fontSize: 11 }}>
                      {fmtDate(a.timestamp)} {fmtTime(a.timestamp)} · {a.action} · {a.prompt_id}
                      {a.note && ` · ${a.note}`}
                    </div>
                  ))
                }
              </div>
            </>
          ) : <div className="empty">No prompt selected.</div>}
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────── Logs drawer (SSE) ─────────────────────── */

function LogsDrawer({ journeyId, jobId, onClose }) {
  const [logs, setLogs] = useState([]);
  const [job, setJob] = useState(null);
  const [status, setStatus] = useState('connecting');
  const endRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api.getJob(journeyId, jobId).then(j => !cancelled && setJob(j)).catch(() => {});
    api.jobLogs(journeyId, jobId).then(ls => !cancelled && setLogs(ls)).catch(() => {});
    return () => { cancelled = true; };
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
    es.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        if (payload.type === 'task_progress' && payload.data && payload.data.message) {
          setLogs(prev => [...prev, {
            timestamp: payload.timestamp,
            level: 'INFO',
            message: payload.data.message,
            step_id: payload.step_id,
          }]);
        } else if (payload.type === 'step_status') {
          setLogs(prev => [...prev, {
            timestamp: payload.timestamp,
            level: payload.data?.status === 'failed' ? 'ERROR' : 'INFO',
            message: `step ${payload.step_id}: ${payload.data?.status}${payload.data?.error ? ` (${payload.data.error})` : ''}`,
            step_id: payload.step_id,
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
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs.length]);

  return (
    <>
      <div className="drawer__backdrop" onClick={onClose} />
      <div className="drawer">
        <div className="drawer__header">
          <div>
            <div className="drawer__title">Job logs · <span className="mono">{fmtShortId(jobId, 14)}</span></div>
            <div className="drawer__subtitle">
              {job ? (
                <>
                  <span className={cx('pill', `pill--${status}`)}>{status}</span>
                  <span style={{ marginLeft: 8 }}>{job.stage_name}</span>
                  {job.duration_seconds != null && <span className="muted"> · {fmtDuration(job.duration_seconds)}</span>}
                </>
              ) : 'Loading…'}
            </div>
          </div>
          <button className="btn btn--ghost" onClick={onClose}>Close</button>
        </div>
        <div className="drawer__body">
          {logs.length === 0 ? (
            <div className="muted">No log lines yet.</div>
          ) : logs.map((l, i) => (
            <div key={i} className={cx('log-line', l.level === 'ERROR' && 'log-line--error', l.level === 'WARNING' && 'log-line--warning')}>
              <span className="log-line__time">{fmtTime(l.timestamp)}</span>
              {' '}
              {l.step_id && <span className="log-line__step">[{l.step_id}]</span>}
              {' '}
              {l.message}
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </div>
    </>
  );
}

/* ─────────────────────── App shell ─────────────────────── */

function App() {
  const hash = useHashRoute();
  const route = useMemo(() => parseRoute(hash), [hash]);

  let view;
  switch (route.name) {
    case 'journeys':  view = <JourneysListPage />; break;
    case 'studio':    view = <JourneyStudioPage journeyId={route.journeyId} />; break;
    case 'jobs':      view = <JobHistoryPage journeyId={route.journeyId} />; break;
    case 'schedules': view = <SchedulesPage />; break;
    case 'prompts':   view = <PromptsPage />; break;
    default:          view = <JourneysListPage />;
  }

  return (
    <ToastProvider>
      <TopBar route={route} />
      {view}
    </ToastProvider>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
