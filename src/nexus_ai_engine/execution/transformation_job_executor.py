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
from typing import Dict, List, Optional

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

    def _get_journey_pk(self, journey_id: str) -> str:
        """Helper method to get the correct DynamoDB PK for a journey.
        Uses the same format as journey service: JOURNEY#{journey_id}"""
        return f'JOURNEY#{journey_id}'

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
        """Execute all steps in a job using stage-based architecture"""
        try:
            # Get job data
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                self.logger.error(f'❌ Job {job_id} not found for journey {journey_id}')
                raise ValueError(f'Job {job_id} not found')

            stage_id = job_data['stageId']
            
            # Quick validation - check if stage is available
            if stage_id not in list_available_stages():
                self.logger.error(f'❌ Stage {stage_id} not available for execution')
                self.update_job_status(journey_id, job_id, 'failed', 
                                     error_message=f'Stage {stage_id} not available')
                raise ValueError(f'Stage {stage_id} not available for execution')
            
            # Get stage class
            stage_class = get_stage_class(stage_id)
            if not stage_class:
                self.logger.error(f'❌ Stage class not found for stage: {stage_id}')
                self.update_job_status(journey_id, job_id, 'failed',
                                     error_message=f'Stage class not found for stage: {stage_id}')
                raise ValueError(f'Stage class not found for stage: {stage_id}')

            # Create stage instance with role ARN support
            stage = stage_class(journey_id, stage_id, job_id, self.region_name, self.role_arn)
            steps = stage.steps

            self.logger.info(f'🚀 Executing job {job_id} with {len(steps)} steps using {stage_class.__name__}')
            
            # DEBUG: Log what steps we're about to execute
            self.logger.info('📋 Steps to execute:')
            for i, step in enumerate(steps):
                self.logger.info(f'  {i+1}. {step["id"]} - {step["name"]}')
            self.logger.info(f'🔢 Total steps in execution list: {len(steps)}')

            # Execute each step using the stage implementation
            for step_index, step in enumerate(steps):
                step_id = step['id']

                if self.is_job_cancelled(job_id):
                    self.logger.info(f'🛑 Job {job_id} cancelled before step {step_id}')
                    raise JobCancelledException(f'Job {job_id} cancelled')

                self.logger.info(f'📝 Starting step {step_index + 1}/{len(steps)}: {step["name"]} (ID: {step_id})')

                try:
                    self.update_step_status(journey_id, job_id, step_id, 'in_progress', step_index)

                    step_result = stage.execute_step(step_id, step)
                    self.logger.info(f'✅ Step execution completed for {step_id}, result status: {step_result.get("status", "unknown")}')

                    if self.is_job_cancelled(job_id):
                        self.logger.info(f'🛑 Job {job_id} cancelled after step {step_id}')
                        raise JobCancelledException(f'Job {job_id} cancelled')

                    self.update_step_results(journey_id, job_id, step_id, step_result)

                    progress = ((step_index + 1) / len(steps)) * 100
                    self.update_job_progress(journey_id, job_id, progress, step_index + 1)

                    self.logger.info(f'✅ Completed step: {step["name"]} (ID: {step_id})')
                    
                except JobCancelledException:
                    raise
                except Exception as step_error:
                    self.logger.error(f'❌ Error in step {step_id}: {str(step_error)}')
                    self.logger.error(f'Error type: {type(step_error).__name__}')
                    import traceback
                    traceback.print_exc()
                    raise step_error

            # Collect metrics from stage
            items_processed = 0
            items_total = 0
            detailed_metrics = {}

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

            self.complete_job(journey_id, job_id, items_processed, items_total, detailed_metrics)
            self.logger.info(f'🎉 Job {job_id} completed successfully (processed: {items_processed}/{items_total})')
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
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :gsi1pk',
                ExpressionAttributeValues={':gsi1pk': f'STAGE#{journey_id}#{stage_id}'},
                ScanIndexForward=False,
                Limit=1,
            )

            if response['Items']:
                last_execution = response['Items'][0]['Data']['executionNumber']
                return int(last_execution) + 1
            return 1

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
        self, journey_id: str, job_id: str, step_id: str, status: str, step_index: int
    ):
        """Update step status in job record and emit SSE event"""
        try:
            # First, get the job to find the correct SK
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            # Build the SK from job data
            stage_id = job_data['stageId']
            execution_number = job_data['executionNumber']
            timestamp = job_id.split('-')[-1]  # Extract timestamp from job_id
            sk = f'JOB#{int(job_data["stageOrder"]):02d}#{stage_id}#{int(execution_number):03d}#{timestamp}'

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression='SET #data.stepResults.#step_id.#status = :status, #data.currentStepIndex = :step_index, #data.currentStepId = :step_id, #data.updatedAt = :updated_at',
                ExpressionAttributeNames={
                    '#data': 'Data',
                    '#step_id': step_id,
                    '#status': 'status',
                },
                ExpressionAttributeValues={
                    ':status': status,
                    ':step_index': step_index,
                    ':step_id': step_id,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )
            
            # Emit SSE event for real-time UI updates
            emit_step_status(
                job_id=job_id,
                step_id=step_id,
                status=status,
                step_index=step_index,
                progress=0 if status == 'in_progress' else 100 if status == 'completed' else 0,
                message=f"Step {step_id} {status}"
            )
            self.logger.debug(f'📡 SSE event emitted: step_status for {step_id} -> {status}')
            
        except Exception as e:
            self.logger.error(f'Error updating step status: {str(e)}')

    def update_step_results(self, journey_id: str, job_id: str, step_id: str, step_result: Dict):
        """Update step results in job record"""
        try:
            # Get job data to find correct SK
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            # Build the SK
            stage_id = job_data['stageId']
            execution_number = job_data['executionNumber']
            timestamp = job_id.split('-')[-1]
            sk = f'JOB#{int(job_data["stageOrder"]):02d}#{stage_id}#{int(execution_number):03d}#{timestamp}'

            # Convert float values to Decimal for DynamoDB compatibility
            step_result_converted = self._convert_floats_to_decimal(step_result)

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression='SET #data.stepResults.#step_id = :step_result, #data.updatedAt = :updated_at',
                ExpressionAttributeNames={
                    '#data': 'Data',
                    '#step_id': step_id,
                },
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
        self, journey_id: str, job_id: str, progress: float, current_step_index: int
    ):
        """Update job progress"""
        try:
            # Get job data to find correct SK
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            # Build the SK
            stage_id = job_data['stageId']
            execution_number = job_data['executionNumber']
            timestamp = job_id.split('-')[-1]
            sk = f'JOB#{int(job_data["stageOrder"]):02d}#{stage_id}#{int(execution_number):03d}#{timestamp}'

            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression='SET #data.progress = :progress, #data.jobMetrics.overallProgress = :progress, #data.currentStepIndex = :step_index, #data.updatedAt = :updated_at',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':progress': Decimal(str(progress)),
                    ':step_index': current_step_index,
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

            stage_id = job_data['stageId']
            execution_number = job_data['executionNumber']
            timestamp = job_id.split('-')[-1]
            sk = f'JOB#{int(job_data["stageOrder"]):02d}#{stage_id}#{int(execution_number):03d}#{timestamp}'

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

            # Update journey aggregates
            self.update_journey_aggregates(journey_id, stage_id, 'completed')
            
            # Emit SSE event for job completion
            emit_job_complete(
                job_id=job_id,
                status='completed',
                duration_seconds=duration_seconds,
                items_processed=items_processed,
                items_total=items_total
            )
            self.logger.info(f'📡 SSE event emitted: job_complete for {job_id}')

        except Exception as e:
            self.logger.error(f'Error completing job: {str(e)}')

    def fail_job(self, journey_id: str, job_id: str, error_message: str):
        """Mark job as failed"""
        try:
            # Get job data
            job_data = self.get_job_execution(journey_id, job_id)
            if not job_data:
                raise Exception(f'Job {job_id} not found')

            # Build the SK
            stage_id = job_data['stageId']
            execution_number = job_data['executionNumber']
            timestamp = job_id.split('-')[-1]
            sk = f'JOB#{int(job_data["stageOrder"]):02d}#{stage_id}#{int(execution_number):03d}#{timestamp}'

            # Update job record
            self.table.update_item(
                Key={'PK': self._get_journey_pk(journey_id), 'SK': sk},
                UpdateExpression='SET #data.#status = :status, #data.endTime = :end_time, #data.errorMessage = :error_message, #data.updatedAt = :updated_at',
                ExpressionAttributeNames={
                    '#data': 'Data',
                    '#status': 'status',
                },
                ExpressionAttributeValues={
                    ':status': 'failed',
                    ':end_time': datetime.utcnow().isoformat() + 'Z',
                    ':error_message': error_message,
                    ':updated_at': datetime.utcnow().isoformat() + 'Z',
                },
            )

            # Update journey aggregates
            self.update_journey_aggregates(journey_id, stage_id, 'failed')
            
            # Emit SSE event for job failure
            emit_job_complete(
                job_id=job_id,
                status='failed',
                duration_seconds=0,
                items_processed=0,
                items_total=0
            )
            self.logger.info(f'📡 SSE event emitted: job_complete (failed) for {job_id}')

        except Exception as e:
            self.logger.error(f'Error failing job: {str(e)}')

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
