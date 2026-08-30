# job_executor.py - Refactored for Stage-based Architecture
import boto3
import json
import logging
import os
import time
import uuid
import inspect
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

# Import the stage registry from the stages package
from ..stages import get_stage_class, list_available_stages
from ..adapters.aws import AWSClientManager
from ..config import get_config

# Import SSE manager for real-time updates
try:
    from ..events.sse_manager import emit_step_status, emit_log, emit_task_progress, emit_job_complete
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False
    # Define no-op functions if SSE not available
    def emit_step_status(*args, **kwargs): pass
    def emit_log(*args, **kwargs): pass
    def emit_task_progress(*args, **kwargs): pass
    def emit_job_complete(*args, **kwargs): pass


class JobCancelledException(Exception):
    pass


class TransformationJobExecutor:
    _cancelled_jobs: set = set()

    @classmethod
    def cancel_job_execution(cls, job_id: str):
        cls._cancelled_jobs.add(job_id)

    @classmethod
    def is_job_cancelled(cls, job_id: str) -> bool:
        return job_id in cls._cancelled_jobs

    def __init__(self, region_name: str = None, role_arn: Optional[str] = None):
        """
        Initialize the TransformationJobExecutor.
        
        Args:
            region_name: AWS region name (optional)
            role_arn: AWS role ARN to assume (optional)
        """
        self.role_arn = role_arn or os.environ.get('AWS_ROLE_ARN')
        self.region_name = region_name
        
        # Get configuration
        self._config = get_config()
        
        # Create AWS client manager
        self.client_manager = AWSClientManager(role_arn=self.role_arn, region_name=self.region_name)
        
        # Create AWS clients using the client manager
        self.dynamodb = self.client_manager.create_resource('dynamodb')
        self.s3 = self.client_manager.create_client('s3')
        self.table = self.dynamodb.Table(self._config.dynamodb_transformation_table)
        self.logs_bucket = self._config.s3_journey_logs_bucket
        self.reports_bucket = self._config.s3_journey_reports_bucket

        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Log the configuration
        if self.role_arn:
            self.logger.info(f"Job executor configured with role ARN: {self.role_arn}")
        else:
            self.logger.info("Job executor configured with default credential chain")

    def _write_to_dlq(
        self,
        job_id: str,
        journey_id: str,
        stage_id: str,
        error: str,
        context: dict | None = None,
    ) -> None:
        """Write failed job to dead letter queue for later inspection/retry."""
        try:
            from .. import resource_naming as rn

            cfg = get_config()
            table_name = os.getenv("DYNAMODB_DLQ_TABLE") or rn.dynamodb_table_name(
                "dlq", capability=cfg.capability_name, environment=cfg.environment
            )
            table = self.dynamodb.Table(table_name)
            now = datetime.utcnow().isoformat() + "Z"
            table.put_item(
                Item={
                    "PK": "dlq",
                    "SK": f"{now}#{job_id}",
                    "EntityType": "JobDLQ",
                    "job_id": job_id,
                    "journey_id": journey_id,
                    "stage_id": stage_id,
                    "error": str(error)[:2000],
                    "context": str(context)[:5000] if context else "",
                    "timestamp": now,
                    "status": "pending_review",
                }
            )
        except Exception as exc:
            self.logger.warning("DLQ write failed for job %s: %s", job_id, exc)

    def _get_journey_pk(self, journey_id: str) -> str:
        """Helper method to get the correct DynamoDB PK for a journey.
        Uses the same format as journey service: JOURNEY#{journey_id}"""
        return f'JOURNEY#{journey_id}'

    def _job_sk(self, job_data: Dict, job_id: str) -> str:
        """Build DynamoDB SK for a job record."""
        if job_data.get('jobType') == 'journey':
            execution_number = int(job_data.get('executionNumber', 0))
            timestamp = job_id.split('-')[-1]
            return f'JOB#JRN#{execution_number:03d}#{timestamp}'
        stage_id = job_data['stageId']
        execution_number = job_data['executionNumber']
        timestamp = job_id.split('-')[-1]
        return f'JOB#{int(job_data["stageOrder"]):02d}#{stage_id}#{int(execution_number):03d}#{timestamp}'

    def get_journey_stages_ordered(self, journey_id: str) -> List[Dict]:
        """List journey stages from DynamoDB ordered by pipeline sequence."""
        try:
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': self._get_journey_pk(journey_id),
                    ':sk': 'STAGE#',
                },
            )
            stages = [item['Data'] for item in response.get('Items', []) if item.get('Data')]
            stages.sort(key=lambda s: s.get('order', 0))
            return stages
        except Exception as e:
            self.logger.error(f'Error listing journey stages: {str(e)}')
            return []

    def get_next_journey_execution_number(self, journey_id: str) -> int:
        """Next execution number for journey-level (multi-stage) jobs."""
        try:
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': self._get_journey_pk(journey_id),
                    ':sk': 'JOB#',
                },
                ScanIndexForward=False,
            )
            max_num = 0
            for item in response.get('Items', []):
                data = item.get('Data', {})
                if data.get('jobType') == 'journey':
                    max_num = max(max_num, int(data.get('executionNumber', 0)))
                elif item.get('SK', '').startswith('JOB#JRN#'):
                    max_num = max(max_num, int(data.get('executionNumber', 0)))
            return max_num + 1 if max_num else 1
        except Exception as e:
            self.logger.error(f'Error getting journey execution number: {str(e)}')
            return 1

    def start_journey_job_execution(
        self,
        journey_id: str,
        stage_ids: Optional[List[str]] = None,
        triggered_by: str = 'system',
        reason: str = 'Journey pipeline execution',
    ) -> str:
        """Start a single journey-level job that runs all stages sequentially."""
        journey = self.get_journey(journey_id)
        if not journey:
            raise Exception(f'Journey {journey_id} not found')

        stages = self.get_journey_stages_ordered(journey_id)
        if stage_ids:
            wanted = set(stage_ids)
            stages = [s for s in stages if s.get('stageId') in wanted]
        if not stages:
            raise ValueError(f'No stages configured for journey {journey_id}')

        stage_ids_ordered = [s['stageId'] for s in stages]
        for sid in stage_ids_ordered:
            if sid not in list_available_stages():
                raise ValueError(f'Stage {sid} not implemented. Available: {", ".join(list_available_stages())}')

        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        execution_number = self.get_next_journey_execution_number(journey_id)
        job_id = f'JOB-{execution_number:03d}-{timestamp}'
        sk = f'JOB#JRN#{execution_number:03d}#{timestamp}'

        stage_results: Dict[str, Any] = {}
        total_steps = 0
        for stage_row in stages:
            sid = stage_row['stageId']
            stage_info = self.get_stage_info(sid)
            if not stage_info:
                raise ValueError(f'Stage {sid} not found in stage registry')
            steps = stage_info['steps']
            total_steps += len(steps)
            stage_results[sid] = {
                'stageId': sid,
                'stageName': stage_info.get('stage_name', sid),
                'status': 'pending',
                'stepResults': {
                    step['id']: {'status': 'pending', 'progress': Decimal('0')}
                    for step in steps
                },
            }

        first_stage_id = stage_ids_ordered[0]
        first_stage_info = self.get_stage_info(first_stage_id)
        first_steps = first_stage_info['steps']

        job_item = {
            'PK': self._get_journey_pk(journey_id),
            'SK': sk,
            'EntityType': 'JobExecution',
            'GSI1PK': f'JOURNEYJOB#{journey_id}',
            'GSI1SK': datetime.utcnow().isoformat() + 'Z',
            'CreatedAt': datetime.utcnow().isoformat() + 'Z',
            'UpdatedAt': datetime.utcnow().isoformat() + 'Z',
            'Data': {
                'jobId': job_id,
                'jobType': 'journey',
                'journeyId': journey_id,
                'stageIds': stage_ids_ordered,
                'stageId': first_stage_id,
                'stageName': journey.get('name', journey_id),
                'currentStageId': first_stage_id,
                'currentStageIndex': 0,
                'totalStages': len(stage_ids_ordered),
                'totalSteps': total_steps,
                'stageResults': stage_results,
                'executionNumber': execution_number,
                'status': 'in_progress',
                'startTime': datetime.utcnow().isoformat() + 'Z',
                'endTime': None,
                'duration': None,
                'progress': Decimal('0'),
                'triggeredBy': triggered_by,
                'triggerReason': reason,
                'retryAttempt': 0,
                's3Config': {
                    'logsBucket': self.logs_bucket,
                    'logsPrefix': f'journeys/{journey_id}/executions/{job_id}/',
                    'reportsBucket': self.reports_bucket,
                    'reportsPrefix': f'journeys/{journey_id}/executions/{job_id}/',
                    'region': self.region_name,
                },
                'currentStepIndex': 0,
                'currentStepId': first_steps[0]['id'] if first_steps else None,
                'stepResults': stage_results[first_stage_id]['stepResults'],
                'jobMetrics': {
                    'totalLogs': 0,
                    'totalErrors': 0,
                    'totalWarnings': 0,
                    'overallProgress': Decimal('0'),
                    'itemsProcessed': 0,
                    'itemsTotal': 0,
                },
            },
        }

        self.table.put_item(Item=job_item)
        self.logger.info(
            f'✅ Started journey job {job_id} for {len(stage_ids_ordered)} stages: {", ".join(stage_ids_ordered)}'
        )
        return job_id

    def start_job_execution(
        self,
        journey_id: str,
        stage_id: str,
        triggered_by: str = 'system',
        reason: str = 'Automated execution',
    ) -> str:
        """Start a new job execution for a stage"""
        try:
            self.logger.info(f'🚀 Starting job execution for journey: {journey_id}, stage: {stage_id}')
            self.logger.info(f'📊 Using DynamoDB table: {self.table.table_name}')
            
            # Get journey metadata
            journey = self.get_journey(journey_id)
            if not journey:
                self.logger.error(f'❌ Journey {journey_id} not found - cannot create job')
                raise Exception(f'Journey {journey_id} not found')

            self.logger.info(f'✅ Journey {journey_id} found successfully')

            # Validate stage is available first (quick check)
            available_stages = list_available_stages()
            if stage_id not in available_stages:
                self.logger.error(f'❌ Stage {stage_id} not implemented. Available stages: {", ".join(available_stages)}')
                raise ValueError(f'Stage {stage_id} not implemented. Available stages: {", ".join(available_stages)}')
            
            # Get stage definition from stage class (not DynamoDB)
            stage_def = self.get_stage_info(stage_id)
            if not stage_def:
                self.logger.error(f'❌ Stage {stage_id} not found in stage registry')
                raise ValueError(f'Stage {stage_id} not found in stage registry')
            
            # Stage definition from class always has all required fields
            self.logger.info(f'Using stage definition: {stage_def["stage_name"]} with {len(stage_def["steps"])} steps')

            # Generate job ID and execution number
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            execution_number = self.get_next_execution_number(journey_id, stage_id)
            job_id = f'JOB-{execution_number:03d}-{timestamp}'

            self.logger.info(f'📋 Generated job ID: {job_id}, execution number: {execution_number}')

            # Extract stage info with proper field mapping
            stage_name = stage_def.get('stage_name', stage_id)
            stage_order = stage_def.get('order', 0)  # Default order 0
            
            # Create job execution record
            job_data = {
                'PK': self._get_journey_pk(journey_id),
                'SK': f'JOB#{stage_order:02d}#{stage_id}#{execution_number:03d}#{timestamp}',
                'EntityType': 'JobExecution',
                'GSI1PK': f'STAGE#{journey_id}#{stage_id}',
                'GSI1SK': datetime.utcnow().isoformat() + 'Z',
                'CreatedAt': datetime.utcnow().isoformat() + 'Z',
                'UpdatedAt': datetime.utcnow().isoformat() + 'Z',
                'Data': {
                    'jobId': job_id,
                    'jobType': 'stage',
                    'journeyId': journey_id,
                    'stageId': stage_id,
                    'stageName': stage_name,
                    'stageOrder': stage_order,
                    'executionNumber': execution_number,
                    'status': 'in_progress',
                    'startTime': datetime.utcnow().isoformat() + 'Z',
                    'endTime': None,
                    'duration': None,
                    'progress': Decimal('0'),
                    'triggeredBy': triggered_by,
                    'triggerReason': reason,
                    'retryAttempt': 0,
                    's3Config': {
                        'logsBucket': self.logs_bucket,
                        'logsPrefix': f'journeys/{journey_id}/stages/{stage_id}/executions/{job_id}/',
                        'reportsBucket': self.reports_bucket,
                        'reportsPrefix': f'journeys/{journey_id}/stages/{stage_id}/executions/{job_id}/',
                        'region': self.region_name,
                    },
                    'currentStepIndex': 0,
                    'currentStepId': stage_def['steps'][0]['id'],
                    'stepResults': {
                        step['id']: {'status': 'pending', 'progress': Decimal('0')}
                        for step in stage_def['steps']
                    },
                    'jobMetrics': {
                        'totalLogs': 0,
                        'totalErrors': 0,
                        'totalWarnings': 0,
                        'overallProgress': Decimal('0'),
                        'itemsProcessed': 0,
                        'itemsTotal': 0,
                    },
                },
            }

            # Save job to DynamoDB
            self.table.put_item(Item=job_data)

            # Update journey current job
            self.update_journey_current_job(journey_id, stage_id, job_id, execution_number)

            self.logger.info(f'✅ Started job execution: {job_id} for stage {stage_id}')
            
            # Return the job ID - the caller will execute the job
            return job_id

        except Exception as e:
            self.logger.error(f'❌ Error starting job execution: {str(e)}')
            raise

    def execute_job(self, journey_id: str, job_id: str):
        """Execute a job — single stage or full journey pipeline."""
        job_data = self.get_job_execution(journey_id, job_id)
        if not job_data:
            self.logger.error(f'❌ Job {job_id} not found for journey {journey_id}')
            raise ValueError(f'Job {job_id} not found')
        if job_data.get('jobType') == 'journey':
            return self.execute_journey_job(journey_id, job_id)
        return self._execute_stage_job(journey_id, job_id, job_data)

    def execute_journey_job(self, journey_id: str, job_id: str):
        """Execute all stages in a journey-level job sequentially."""
        job_data = self.get_job_execution(journey_id, job_id)
        if not job_data:
            raise ValueError(f'Job {job_id} not found')

        stage_ids = job_data.get('stageIds') or [job_data.get('stageId')]
        total_stages = len(stage_ids)
        total_items_processed = 0
        total_items_total = 0
        combined_metrics: Dict[str, Any] = {}

        try:
            for stage_index, stage_id in enumerate(stage_ids):
                if self.is_job_cancelled(job_id):
                    raise JobCancelledException(f'Job {job_id} cancelled')

                stage_info = self.get_stage_info(stage_id)
                if not stage_info:
                    raise ValueError(f'Stage {stage_id} not available')

                self._set_journey_current_stage(journey_id, job_id, stage_id, stage_index, stage_info)
                self.logger.info(
                    f'🚀 Journey job {job_id}: stage {stage_index + 1}/{total_stages} — {stage_id}'
                )

                metrics = self._execute_single_stage(journey_id, job_id, stage_id)
                total_items_processed += int(metrics.get('items_processed', 0))
                total_items_total += int(metrics.get('items_total', 0))
                combined_metrics.update(metrics.get('detailed_metrics', {}))
                self._complete_journey_stage(journey_id, job_id, stage_id, stage_index, total_stages)

            self.complete_job(
                journey_id,
                job_id,
                total_items_processed,
                total_items_total,
                combined_metrics,
            )
            self.logger.info(f'🎉 Journey job {job_id} completed all {total_stages} stages')
            from ..stages import BaseStage
            BaseStage._last_db_cancel_check.pop(job_id, None)

        except JobCancelledException:
            self.logger.info(f'🛑 Journey job {job_id} was cancelled')
            self._cancelled_jobs.discard(job_id)
            from ..stages import BaseStage
            BaseStage._last_db_cancel_check.pop(job_id, None)
        except Exception as e:
            self.logger.error(f'❌ Journey job {job_id} failed: {str(e)}')
            self.fail_job(journey_id, job_id, str(e))
            raise

    def _execute_stage_job(self, journey_id: str, job_id: str, job_data: Dict):
        """Execute a legacy single-stage job."""
        stage_id = job_data['stageId']
        try:
            metrics = self._execute_single_stage(journey_id, job_id, stage_id)
            self.complete_job(
                journey_id,
                job_id,
                metrics.get('items_processed', 0),
                metrics.get('items_total', 0),
                metrics.get('detailed_metrics'),
            )
            self.logger.info(f'🎉 Job {job_id} completed successfully')
            from ..stages import BaseStage
            BaseStage._last_db_cancel_check.pop(job_id, None)
        except JobCancelledException:
            self.logger.info(f'🛑 Job {job_id} was cancelled')
            self._cancelled_jobs.discard(job_id)
            from ..stages import BaseStage
            BaseStage._last_db_cancel_check.pop(job_id, None)
        except Exception as e:
            self.logger.error(f'❌ Error executing job {job_id}: {str(e)}')
            self.fail_job(journey_id, job_id, str(e))
            raise

    def _execute_single_stage(self, journey_id: str, job_id: str, stage_id: str) -> Dict[str, Any]:
        """Run all steps for one stage; returns aggregated metrics for the stage."""
        if stage_id not in list_available_stages():
            raise ValueError(f'Stage {stage_id} not available for execution')

        stage_class = get_stage_class(stage_id)
        if not stage_class:
            raise ValueError(f'Stage class not found for stage: {stage_id}')

        stage = stage_class(journey_id, stage_id, job_id, self.region_name, self.role_arn)
        steps = stage.steps

        self.logger.info(f'🚀 Executing stage {stage_id} in job {job_id} ({len(steps)} steps)')

        for step_index, step in enumerate(steps):
            step_id = step['id']

            if self.is_job_cancelled(job_id):
                raise JobCancelledException(f'Job {job_id} cancelled')

            self.logger.info(f'📝 Step {step_index + 1}/{len(steps)}: {step["name"]} ({step_id})')

            try:
                self.update_step_status(journey_id, job_id, step_id, 'in_progress', step_index, stage_id=stage_id)
                step_result = stage.execute_step(step_id, step)

                if self.is_job_cancelled(job_id):
                    raise JobCancelledException(f'Job {job_id} cancelled')

                self.update_step_results(journey_id, job_id, step_id, step_result, stage_id=stage_id)
                self.update_job_progress(journey_id, job_id, step_index, stage_id, len(steps))
                self.logger.info(f'✅ Completed step: {step["name"]} ({step_id})')

            except JobCancelledException:
                raise
            except Exception as step_error:
                self.logger.error(f'❌ Error in step {step_id}: {str(step_error)}')
                raise step_error

        items_processed = 0
        items_total = 0
        detailed_metrics: Dict[str, Any] = {}

        if stage_id == 'order_to_cash' and hasattr(stage, '_processor'):
            proc = stage._processor
            items_total = len(getattr(proc, '_resolved_orders', []))
            items_processed = len(getattr(proc, '_risk_ranked', []))
            alerts = getattr(proc, '_alerts', [])
            detailed_metrics = {
                'ordersResolved': items_total,
                'ordersRanked': items_processed,
                'alertsGenerated': len(alerts) if isinstance(alerts, list) else 0,
            }
        elif hasattr(stage, 'metrics'):
            metrics = stage.metrics
            if 'process_recordings' in metrics:
                items_processed = metrics['process_recordings'].get('processed', 0)
            if 'fetch_tasks' in metrics:
                items_total = metrics['fetch_tasks'].get('tasks_found', 0)
            if not items_processed and 'crm_actions' in metrics:
                items_processed = metrics['crm_actions'].get('calls_considered', 0)
            if not items_processed and 'processed' in metrics:
                items_processed = metrics.get('processed', 0)
            if not items_total and 'tasks_found' in metrics:
                items_total = metrics.get('tasks_found', 0)
            detailed_metrics = {
                'availableCalls': metrics.get('fetch_tasks', {}).get('tasks_found', 0),
                'newTasks': metrics.get('deduplication', {}).get('new_tasks', 0),
                'skippedTasks': metrics.get('deduplication', {}).get('skipped_tasks', 0),
                'successfulProcessing': metrics.get('process_recordings', {}).get('processed', 0),
                'failedProcessing': metrics.get('process_recordings', {}).get('failed', 0),
                'noRecording': metrics.get('process_recordings', {}).get('no_recording', 0),
                'transcriptsCollected': metrics.get('process_recordings', {}).get('transcripts_collected', 0),
                'analyzed': metrics.get('ai_analysis', {}).get('analyzed', 0),
            }

        return {
            'items_processed': items_processed,
            'items_total': items_total,
            'detailed_metrics': detailed_metrics,
        }

    def _set_journey_current_stage(
        self, journey_id: str, job_id: str, stage_id: str, stage_index: int, stage_info: Dict
    ):
        """Switch active stage context on a journey-level job."""
        job_data = self.get_job_execution(journey_id, job_id)
        if not job_data:
            return
        sk = self._job_sk(job_data, job_id)
        steps = stage_info.get('steps', [])
        stage_results = job_data.get('stageResults', {})
        stage_entry = stage_results.get(stage_id, {})
        step_results = stage_entry.get('stepResults') or {
            step['id']: {'status': 'pending', 'progress': Decimal('0')} for step in steps
        }

        self.table.update_item(
            Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
            UpdateExpression=(
                'SET #data.currentStageId = :stage_id, #data.currentStageIndex = :stage_index, '
                '#data.stageId = :stage_id, #data.stepResults = :step_results, '
                '#data.currentStepIndex = :zero, #data.currentStepId = :first_step, '
                '#data.stageResults.#stage_id.#status = :running, #data.updatedAt = :updated_at'
            ),
            ExpressionAttributeNames={
                '#data': 'Data',
                '#stage_id': stage_id,
                '#status': 'status',
            },
            ExpressionAttributeValues={
                ':stage_id': stage_id,
                ':stage_index': stage_index,
                ':step_results': self._convert_floats_to_decimal(step_results),
                ':zero': 0,
                ':first_step': steps[0]['id'] if steps else None,
                ':running': 'in_progress',
                ':updated_at': datetime.utcnow().isoformat() + 'Z',
            },
        )

    def _complete_journey_stage(
        self, journey_id: str, job_id: str, stage_id: str, stage_index: int, total_stages: int
    ):
        """Mark a stage complete inside a journey job and update overall progress."""
        job_data = self.get_job_execution(journey_id, job_id)
        if not job_data:
            return
        sk = self._job_sk(job_data, job_id)
        overall = ((stage_index + 1) / total_stages) * 100
        self.table.update_item(
            Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
            UpdateExpression=(
                'SET #data.stageResults.#stage_id.#status = :completed, '
                '#data.progress = :progress, #data.jobMetrics.overallProgress = :progress, '
                '#data.updatedAt = :updated_at'
            ),
            ExpressionAttributeNames={
                '#data': 'Data',
                '#stage_id': stage_id,
                '#status': 'status',
            },
            ExpressionAttributeValues={
                ':completed': 'completed',
                ':progress': Decimal(str(overall)),
                ':updated_at': datetime.utcnow().isoformat() + 'Z',
            },
        )
        self.update_journey_stage_summary(journey_id, stage_id, 'completed')

    def get_available_stages(self) -> List[str]:
        """Get list of available stage implementations"""
        return list_available_stages()

    def get_stage_info(self, stage_id: str) -> Dict:
        """Get information about a stage implementation"""
        stage_class = get_stage_class(stage_id)
        if not stage_class:
            return None
        
        # Create a temporary instance to get stage info (disable logging for temp instance)
        # Check if the stage class supports the enable_logging parameter
        import inspect
        sig = inspect.signature(stage_class.__init__)
        if 'enable_logging' in sig.parameters:
            temp_stage = stage_class('temp', stage_id, 'temp', self.region_name, self.role_arn, enable_logging=False)
        else:
            temp_stage = stage_class('temp', stage_id, 'temp', self.region_name, self.role_arn)
        
        # Determine stage order based on common pipeline sequence
        stage_order_map = {
            'raw_analysis': 0,
            'stripped_schema': 1, 
            'data_mapping': 2,
            'compliance_validation': 3,
            'business_rules': 4,
            'integration_testing': 5
        }
        
        return {
            'stage_id': stage_id,
            'stage_name': temp_stage.stage_name,
            'stage_description': temp_stage.stage_description,
            'steps': temp_stage.steps,
            'order': stage_order_map.get(stage_id, 99),  # Default to 99 for unknown stages
            'class_name': stage_class.__name__
        }

    def get_journey(self, journey_id: str) -> Dict:
        """Get journey metadata"""
        try:
            self.logger.info(f'🔍 Getting journey: {journey_id}')
            
            pk_value = self._get_journey_pk(journey_id)
            self.logger.info(f'📋 Using PK: {pk_value}')
            
            response = self.table.get_item(Key={'PK': pk_value, 'SK': 'METADATA'})
            
            self.logger.info(f'📋 DynamoDB response keys: {list(response.keys())}')
            
            if 'Item' not in response:
                self.logger.error(f'❌ Journey {journey_id} not found in DynamoDB (PK: {pk_value})')
                return None
            
            item = response['Item']
            self.logger.info(f'📝 Item keys: {list(item.keys())}')
            
            # Check if Data field exists
            if 'Data' not in item:
                self.logger.warning(f'⚠️ Journey {journey_id} found but has no Data field')
                # For compatibility with journey management system, return the item itself if no Data field
                return item
            
            journey_data = item['Data']
            self.logger.info(f'✅ Successfully retrieved journey {journey_id} with data keys: {list(journey_data.keys()) if isinstance(journey_data, dict) else "not a dict"}')
            
            return journey_data
            
        except Exception as e:
            self.logger.error(f'❌ Error getting journey {journey_id}: {str(e)}')
            import traceback
            self.logger.error(f'Traceback: {traceback.format_exc()}')
            return None

    def get_stage_definition(self, journey_id: str, stage_id: str) -> Dict:
        """Get stage definition from DynamoDB"""
        try:
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
                ExpressionAttributeValues={
                    ':pk': self._get_journey_pk(journey_id),
                    ':sk_prefix': f'STAGE#',
                    ':stage_id': stage_id,
                },
                FilterExpression='#data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
            )

            if response['Items']:
                return response['Items'][0]['Data']
            return None

        except Exception as e:
            self.logger.error(f'Error getting stage definition: {str(e)}')
            return None

    def get_next_execution_number(self, journey_id: str, stage_id: str) -> int:
        """Get the next execution number for a stage"""
        try:
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
                ExpressionAttributeValues={
                    ':pk': self._get_journey_pk(journey_id),
                    ':sk_prefix': 'JOB#',
                    ':stage_id': stage_id,
                },
                FilterExpression='#data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ScanIndexForward=False,
            )

            max_num = 0
            for item in response.get('Items', []):
                data = item.get('Data', {})
                if data.get('stageId') != stage_id:
                    continue
                max_num = max(max_num, int(data.get('executionNumber', 0)))
            return max_num + 1 if max_num else 1

        except Exception as e:
            self.logger.error(f'Error getting next execution number: {str(e)}')
            return 1

    def get_job_execution(self, journey_id: str, job_id: str) -> Dict:
        """Get job execution data (paginated to handle >1MB result sets)"""
        try:
            query_params = {
                'KeyConditionExpression': 'PK = :pk AND begins_with(SK, :sk_prefix)',
                'ExpressionAttributeValues': {
                    ':pk': self._get_journey_pk(journey_id),
                    ':sk_prefix': 'JOB#',
                    ':job_id': job_id,
                },
                'FilterExpression': '#data.jobId = :job_id',
                'ExpressionAttributeNames': {'#data': 'Data'},
                'ScanIndexForward': False,
            }

            while True:
                response = self.table.query(**query_params)
                if response.get('Items'):
                    return response['Items'][0]['Data']
                if 'LastEvaluatedKey' not in response:
                    break
                query_params['ExclusiveStartKey'] = response['LastEvaluatedKey']

            return None

        except Exception as e:
            self.logger.error(f'Error getting job execution: {str(e)}')
            return None

    def update_journey_current_job(
        self, journey_id: str, stage_id: str, job_id: str, execution_number: int
    ):
        """Update journey with current job info"""
        try:
            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': 'METADATA'},
                UpdateExpression='SET #data.currentJobs.#stage_id = :job_info, #data.updatedAt = :updated_at',
                ExpressionAttributeNames={
                    '#data': 'Data',
                    '#stage_id': stage_id,
                },
                ExpressionAttributeValues={
                    ':job_info': {
                        'jobId': job_id,
                        'executionNumber': execution_number,
                        'status': 'in_progress',
                        'startTime': datetime.utcnow().isoformat() + 'Z',
                    },
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )
        except Exception as e:
            self.logger.error(f'Error updating journey current job: {str(e)}')

    def update_step_status(
        self, journey_id: str, job_id: str, step_id: str, status: str, step_index: int,
        stage_id: Optional[str] = None,
    ):
        """Update step status in job record and emit SSE event"""
        try:
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            active_stage_id = stage_id or job_data.get('currentStageId') or job_data['stageId']
            sk = self._job_sk(job_data, job_id)

            update_expr = (
                'SET #data.stepResults.#step_id.#status = :status, '
                '#data.currentStepIndex = :step_index, #data.currentStepId = :step_id, '
                '#data.updatedAt = :updated_at'
            )
            expr_names = {
                '#data': 'Data',
                '#step_id': step_id,
                '#status': 'status',
            }
            if job_data.get('jobType') == 'journey':
                update_expr += (
                    ', #data.stageResults.#stage_id.stepResults.#step_id.#status = :status'
                )
                expr_names['#stage_id'] = active_stage_id

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues={
                    ':status': status,
                    ':step_index': step_index,
                    ':step_id': step_id,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )

            emit_step_status(
                job_id=job_id,
                step_id=step_id,
                status=status,
                step_index=step_index,
                progress=0 if status == 'in_progress' else 100 if status == 'completed' else 0,
                message=f"Step {step_id} {status}",
                stage_id=active_stage_id,
            )
            
        except Exception as e:
            self.logger.error(f'Error updating step status: {str(e)}')

    def update_step_results(
        self, journey_id: str, job_id: str, step_id: str, step_result: Dict,
        stage_id: Optional[str] = None,
    ):
        """Update step results in job record"""
        try:
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            active_stage_id = stage_id or job_data.get('currentStageId') or job_data['stageId']
            sk = self._job_sk(job_data, job_id)
            step_result_converted = self._convert_floats_to_decimal(step_result)

            update_expr = 'SET #data.stepResults.#step_id = :step_result, #data.updatedAt = :updated_at'
            expr_names = {'#data': 'Data', '#step_id': step_id}
            if job_data.get('jobType') == 'journey':
                update_expr += ', #data.stageResults.#stage_id.stepResults.#step_id = :step_result'
                expr_names['#stage_id'] = active_stage_id

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues={
                    ':step_result': step_result_converted,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )
        except Exception as e:
            self.logger.error(f'Error updating step results: {str(e)}')

    def _convert_floats_to_decimal(self, obj):
        """Recursively convert float values to Decimal for DynamoDB compatibility"""
        if isinstance(obj, dict):
            return {key: self._convert_floats_to_decimal(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        else:
            return obj

    def update_job_progress(
        self,
        journey_id: str,
        job_id: str,
        step_index: int,
        stage_id: Optional[str] = None,
        stage_step_count: Optional[int] = None,
    ):
        """Update job progress"""
        try:
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            sk = self._job_sk(job_data, job_id)
            if job_data.get('jobType') == 'journey' and stage_step_count:
                total_stages = len(job_data.get('stageIds') or [])
                current_stage_index = int(job_data.get('currentStageIndex', 0))
                stage_progress = (step_index + 1) / stage_step_count
                progress = ((current_stage_index + stage_progress) / max(total_stages, 1)) * 100
            elif stage_step_count:
                progress = ((step_index + 1) / stage_step_count) * 100
            else:
                progress = float(job_data.get('progress', 0))

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression='SET #data.progress = :progress, #data.jobMetrics.overallProgress = :progress, #data.currentStepIndex = :step_index, #data.updatedAt = :updated_at',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':progress': Decimal(str(progress)),
                    ':step_index': step_index,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )
        except Exception as e:
            self.logger.error(f'Error updating job progress: {str(e)}')

    def complete_job(self, journey_id: str, job_id: str, items_processed: int = 0, items_total: int = 0, detailed_metrics: dict = None):
        """Mark job as completed with optional metrics"""
        try:
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            sk = self._job_sk(job_data, job_id)
            stage_id = job_data.get('currentStageId') or job_data['stageId']

            from datetime import timezone
            start_time = datetime.fromisoformat(job_data['startTime'].replace('Z', '+00:00'))
            end_time = datetime.utcnow().replace(tzinfo=timezone.utc)
            duration_seconds = (end_time - start_time).total_seconds()
            duration_str = f'{int(duration_seconds // 60)}m {int(duration_seconds % 60)}s'

            metrics_obj = {
                'itemsProcessed': items_processed,
                'itemsTotal': items_total,
                'totalErrors': 0,
                'totalWarnings': 0,
                'overallProgress': Decimal('100'),
                'durationSeconds': Decimal(str(round(duration_seconds, 1))),
            }
            if detailed_metrics:
                for k, v in detailed_metrics.items():
                    metrics_obj[k] = v

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression='SET #data.#status = :status, #data.endTime = :end_time, #data.#duration = :duration, #data.progress = :progress, #data.updatedAt = :updated_at, #data.#metrics = :metrics',
                ExpressionAttributeNames={
                    '#data': 'Data',
                    '#status': 'status',
                    '#duration': 'duration',
                    '#metrics': 'metrics',
                },
                ExpressionAttributeValues={
                    ':status': 'completed',
                    ':end_time': end_time.isoformat() + 'Z',
                    ':duration': duration_str,
                    ':progress': Decimal('100'),
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                    ':metrics': metrics_obj,
                },
            )

            if job_data.get('jobType') == 'journey':
                self.update_journey_aggregates(journey_id, stage_id, 'completed')
            else:
                self.update_journey_aggregates(journey_id, stage_id, 'completed')
            
            emit_job_complete(
                job_id=job_id,
                status='completed',
                duration_seconds=duration_seconds,
                items_processed=items_processed,
                items_total=items_total
            )

        except Exception as e:
            self.logger.error(f'Error completing job: {str(e)}')

    def fail_job(self, journey_id: str, job_id: str, error_message: str):
        """Mark job as failed"""
        try:
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            sk = self._job_sk(job_data, job_id)
            stage_id = job_data.get('currentStageId') or job_data['stageId']

            update_expr = (
                'SET #data.#status = :status, #data.endTime = :end_time, '
                '#data.errorMessage = :error_message, #data.updatedAt = :updated_at'
            )
            expr_names = {'#data': 'Data', '#status': 'status'}
            if job_data.get('jobType') == 'journey':
                update_expr += ', #data.stageResults.#stage_id.#status = :failed'
                expr_names['#stage_id'] = stage_id

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues={
                    ':status': 'failed',
                    ':failed': 'failed',
                    ':end_time': datetime.utcnow().isoformat() + 'Z',
                    ':error_message': error_message,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )

            self.update_journey_aggregates(journey_id, stage_id, 'failed')
            
            emit_job_complete(
                job_id=job_id,
                status='failed',
                duration_seconds=0,
                items_processed=0,
                items_total=0
            )

            self._write_to_dlq(
                job_id=job_id,
                journey_id=journey_id,
                stage_id=stage_id,
                error=error_message,
            )

        except Exception as e:
            self.logger.error(f'Error failing job: {str(e)}')

    def update_journey_stage_summary(self, journey_id: str, stage_id: str, status: str):
        """Update per-stage last status without incrementing job counters (mid-journey)."""
        try:
            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': 'METADATA'},
                UpdateExpression=(
                    'SET #data.stageSummary = if_not_exists(#data.stageSummary, :empty_map), '
                    '#data.stageSummary.#stage_id = if_not_exists(#data.stageSummary.#stage_id, :empty_stage), '
                    '#data.stageSummary.#stage_id.lastStatus = :status, #data.updatedAt = :updated_at'
                ),
                ExpressionAttributeNames={'#data': 'Data', '#stage_id': stage_id},
                ExpressionAttributeValues={
                    ':empty_map': {},
                    ':empty_stage': {'totalExecutions': 0, 'lastStatus': 'pending'},
                    ':status': status,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )
        except Exception as e:
            self.logger.error(f'Error updating stage summary: {str(e)}')

    def update_journey_aggregates(self, journey_id: str, stage_id: str, status: str):
        """Update journey aggregate statistics"""
        try:
            # First, ensure the aggregates and stageSummary structures exist
            # by initializing them if they don't
            try:
                self.table.update_item(
                    Key={'PK': self._get_journey_pk(journey_id), 'SK': 'METADATA'},
                    UpdateExpression='SET #data.aggregates = if_not_exists(#data.aggregates, :empty_agg), #data.stageSummary = if_not_exists(#data.stageSummary, :empty_map)',
                    ExpressionAttributeNames={
                        '#data': 'Data',
                    },
                    ExpressionAttributeValues={
                        ':empty_agg': {'totalJobs': 0, 'completedJobs': 0, 'failedJobs': 0},
                        ':empty_map': {},
                    },
                )
            except Exception:
                pass  # Ignore initialization errors, paths may already exist
            
            # Now ensure the stage-specific summary exists
            try:
                self.table.update_item(
                    Key={'PK': self._get_journey_pk(journey_id), 'SK': 'METADATA'},
                    UpdateExpression='SET #data.stageSummary.#stage_id = if_not_exists(#data.stageSummary.#stage_id, :empty_stage)',
                    ExpressionAttributeNames={
                        '#data': 'Data',
                        '#stage_id': stage_id,
                    },
                    ExpressionAttributeValues={
                        ':empty_stage': {'totalExecutions': 0, 'lastStatus': 'pending'},
                    },
                )
            except Exception:
                pass  # Ignore initialization errors
            
            # Now update the aggregates
            updated_at = datetime.utcnow().isoformat() + 'Z'
            
            if status == 'completed':
                self.table.update_item(
                    Key={'PK': self._get_journey_pk(journey_id), 'SK': 'METADATA'},
                    UpdateExpression='SET #data.aggregates.completedJobs = #data.aggregates.completedJobs + :inc, #data.aggregates.totalJobs = #data.aggregates.totalJobs + :inc, #data.stageSummary.#stage_id.totalExecutions = #data.stageSummary.#stage_id.totalExecutions + :inc, #data.stageSummary.#stage_id.lastStatus = :status, #data.updatedAt = :updated_at',
                    ExpressionAttributeNames={
                        '#data': 'Data',
                        '#stage_id': stage_id,
                    },
                    ExpressionAttributeValues={
                        ':inc': 1,
                        ':status': status,
                        ':updated_at': updated_at,
                    },
                )
            elif status == 'failed':
                self.table.update_item(
                    Key={'PK': self._get_journey_pk(journey_id), 'SK': 'METADATA'},
                    UpdateExpression='SET #data.aggregates.failedJobs = #data.aggregates.failedJobs + :inc, #data.aggregates.totalJobs = #data.aggregates.totalJobs + :inc, #data.stageSummary.#stage_id.totalExecutions = #data.stageSummary.#stage_id.totalExecutions + :inc, #data.stageSummary.#stage_id.lastStatus = :status, #data.updatedAt = :updated_at',
                    ExpressionAttributeNames={
                        '#data': 'Data',
                        '#stage_id': stage_id,
                    },
                    ExpressionAttributeValues={
                        ':inc': 1,
                        ':status': status,
                        ':updated_at': updated_at,
                    },
                )
            
            self.logger.info(f'✅ Updated journey aggregates for {journey_id}, stage {stage_id}, status {status}')
        except Exception as e:
            self.logger.error(f'Error updating journey aggregates: {str(e)}')
