"""
Base Stage Class for TMF ODA Transformation Stages

This module defines the abstract base class that all transformation stages must implement.
It provides the common interface and utilities for stage execution.
"""

import json
import boto3
import os
import sys
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal

from ..adapters.aws import AWSClientManager
from ..config import get_config


class BaseStage(ABC):
    """
    Abstract base class for all transformation stages.
    
    Each stage must implement the execute_step method and define its steps.
    """
    
    def __init__(self, journey_id: str, stage_id: str, job_id: str, region_name: str = None, role_arn: Optional[str] = None):
        """
        Initialize the stage.
        
        Args:
            journey_id: The journey ID this stage belongs to
            stage_id: The stage ID (e.g., 'raw_analysis')
            job_id: The job execution ID
            region_name: AWS region name (optional)
            role_arn: AWS role ARN to assume (optional)
        """
        self.journey_id = journey_id
        self.stage_id = stage_id
        self.job_id = job_id
        self.role_arn = role_arn or os.environ.get('AWS_ROLE_ARN')
        
        # Create AWS client manager
        self.client_manager = AWSClientManager(role_arn=self.role_arn, region_name=region_name)
        
        # Get configuration
        self._config = get_config()
        
        # Create AWS clients using the client manager
        self.dynamodb = self.client_manager.create_resource('dynamodb')
        self.s3 = self.client_manager.create_client('s3')
        self.table = self.dynamodb.Table(self._config.dynamodb_transformation_table)
        
        # Get region from client manager
        self.region_name = self.client_manager.region_name
        
        # Stage execution state
        self.logs = []
        self.metrics = {}
        self.artifacts = {}
        
        # Set up logger to use stderr to avoid interfering with JSON-RPC protocol
        self.logger = logging.getLogger(f'stage.{self.stage_id}')
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        # Enhanced local file logger (common for all stages)
        self._local_logger = None
        self._local_log_file = None
        self._sse_emit_log = None
        try:
            from ..events.sse_manager import emit_log
            self._sse_emit_log = emit_log
        except (ImportError, Exception):
            pass

    def setup_enhanced_logging(self):
        """
        Setup enhanced logging with local file + SSE broadcasting.
        Call this in __init__ of any stage that wants file-based logging.
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_dir
            while not os.path.exists(os.path.join(project_root, 'scripts')):
                parent = os.path.dirname(project_root)
                if parent == project_root:
                    project_root = os.path.join(current_dir, '..', '..', '..')
                    break
                project_root = parent

            logs_dir = os.path.join(project_root, 'logs')
            os.makedirs(logs_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = f'{self.stage_id}_{self.job_id}_{timestamp}.log'
            self._local_log_file = os.path.join(logs_dir, log_filename)

            self._local_logger = logging.getLogger(f'{self.stage_id}_{self.job_id}')
            self._local_logger.setLevel(logging.INFO)
            for h in self._local_logger.handlers[:]:
                self._local_logger.removeHandler(h)

            file_handler = logging.FileHandler(self._local_log_file)
            console_handler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            self._local_logger.addHandler(file_handler)
            self._local_logger.addHandler(console_handler)

            self._local_logger.info("=" * 80)
            self._local_logger.info(f"STAGE STARTED: {self.stage_id}")
            self._local_logger.info(f"Journey: {self.journey_id} | Job: {self.job_id}")
            self._local_logger.info("=" * 80)
        except Exception as e:
            sys.stderr.write(f"Enhanced logging setup failed: {e}\n")

    def stage_log(self, level: str, message: str, step_id: str = None):
        """
        Common logging method for all stages.
        Writes to: local file + DynamoDB LIVELOG + SSE broadcast.
        Use this instead of log_info/log_error directly.
        """
        step_prefix = f"[{step_id}] " if step_id else ""
        formatted = f"{step_prefix}{message}"

        # 1. Local file logger
        if self._local_logger:
            if level.upper() == 'ERROR':
                self._local_logger.error(formatted)
            elif level.upper() == 'WARNING':
                self._local_logger.warning(formatted)
            else:
                self._local_logger.info(formatted)

        # 2. Base class DynamoDB LIVELOG write
        if level.upper() == 'ERROR':
            self.log_error(message, step_id)
        elif level.upper() == 'WARNING':
            self.log_warning(message, step_id)
        else:
            self.log_info(message, step_id)

        # 3. SSE broadcast for real-time UI updates
        if self._sse_emit_log and self.job_id:
            try:
                self._sse_emit_log(
                    job_id=self.job_id,
                    step_id=step_id or 'general',
                    level=level.lower(),
                    message=message
                )
            except Exception:
                pass

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Return the human-readable stage name"""
        pass
    
    @property
    @abstractmethod
    def stage_description(self) -> str:
        """Return the stage description"""
        pass
    
    @property
    @abstractmethod
    def steps(self) -> List[Dict[str, Any]]:
        """Return the list of steps for this stage"""
        pass
    
    @abstractmethod
    def execute_step(self, step_id: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific step of this stage.
        
        Args:
            step_id: The step ID to execute
            step_data: Step configuration data
            
        Returns:
            Dict containing step results, logs, and metrics
        """
        pass
    
    def log_info(self, message: str, step_id: str = None):
        """Log an info message"""
        self._log('INFO', message, step_id)
    
    def log_warning(self, message: str, step_id: str = None):
        """Log a warning message"""
        self._log('WARNING', message, step_id)
    
    def log_error(self, message: str, step_id: str = None):
        """Log an error message"""
        self._log('ERROR', message, step_id)
    
    def _log(self, level: str, message: str, step_id: str = None):
        """Internal logging method"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'message': message,
            'step_id': step_id,
            'stage_id': self.stage_id,
            'job_id': self.job_id
        }
        self.logs.append(log_entry)
        
        if step_id:
            self._write_live_logs_to_dynamo(step_id)
        
        # Log to stderr using logger to avoid interfering with JSON-RPC protocol
        emoji = {'INFO': 'ℹ️', 'WARNING': '⚠️', 'ERROR': '❌'}.get(level, '📝')
        step_prefix = f"[{step_id}] " if step_id else ""
        formatted_message = f'{emoji} {step_prefix}{message}'
        
        # Use appropriate log level
        if level == 'ERROR':
            self.logger.error(formatted_message)
        elif level == 'WARNING':
            self.logger.warning(formatted_message)
        else:
            self.logger.info(formatted_message)
    
    def _write_live_logs_to_dynamo(self, step_id: str):
        """Write current step logs to DynamoDB for immediate real-time polling."""
        try:
            step_logs = [log for log in self.logs if log.get('step_id') == step_id]
            self.table.put_item(Item={
                'PK': f'LIVELOG#{self.job_id}',
                'SK': step_id,
                'logs_json': json.dumps(step_logs, default=str),
                'log_count': len(step_logs),
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'ttl': int(datetime.utcnow().timestamp()) + 3600,
            })
        except Exception as e:
            self.logger.warning(f'DynamoDB live log write failed for {step_id}: {e}')

    def _delete_live_logs_from_dynamo(self, step_id: str):
        """Remove live log entry from DynamoDB after final S3 upload."""
        try:
            self.table.delete_item(Key={
                'PK': f'LIVELOG#{self.job_id}',
                'SK': step_id,
            })
        except Exception as e:
            self.logger.warning(f'DynamoDB live log delete failed for {step_id}: {e}')

    _last_db_cancel_check: Dict[str, float] = {}
    _DB_CANCEL_CHECK_INTERVAL = 5

    def is_cancelled(self) -> bool:
        from ..execution.transformation_job_executor import TransformationJobExecutor
        if TransformationJobExecutor.is_job_cancelled(self.job_id):
            return True

        now = time.time()
        last_check = self._last_db_cancel_check.get(self.job_id, 0)
        if now - last_check < self._DB_CANCEL_CHECK_INTERVAL:
            return False

        self._last_db_cancel_check[self.job_id] = now
        try:
            resp = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{self.journey_id}',
                    ':sk_prefix': 'JOB#',
                    ':job_id': self.job_id,
                },
                FilterExpression='#data.jobId = :job_id',
                ExpressionAttributeNames={'#data': 'Data'},
            )
            if resp.get('Items'):
                status = resp['Items'][0].get('Data', {}).get('status', '')
                if status == 'cancelled':
                    TransformationJobExecutor.cancel_job_execution(self.job_id)
                    self.logger.info(f'Cancellation detected from DynamoDB for job {self.job_id}')
                    return True
        except Exception:
            pass
        return False

    def set_metric(self, key: str, value: Any, step_id: str = None):
        """Set a metric value"""
        if step_id:
            if step_id not in self.metrics:
                self.metrics[step_id] = {}
            self.metrics[step_id][key] = value
        else:
            self.metrics[key] = value
    
    def add_artifact(self, name: str, data: Any, step_id: str = None):
        """Add an artifact (result data)"""
        if step_id:
            if step_id not in self.artifacts:
                self.artifacts[step_id] = {}
            self.artifacts[step_id][name] = data
        else:
            self.artifacts[name] = data
    
    def flush_logs_to_s3(self, step_id: str):
        """Flush current step logs to S3 for incremental updates during execution."""
        try:
            logs_key = f'journeys/{self.journey_id}/stages/{self.stage_id}/executions/{self.job_id}/logs/{step_id}.json'
            step_logs = [log for log in self.logs if log.get('step_id') == step_id]
            self.s3.put_object(
                Bucket=self._config.s3_journey_logs_bucket,
                Key=logs_key,
                Body=json.dumps(step_logs, indent=2, default=str),
                ContentType='application/json'
            )
        except Exception as e:
            self.logger.warning(f'flush_logs_to_s3 failed for {step_id}: {e}')

    def upload_logs_to_s3(self, step_id: str):
        """Upload step logs to S3"""
        try:
            logs_key = f'journeys/{self.journey_id}/stages/{self.stage_id}/executions/{self.job_id}/logs/{step_id}.json'
            
            # Filter logs for this step
            step_logs = [log for log in self.logs if log.get('step_id') == step_id]
            
            self.s3.put_object(
                Bucket=self._config.s3_journey_logs_bucket,
                Key=logs_key,
                Body=json.dumps(step_logs, indent=2, default=str),
                ContentType='application/json'
            )
            
            self._delete_live_logs_from_dynamo(step_id)
            
            self.log_info(f'Uploaded logs to S3: {logs_key}', step_id)
            
        except Exception as e:
            self.log_error(f'Failed to upload logs to S3: {str(e)}', step_id)
    
    def upload_report_to_s3(self, step_id: str, report_data: Dict[str, Any]):
        """Upload step report to S3"""
        try:
            report_key = f'journeys/{self.journey_id}/stages/{self.stage_id}/executions/{self.job_id}/reports/{step_id}.json'
            
            # Convert Decimal values to float for JSON serialization
            report_json = json.dumps(report_data, indent=2, default=self._decimal_default)
            
            self.s3.put_object(
                Bucket=self._config.s3_journey_reports_bucket,
                Key=report_key,
                Body=report_json,
                ContentType='application/json'
            )
            
            self.log_info(f'Uploaded report to S3: {report_key}', step_id)
            
        except Exception as e:
            self.log_error(f'Failed to upload report to S3: {str(e)}', step_id)
    
    def _decimal_default(self, obj):
        """JSON serializer for Decimal objects"""
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def simulate_processing(self, step_id: str, duration_seconds: int = 2):
        """Simulate processing time (for demo purposes)"""
        import time
        self.log_info(f'Processing step: {step_id}', step_id)
        time.sleep(duration_seconds)
        self.log_info(f'Completed step: {step_id}', step_id) 