"""
Batch Scheduler Service

In-process asyncio scheduler that periodically triggers journey stage jobs.
Schedule configs are persisted in DynamoDB and survive pod restarts.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from botocore.exceptions import ClientError
from loguru import logger

from ..config import get_config
from ..adapters.aws import AWSClientManager


class SchedulerService:
    _instance: Optional['SchedulerService'] = None

    def __init__(self):
        self._config = get_config()
        self._client_manager = AWSClientManager(region_name=None)
        self._dynamodb = self._client_manager.create_resource('dynamodb')
        self._table = self._dynamodb.Table(self._config.dynamodb_transformation_table)
        self._schedules: Dict[str, dict] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._journey_service = None
        self._job_executor = None

    @classmethod
    def get_instance(cls) -> 'SchedulerService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_journey_service(self):
        if self._journey_service is None:
            from .journey_service import JourneyService
            self._journey_service = JourneyService()
        return self._journey_service

    def _get_job_executor(self):
        if self._job_executor is None:
            from ..execution.transformation_job_executor import TransformationJobExecutor
            self._job_executor = TransformationJobExecutor()
        return self._job_executor

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self):
        if self._running:
            return
        self._running = True
        self._load_schedules_from_db()
        enabled_count = sum(1 for s in self._schedules.values() if s.get('enabled'))
        logger.info(f"Scheduler started: {len(self._schedules)} schedules loaded ({enabled_count} enabled)")
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    # =========================================================================
    # DynamoDB CRUD
    # =========================================================================

    def _load_schedules_from_db(self):
        try:
            response = self._table.query(
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :pk',
                ExpressionAttributeValues={':pk': 'SCHEDULES'},
            )
            self._schedules = {}
            for item in response.get('Items', []):
                data = item.get('Data', {})
                schedule_id = data.get('scheduleId')
                if schedule_id:
                    self._schedules[schedule_id] = self._deserialize(data)
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")

    def _put_schedule(self, schedule: dict):
        schedule_id = schedule['scheduleId']
        now = datetime.now(timezone.utc).isoformat()
        item = {
            'PK': f'SCHEDULE#{schedule_id}',
            'SK': 'METADATA',
            'EntityType': 'BatchSchedule',
            'GSI1PK': 'SCHEDULES',
            'GSI1SK': f'SCHEDULE#{schedule_id}',
            'CreatedAt': schedule.get('createdAt', now),
            'UpdatedAt': now,
            'Data': self._serialize(schedule),
        }
        self._table.put_item(Item=item)

    def _delete_schedule_from_db(self, schedule_id: str):
        self._table.delete_item(
            Key={'PK': f'SCHEDULE#{schedule_id}', 'SK': 'METADATA'}
        )

    @staticmethod
    def _serialize(data: dict) -> dict:
        """Convert Python types to DynamoDB-safe types."""
        result = {}
        for k, v in data.items():
            if isinstance(v, float):
                result[k] = Decimal(str(v))
            elif isinstance(v, int) and not isinstance(v, bool):
                result[k] = Decimal(str(v))
            else:
                result[k] = v
        return result

    @staticmethod
    def _deserialize(data: dict) -> dict:
        """Convert DynamoDB Decimal back to int/float."""
        result = {}
        for k, v in data.items():
            if isinstance(v, Decimal):
                result[k] = int(v) if v == int(v) else float(v)
            else:
                result[k] = v
        return result

    # =========================================================================
    # Public API
    # =========================================================================

    def create_schedule(
        self,
        journey_id: str,
        stage_id: str,
        interval_minutes: int,
        enabled: bool = True,
        timezone_str: str = 'UTC',
        created_by: str = 'ui',
    ) -> dict:
        schedule_id = f"SCH-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        next_run = (datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)).isoformat()

        schedule = {
            'scheduleId': schedule_id,
            'journeyId': journey_id,
            'stageId': stage_id,
            'intervalMinutes': interval_minutes,
            'enabled': enabled,
            'timezone': timezone_str,
            'createdBy': created_by,
            'createdAt': now,
            'updatedAt': now,
            'lastRunAt': None,
            'nextRunAt': next_run,
            'lastJobId': None,
            'lastJobStatus': None,
        }
        self._put_schedule(schedule)
        self._schedules[schedule_id] = schedule
        logger.info(f"Schedule created: {schedule_id} for journey={journey_id} stage={stage_id} every {interval_minutes}m")
        return schedule

    def update_schedule(self, schedule_id: str, updates: dict) -> Optional[dict]:
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            self._load_schedules_from_db()
            schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None

        allowed_fields = {'intervalMinutes', 'enabled', 'timezone'}
        for key in allowed_fields:
            if key in updates:
                schedule[key] = updates[key]

        if 'intervalMinutes' in updates:
            last = schedule.get('lastRunAt')
            base = datetime.fromisoformat(last) if last else datetime.now(timezone.utc)
            schedule['nextRunAt'] = (base + timedelta(minutes=updates['intervalMinutes'])).isoformat()

        schedule['updatedAt'] = datetime.now(timezone.utc).isoformat()
        self._put_schedule(schedule)
        self._schedules[schedule_id] = schedule
        return schedule

    def delete_schedule(self, schedule_id: str) -> bool:
        if schedule_id not in self._schedules:
            self._load_schedules_from_db()
        if schedule_id not in self._schedules:
            return False
        self._delete_schedule_from_db(schedule_id)
        self._schedules.pop(schedule_id, None)
        logger.info(f"Schedule deleted: {schedule_id}")
        return True

    def toggle_schedule(self, schedule_id: str) -> Optional[dict]:
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            self._load_schedules_from_db()
            schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None
        new_enabled = not schedule.get('enabled', False)
        return self.update_schedule(schedule_id, {'enabled': new_enabled})

    def get_schedule(self, schedule_id: str) -> Optional[dict]:
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            self._load_schedules_from_db()
            schedule = self._schedules.get(schedule_id)
        if schedule and schedule.get('lastJobStatus') == 'in_progress':
            last_job_id = schedule.get('lastJobId')
            if last_job_id:
                try:
                    executor = self._get_job_executor()
                    job_data = executor.get_job_execution(schedule['journeyId'], last_job_id)
                    if job_data:
                        actual = job_data.get('status', 'unknown')
                        if actual != 'in_progress':
                            schedule['lastJobStatus'] = actual
                            self._put_schedule(schedule)
                            self._schedules[schedule_id] = schedule
                except Exception:
                    pass
        return schedule

    def list_schedules(self, journey_id: Optional[str] = None) -> List[dict]:
        self._load_schedules_from_db()
        self._sync_refresh_in_progress()
        schedules = list(self._schedules.values())
        if journey_id:
            schedules = [s for s in schedules if s.get('journeyId') == journey_id]
        return schedules

    def _sync_refresh_in_progress(self):
        """Synchronously update lastJobStatus for schedules showing in_progress."""
        for schedule in list(self._schedules.values()):
            if schedule.get('lastJobStatus') != 'in_progress':
                continue
            last_job_id = schedule.get('lastJobId')
            if not last_job_id:
                continue
            try:
                executor = self._get_job_executor()
                job_data = executor.get_job_execution(schedule['journeyId'], last_job_id)
                if job_data:
                    actual = job_data.get('status', 'unknown')
                    if actual != 'in_progress':
                        schedule['lastJobStatus'] = actual
                        self._put_schedule(schedule)
                        self._schedules[schedule['scheduleId']] = schedule
                elif job_data is None:
                    schedule['lastJobStatus'] = 'unknown'
                    self._put_schedule(schedule)
                    self._schedules[schedule['scheduleId']] = schedule
            except Exception:
                pass

    async def run_now(self, schedule_id: str) -> Optional[dict]:
        """Trigger a schedule's job immediately, bypassing the nextRunAt timer."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            self._load_schedules_from_db()
            schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None

        journey_id = schedule['journeyId']
        stage_id = schedule['stageId']
        interval = schedule.get('intervalMinutes', 5)

        logger.info(f"Run-now triggered: schedule={schedule_id} journey={journey_id} stage={stage_id}")

        from ..models.journey_model import JourneyActionRequest
        svc = self._get_journey_service()
        request = JourneyActionRequest(
            action='run_job',
            journey_id=journey_id,
            stage_id=stage_id,
            triggered_by='scheduler',
            reason='Manual run-now',
        )
        response = await svc.run_job(request)

        now = datetime.now(timezone.utc)
        schedule['lastRunAt'] = now.isoformat()
        schedule['nextRunAt'] = (now + timedelta(minutes=interval)).isoformat()

        if response.status == 'success' and response.job_id:
            schedule['lastJobId'] = response.job_id
            schedule['lastJobStatus'] = 'in_progress'
            logger.info(f"Run-now schedule {schedule_id}: triggered job {response.job_id}")
        else:
            schedule['lastJobStatus'] = 'failed'
            logger.warning(f"Run-now schedule {schedule_id}: trigger failed - {response.message}")

        schedule['updatedAt'] = now.isoformat()
        self._put_schedule(schedule)
        self._schedules[schedule_id] = schedule
        return schedule

    def reset_schedule(self, schedule_id: str) -> Optional[dict]:
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            self._load_schedules_from_db()
            schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None
        now = datetime.now(timezone.utc)
        interval = schedule.get('intervalMinutes', 5)
        schedule['lastJobId'] = None
        schedule['lastJobStatus'] = None
        schedule['lastRunAt'] = None
        schedule['nextRunAt'] = (now + timedelta(minutes=interval)).isoformat()
        schedule['updatedAt'] = now.isoformat()
        self._put_schedule(schedule)
        self._schedules[schedule_id] = schedule
        logger.info(f"Schedule reset: {schedule_id}")
        return schedule

    # =========================================================================
    # Scheduler Loop
    # =========================================================================

    async def _scheduler_loop(self):
        logger.info("Scheduler loop started (30s check interval)")
        while self._running:
            try:
                await asyncio.sleep(30)
                await self._check_and_trigger()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

    async def _check_and_trigger(self):
        self._load_schedules_from_db()

        await self._refresh_in_progress_statuses()

        now = datetime.now(timezone.utc)
        for schedule_id, schedule in list(self._schedules.items()):
            if not schedule.get('enabled'):
                continue

            next_run_str = schedule.get('nextRunAt')
            if not next_run_str:
                continue

            try:
                next_run = datetime.fromisoformat(next_run_str)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            if now < next_run:
                continue

            if await self._is_previous_job_running(schedule):
                logger.warning(f"Schedule {schedule_id}: previous job still running, skipping")
                continue

            await self._trigger_job(schedule)

    async def _refresh_in_progress_statuses(self):
        """Update lastJobStatus for any schedule stuck showing in_progress."""
        self._sync_refresh_in_progress()

    async def _is_previous_job_running(self, schedule: dict) -> bool:
        last_job_id = schedule.get('lastJobId')
        if not last_job_id:
            return False
        last_status = schedule.get('lastJobStatus')
        if last_status != 'in_progress':
            return False

        try:
            executor = self._get_job_executor()
            job_data = executor.get_job_execution(schedule['journeyId'], last_job_id)
            if job_data:
                actual_status = job_data.get('status', 'unknown')
                if actual_status != 'in_progress':
                    schedule['lastJobStatus'] = actual_status
                    self._put_schedule(schedule)
                    self._schedules[schedule['scheduleId']] = schedule
                    return False
            else:
                schedule['lastJobStatus'] = 'unknown'
                self._put_schedule(schedule)
                self._schedules[schedule['scheduleId']] = schedule
                return False
        except Exception as e:
            logger.warning(f"Failed to check job status for {last_job_id}: {e}")

        return True

    def _claim_schedule(self, schedule: dict) -> bool:
        """Atomically claim a schedule using conditional write (prevents multi-pod race)."""
        schedule_id = schedule['scheduleId']
        old_next_run = schedule.get('nextRunAt')
        interval = schedule.get('intervalMinutes', 5)
        now = datetime.now(timezone.utc)
        new_next_run = (now + timedelta(minutes=interval)).isoformat()

        try:
            self._table.update_item(
                Key={'PK': f'SCHEDULE#{schedule_id}', 'SK': 'METADATA'},
                UpdateExpression='SET #d.nextRunAt = :new_next, #d.lastRunAt = :now, UpdatedAt = :now_str',
                ConditionExpression='#d.nextRunAt = :old_next',
                ExpressionAttributeNames={'#d': 'Data'},
                ExpressionAttributeValues={
                    ':old_next': old_next_run,
                    ':new_next': new_next_run,
                    ':now': now.isoformat(),
                    ':now_str': now.isoformat(),
                },
            )
            schedule['nextRunAt'] = new_next_run
            schedule['lastRunAt'] = now.isoformat()
            schedule['updatedAt'] = now.isoformat()
            logger.info(f"Schedule {schedule_id}: claimed successfully")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.info(f"Schedule {schedule_id}: another pod already claimed this cycle")
                return False
            logger.warning(f"Schedule {schedule_id}: claim failed - {e}")
            return False
        except Exception as e:
            logger.warning(f"Schedule {schedule_id}: claim failed - {e}")
            return False

    async def _trigger_job(self, schedule: dict):
        schedule_id = schedule['scheduleId']
        journey_id = schedule['journeyId']
        stage_id = schedule['stageId']
        interval = schedule['intervalMinutes']

        if not self._claim_schedule(schedule):
            return

        logger.info(f"Scheduler triggering job: schedule={schedule_id} journey={journey_id} stage={stage_id}")
        try:
            from ..models.journey_model import JourneyActionRequest
            svc = self._get_journey_service()
            request = JourneyActionRequest(
                action='run_job',
                journey_id=journey_id,
                stage_id=stage_id,
                triggered_by='scheduler',
                reason=f'Scheduled execution (every {interval}m)',
            )
            response = await svc.run_job(request)

            if response.status == 'success' and response.job_id:
                schedule['lastJobId'] = response.job_id
                schedule['lastJobStatus'] = 'in_progress'
                logger.info(f"Schedule {schedule_id}: triggered job {response.job_id}")
            else:
                schedule['lastJobStatus'] = 'failed'
                logger.warning(f"Schedule {schedule_id}: trigger failed - {response.message}")

            self._put_schedule(schedule)
            self._schedules[schedule_id] = schedule

        except Exception as e:
            logger.error(f"Schedule {schedule_id}: trigger error - {e}")
