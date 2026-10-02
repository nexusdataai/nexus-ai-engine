"""Operations runbooks: stale jobs and pod crash analysis for this ai-engine."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from loguru import logger

from .stale_job_manager import StaleJobManager, StaleJobRecord, _get_transformation_table


def _namespace() -> str:
    cap = os.getenv("CAPABILITY_NAME", "ai-engine")
    env = os.getenv("ENVIRONMENT") or os.getenv("DEPLOY_ENV") or "local"
    return os.getenv("KUBERNETES_NAMESPACE") or os.getenv("POD_NAMESPACE") or f"{cap}-{env}"


class RunbooksService:
    def list_stale_jobs(self, threshold_min: Optional[int] = None) -> Dict[str, Any]:
        table = _get_transformation_table()
        manager = StaleJobManager(table, threshold_min=threshold_min) if threshold_min else StaleJobManager(table)
        result = manager.scan()
        return {
            "summary": result.summary,
            "jobs": [asdict(j) for j in result.jobs],
            "blocked_schedules": [asdict(s) for s in result.blocked_schedules],
        }

    def cancel_stale_jobs(
        self,
        *,
        skip_unverified_long: bool = True,
        reason: str = "Cancelled via Operations runbook UI",
    ) -> Dict[str, Any]:
        table = _get_transformation_table()
        manager = StaleJobManager(table)
        scan = manager.scan()
        return {
            "scan_summary": scan.summary,
            "cancel": manager.cancel_jobs(scan.jobs, skip_unverified_long=skip_unverified_long, reason=reason),
            "unblock_schedules": manager.unblock_schedules(scan.blocked_schedules),
        }

    def cancel_job(self, job: Dict[str, Any], reason: str = "Cancelled via Operations runbook UI") -> Dict[str, Any]:
        table = _get_transformation_table()
        manager = StaleJobManager(table)
        record = StaleJobRecord(
            job_id=job["job_id"],
            journey_id=job["journey_id"],
            stage_id=job.get("stage_id", ""),
            current_step=job.get("current_step", ""),
            age_min=float(job.get("age_min", 0)),
            confidence=job.get("confidence", "STALE"),
            pk=job["pk"],
            sk=job["sk"],
        )
        ok = manager._cancel_one(record, reason=reason)
        return {"job_id": record.job_id, "cancelled": ok}

    def list_crashed_pods(self, component: str = "", *, log_tail: int = 100) -> Dict[str, Any]:
        namespace = _namespace()
        try:
            from kubernetes import client, config
        except ImportError:
            return {"namespace": namespace, "available": False, "message": "kubernetes package not installed", "pods": [], "count": 0}

        try:
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()
            v1 = client.CoreV1Api()
            pod_list = v1.list_namespaced_pod(namespace=namespace)
        except Exception as exc:
            logger.warning("Crash analyzer unavailable: {}", exc)
            return {"namespace": namespace, "available": False, "message": str(exc), "pods": [], "count": 0}

        pods: List[Dict[str, Any]] = []
        for pod in pod_list.items:
            name = pod.metadata.name or ""
            if component and component not in name:
                continue
            statuses = pod.status.container_statuses or []
            restarts = sum((cs.restart_count or 0) for cs in statuses)
            if restarts <= 0:
                continue
            containers = []
            analysis: List[str] = []
            for cs in statuses:
                term = cs.last_state.terminated if cs.last_state and cs.last_state.terminated else None
                last_terminated = None
                if term:
                    last_terminated = {
                        "reason": term.reason,
                        "exit_code": term.exit_code,
                        "finished_at": term.finished_at.isoformat() if term.finished_at else None,
                        "message": term.message,
                    }
                    if term.reason:
                        analysis.append(f"{cs.name}: {term.reason} (exit {term.exit_code})")
                    if term.reason == "OOMKilled":
                        analysis.append(f"{cs.name} was OOMKilled — check memory limits")
                prev_log = None
                if term:
                    try:
                        prev_log = v1.read_namespaced_pod_log(
                            name=name,
                            namespace=namespace,
                            container=cs.name,
                            previous=True,
                            tail_lines=log_tail,
                        )
                    except Exception:
                        prev_log = None
                containers.append(
                    {
                        "name": cs.name,
                        "restart_count": cs.restart_count or 0,
                        "last_terminated": last_terminated,
                        "previous_log_tail": prev_log,
                    }
                )
            events: List[Dict[str, Any]] = []
            try:
                evs = v1.list_namespaced_event(namespace=namespace, field_selector=f"involvedObject.name={name}")
                for ev in (evs.items or [])[-8:]:
                    events.append(
                        {
                            "type": ev.type,
                            "reason": ev.reason,
                            "message": ev.message,
                            "last_seen": ev.last_timestamp.isoformat() if ev.last_timestamp else None,
                        }
                    )
            except Exception:
                pass
            pods.append(
                {
                    "name": name,
                    "phase": pod.status.phase,
                    "restarts": restarts,
                    "node": pod.spec.node_name if pod.spec else None,
                    "started_at": pod.status.start_time.isoformat() if pod.status.start_time else None,
                    "analysis": analysis,
                    "containers": containers,
                    "events": events,
                }
            )
        pods.sort(key=lambda p: p["restarts"], reverse=True)
        return {
            "namespace": namespace,
            "available": True,
            "via_operator": False,
            "log_tail_lines": log_tail,
            "pods": pods,
            "count": len(pods),
        }


_service: Optional[RunbooksService] = None


def get_runbooks_service() -> RunbooksService:
    global _service
    if _service is None:
        _service = RunbooksService()
    return _service
