"""Worker registry and scaling via Kubernetes NexusCapability CR."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger

from .job_execution_config_service import get_job_execution_config
from .job_queue_service import (
    JOB_CONSUMER_GROUP,
    JOB_STREAM_KEY,
    get_active_job_count,
    is_queue_mode,
    list_consumers,
    redis_available,
)

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    K8S_AVAILABLE = True
except ImportError:
    client = None  # type: ignore
    config = None  # type: ignore
    ApiException = Exception  # type: ignore
    K8S_AVAILABLE = False

CRD_GROUP = "nexus.ai"
CRD_VERSION = "v1"
CRD_PLURAL = "nexuscapabilities"
KEDA_GROUP = "keda.sh"
KEDA_VERSION = "v1alpha1"
KEDA_PLURAL = "scaledobjects"


def _environment() -> str:
    return os.getenv("ENVIRONMENT", "dev")


def _capability_name() -> str:
    return os.getenv("CAPABILITY_NAME", "ai-engine")


def _namespace() -> str:
    return os.getenv("KUBERNETES_NAMESPACE") or os.getenv("POD_NAMESPACE") or f"{_capability_name()}-{_environment()}"


def _worker_deployment_name() -> str:
    return f"{_capability_name()}-{_environment()}-job-worker"


def _scaled_object_name() -> str:
    return f"{_worker_deployment_name()}-scaler"


def _redis_address_for_keda() -> str:
    url = os.getenv("REDIS_URL", "redis://redis-svc:6379/0")
    parsed = urlparse(url)
    host = parsed.hostname or "redis-svc"
    port = parsed.port or 6379
    if "." not in host:
        redis_namespace = os.getenv("REDIS_NAMESPACE", "nexus-local")
        host = f"{host}.{redis_namespace}.svc.cluster.local"
    return f"{host}:{port}"


def _consumer_pod_name(consumer_name: str) -> str:
    match = re.match(r"ai-engine-worker-(.+)-[0-9a-f]{6}$", consumer_name)
    if match:
        return match.group(1)
    return consumer_name


def _load_k8s_config() -> bool:
    if not K8S_AVAILABLE:
        return False
    try:
        config.load_incluster_config()
        return True
    except Exception:
        try:
            config.load_kube_config()
            return True
        except Exception:
            return False


class WorkerManagementService:
    def __init__(self) -> None:
        self._k8s_ready = _load_k8s_config()
        self._custom_api = client.CustomObjectsApi() if self._k8s_ready else None
        self._apps_api = client.AppsV1Api() if self._k8s_ready else None
        self._core_api = client.CoreV1Api() if self._k8s_ready else None

    @property
    def k8s_available(self) -> bool:
        return self._k8s_ready

    def _find_capability(self) -> Optional[Dict[str, Any]]:
        if not self._custom_api:
            return None
        try:
            items = self._custom_api.list_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=_namespace(),
                plural=CRD_PLURAL,
            ).get("items", [])
        except Exception as exc:
            logger.warning("Failed to list NexusCapability: {}", exc)
            return None

        for item in items:
            spec = item.get("spec") or {}
            if spec.get("capabilityName") == _capability_name():
                return item
        return items[0] if items else None

    def _deployment_status(self) -> Dict[str, Any]:
        if not self._apps_api:
            return {"desired": 0, "ready": 0, "available": 0, "name": _worker_deployment_name()}
        try:
            dep = self._apps_api.read_namespaced_deployment(
                name=_worker_deployment_name(),
                namespace=_namespace(),
            )
            status = dep.status or client.V1DeploymentStatus()
            spec = dep.spec or client.V1DeploymentSpec()
            return {
                "name": dep.metadata.name,
                "desired": spec.replicas or 0,
                "ready": status.ready_replicas or 0,
                "available": status.available_replicas or 0,
            }
        except ApiException as exc:
            if exc.status == 404:
                return {"desired": 0, "ready": 0, "available": 0, "name": _worker_deployment_name()}
            logger.warning("Failed to read worker deployment: {}", exc)
            return {"desired": 0, "ready": 0, "available": 0, "name": _worker_deployment_name()}

    def _list_worker_pods(self) -> List[Dict[str, Any]]:
        if not self._core_api:
            return []
        try:
            pods = self._core_api.list_namespaced_pod(
                namespace=_namespace(),
                label_selector=f"app={_worker_deployment_name()}",
            )
        except Exception as exc:
            logger.warning("Failed to list worker pods: {}", exc)
            return []

        rows: List[Dict[str, Any]] = []
        for pod in pods.items or []:
            status = pod.status or client.V1PodStatus()
            container_statuses = status.container_statuses or []
            restarts = sum(cs.restart_count or 0 for cs in container_statuses)
            rows.append(
                {
                    "worker_id": pod.metadata.name,
                    "phase": status.phase or "Unknown",
                    "start_time": status.start_time.isoformat() if status.start_time else None,
                    "restarts": restarts,
                }
            )
        return rows

    def _get_scaled_object(self) -> Optional[Dict[str, Any]]:
        if not self._custom_api:
            return None
        try:
            return self._custom_api.get_namespaced_custom_object(
                group=KEDA_GROUP,
                version=KEDA_VERSION,
                namespace=_namespace(),
                plural=KEDA_PLURAL,
                name=_scaled_object_name(),
            )
        except ApiException as exc:
            if exc.status == 404:
                return None
            logger.warning("Failed to read ScaledObject: {}", exc)
            return None
        except Exception as exc:
            logger.warning("Failed to read ScaledObject: {}", exc)
            return None

    def _autoscaling_from_scaled_object(self) -> Optional[Dict[str, Any]]:
        scaled_object = self._get_scaled_object()
        if not scaled_object:
            return None
        spec = scaled_object.get("spec") or {}
        lag_threshold = 5
        for trigger in spec.get("triggers") or []:
            if trigger.get("type") == "redis-streams":
                metadata = trigger.get("metadata") or {}
                lag_threshold = int(metadata.get("lagCount", lag_threshold))
                break
        return {
            "enabled": True,
            "min_replicas": int(spec.get("minReplicaCount", 1)),
            "max_replicas": int(spec.get("maxReplicaCount", 10)),
            "lag_threshold": lag_threshold,
            "keda_available": True,
        }

    def _autoscaling_from_cr(self, capability: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        keda_available = self._keda_installed()
        defaults = {
            "enabled": False,
            "min_replicas": 1,
            "max_replicas": get_job_execution_config().get_worker_replicas_desired(),
            "lag_threshold": 5,
            "keda_available": keda_available,
        }
        scaled = self._autoscaling_from_scaled_object()
        if scaled:
            return scaled

        if not capability:
            return defaults
        job_worker = (capability.get("spec") or {}).get("jobWorker") or {}
        autoscaling = job_worker.get("autoscaling") or {}
        return {
            "enabled": bool(autoscaling.get("enabled", False)),
            "min_replicas": int(autoscaling.get("minReplicas", job_worker.get("replicas", 1))),
            "max_replicas": int(autoscaling.get("maxReplicas", 10)),
            "lag_threshold": int(autoscaling.get("lagThreshold", 5)),
            "keda_available": keda_available,
        }

    def _keda_installed(self) -> bool:
        if not self._custom_api:
            return False
        try:
            self._custom_api.list_namespaced_custom_object(
                group="keda.sh",
                version="v1alpha1",
                namespace=_namespace(),
                plural="scaledobjects",
            )
            return True
        except Exception:
            return False

    def get_summary(self) -> Dict[str, Any]:
        consumers = list_consumers() if redis_available() else []
        active_consumers = sum(
            1 for c in consumers if c.get("status") in ("healthy", "idle")
        )
        stale_consumers = sum(1 for c in consumers if c.get("status") == "stale")
        deployment = self._deployment_status()
        capability = self._find_capability()
        autoscaling = self._autoscaling_from_cr(capability)
        job_worker = ((capability or {}).get("spec") or {}).get("jobWorker") or {}
        return {
            "queue_mode": is_queue_mode(),
            "redis_available": redis_available(),
            "k8s_available": self._k8s_ready,
            "deployment": deployment,
            "replicas": int(job_worker.get("replicas", deployment["desired"])),
            "consumers": active_consumers,
            "registered_consumers": len(consumers),
            "stale_consumers": stale_consumers,
            "healthy_consumers": active_consumers,
            "active_jobs": get_active_job_count() if redis_available() else 0,
            "autoscaling": autoscaling,
            "max_worker_replicas": int(os.getenv("JOB_WORKER_MAX_REPLICAS", "10")),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_workers(self) -> Dict[str, Any]:
        consumers = list_consumers() if redis_available() else []
        pods = self._list_worker_pods()
        pod_by_name = {p["worker_id"]: p for p in pods}

        rows: List[Dict[str, Any]] = []
        seen_pods: set[str] = set()

        for consumer in consumers:
            pod_name = _consumer_pod_name(consumer.get("consumer_name", ""))
            pod = pod_by_name.get(pod_name, {})
            consumer_status = consumer.get("status", "offline")
            # Drop stale Redis registrations left behind by replaced pods.
            if consumer_status == "stale" and pod_name not in pod_by_name:
                continue
            seen_pods.add(pod_name)
            rows.append(
                {
                    "worker_id": pod_name or consumer.get("consumer_name"),
                    "consumer_name": consumer.get("consumer_name"),
                    "status": consumer_status,
                    "pending_jobs": consumer.get("pending_jobs", 0),
                    "idle_ms": consumer.get("idle_ms", 0),
                    "current_job": consumer.get("current_job"),
                    "phase": pod.get("phase"),
                    "restarts": pod.get("restarts", 0),
                    "start_time": pod.get("start_time"),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                }
            )

        for pod in pods:
            if pod["worker_id"] in seen_pods:
                continue
            rows.append(
                {
                    "worker_id": pod["worker_id"],
                    "consumer_name": None,
                    "status": "offline" if pod.get("phase") != "Running" else "idle",
                    "pending_jobs": 0,
                    "idle_ms": 0,
                    "current_job": None,
                    "phase": pod.get("phase"),
                    "restarts": pod.get("restarts", 0),
                    "start_time": pod.get("start_time"),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                }
            )

        return {
            "workers": rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _patch_deployment_replicas(self, replicas: int) -> Dict[str, Any]:
        if not self._apps_api:
            raise RuntimeError("Kubernetes Apps API unavailable; cannot scale worker deployment")
        dep_name = _worker_deployment_name()
        ns = _namespace()
        try:
            self._apps_api.patch_namespaced_deployment(
                name=dep_name,
                namespace=ns,
                body={"spec": {"replicas": replicas}},
            )
        except ApiException as exc:
            logger.warning("Failed to scale deployment {}: {}", dep_name, exc)
            raise RuntimeError(f"Failed to scale deployment {dep_name}: {exc.reason}") from exc
        return self._deployment_status()

    def scale_workers(self, replicas: int) -> Dict[str, Any]:
        if not self._custom_api:
            raise RuntimeError("Kubernetes API unavailable; cannot scale workers")
        max_replicas = int(os.getenv("JOB_WORKER_MAX_REPLICAS", "10"))
        replicas = max(0, min(replicas, max_replicas))

        capability = self._find_capability()
        if not capability:
            raise RuntimeError("NexusCapability not found in namespace")

        name = capability["metadata"]["name"]
        deployment = self._patch_deployment_replicas(replicas)

        # Keep CR in sync when jobWorker is configured (operator-managed clusters).
        body = {
            "spec": {
                "jobWorker": {
                    **((capability.get("spec") or {}).get("jobWorker") or {}),
                    "enabled": replicas > 0,
                    "replicas": replicas,
                }
            }
        }
        try:
            self._custom_api.patch_namespaced_custom_object(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=_namespace(),
                plural=CRD_PLURAL,
                name=name,
                body=body,
            )
        except Exception as exc:
            logger.warning("NexusCapability jobWorker patch skipped: {}", exc)

        return {
            "replicas": replicas,
            "capability": name,
            "deployment": deployment,
        }

    def _reconcile_keda_autoscaling(
        self,
        *,
        enabled: bool,
        min_replicas: int,
        max_replicas: int,
        lag_threshold: int,
    ) -> None:
        if not self._custom_api:
            raise RuntimeError("Kubernetes API unavailable; cannot configure autoscaling")

        name = _scaled_object_name()
        if not enabled:
            try:
                self._custom_api.delete_namespaced_custom_object(
                    group=KEDA_GROUP,
                    version=KEDA_VERSION,
                    namespace=_namespace(),
                    plural=KEDA_PLURAL,
                    name=name,
                )
                logger.info("Deleted ScaledObject {}", name)
            except ApiException as exc:
                if exc.status != 404:
                    raise
            return

        body = {
            "apiVersion": f"{KEDA_GROUP}/{KEDA_VERSION}",
            "kind": "ScaledObject",
            "metadata": {
                "name": name,
                "namespace": _namespace(),
            },
            "spec": {
                "scaleTargetRef": {"name": _worker_deployment_name()},
                "minReplicaCount": min_replicas,
                "maxReplicaCount": max_replicas,
                "pollingInterval": 15,
                "cooldownPeriod": 60,
                "triggers": [
                    {
                        "type": "redis-streams",
                        "metadata": {
                            "address": _redis_address_for_keda(),
                            "stream": JOB_STREAM_KEY,
                            "consumerGroup": JOB_CONSUMER_GROUP,
                            "lagCount": str(lag_threshold),
                        },
                    }
                ],
            },
        }
        try:
            self._custom_api.create_namespaced_custom_object(
                group=KEDA_GROUP,
                version=KEDA_VERSION,
                namespace=_namespace(),
                plural=KEDA_PLURAL,
                body=body,
            )
            logger.info("Created ScaledObject {}", name)
        except ApiException as exc:
            if exc.status != 409:
                raise
            self._custom_api.patch_namespaced_custom_object(
                group=KEDA_GROUP,
                version=KEDA_VERSION,
                namespace=_namespace(),
                plural=KEDA_PLURAL,
                name=name,
                body=body,
            )
            logger.info("Patched ScaledObject {}", name)

    def configure_autoscaling(
        self,
        *,
        enabled: bool,
        min_replicas: int,
        max_replicas: int,
        lag_threshold: int,
    ) -> Dict[str, Any]:
        if not self._custom_api:
            raise RuntimeError("Kubernetes API unavailable; cannot configure autoscaling")

        capability = self._find_capability()

        if max_replicas < min_replicas:
            raise ValueError("max_replicas must be >= min_replicas")

        self._reconcile_keda_autoscaling(
            enabled=enabled,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            lag_threshold=lag_threshold,
        )
        if enabled:
            self._patch_deployment_replicas(min_replicas)

        name = (capability or {}).get("metadata", {}).get("name", f"{_capability_name()}-{_environment()}")
        if capability:
            job_worker = dict((capability.get("spec") or {}).get("jobWorker") or {})
            job_worker["autoscaling"] = {
                "enabled": enabled,
                "minReplicas": min_replicas,
                "maxReplicas": max_replicas,
                "lagThreshold": lag_threshold,
            }
            if enabled:
                job_worker["replicas"] = min_replicas

            body = {"spec": {"jobWorker": job_worker}}
            try:
                self._custom_api.patch_namespaced_custom_object(
                    group=CRD_GROUP,
                    version=CRD_VERSION,
                    namespace=_namespace(),
                    plural=CRD_PLURAL,
                    name=name,
                    body=body,
                )
            except Exception as exc:
                logger.warning("NexusCapability jobWorker autoscaling patch skipped: {}", exc)
        return {
            "enabled": enabled,
            "min_replicas": min_replicas,
            "max_replicas": max_replicas,
            "lag_threshold": lag_threshold,
            "capability": name,
        }


_service: WorkerManagementService | None = None


def get_worker_management_service() -> WorkerManagementService:
    global _service
    if _service is None:
        _service = WorkerManagementService()
    return _service
