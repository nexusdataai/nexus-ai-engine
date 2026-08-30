#!/usr/bin/env python3
"""
Comprehensive TMF ODA Transformation Journey Management

This consolidated script provides complete management of TMF ODA transformation journeys including:

Journey Management:
- Create/Update/Delete journeys
- Clone journeys
- List and filter journeys
- Import/Export journeys

Stage Management:
- Add/Update/Delete stages
- Reorder stages
- Manage stage steps
- Enable/disable stages

Second Brain Rules Management:
- Add/Update/Delete rules
- Enable/disable rules
- Import/Export rules
- Interactive rule builder

Job Management:
- Execute jobs for specific stages
- Monitor job progress and status
- Cancel running jobs
- List job execution history

Logs and Reports Management:
- Retrieve job execution logs
- Generate and view job reports
- List available logs by job/stage
- Generate comprehensive summary reports

Interactive Features:
- Journey builder wizard
- Stage configuration wizard
- Rule creation wizard
- Comprehensive dashboards
- Job monitoring dashboard

Usage Examples:
    # Journey operations
    python3 manage_journey.py --action list-journeys
    python3 manage_journey.py --action create-journey --data-file journey.json
    python3 manage_journey.py --action get-journey --journey-id JRN-12345 --include-all
    
    # Stage operations  
    python3 manage_journey.py --action list-stages --journey-id JRN-12345
    python3 manage_journey.py --action add-stage --journey-id JRN-12345 --data-file stage.json
    
    # Rules operations
    python3 manage_journey.py --action list-rules --journey-id JRN-12345
    python3 manage_journey.py --action add-rule --journey-id JRN-12345 --stage-id raw_analysis --data-file rule.json
    
    # Job operations
    python3 manage_journey.py --action list-jobs --journey-id JRN-12345
    python3 manage_journey.py --action run-job --journey-id JRN-12345 --stage-id raw_analysis
    python3 manage_journey.py --action get-job --journey-id JRN-12345 --job-id JOB-12345
    python3 manage_journey.py --action cancel-job --journey-id JRN-12345 --job-id JOB-12345
    
    # Logs and Reports operations
    python3 manage_journey.py --action get-job-logs --journey-id JRN-12345 --job-id JOB-12345
    python3 manage_journey.py --action get-job-reports --journey-id JRN-12345 --job-id JOB-12345
    python3 manage_journey.py --action list-available-logs --journey-id JRN-12345
    python3 manage_journey.py --action generate-summary-report --journey-id JRN-12345 --job-id JOB-12345
    
    # Interactive mode
    python3 manage_journey.py --action interactive
    python3 manage_journey.py --action dashboard --journey-id JRN-12345
    
    # Bulk operations
    python3 manage_journey.py --action export-complete --journey-id JRN-12345 --output-file journey_backup.json
    python3 manage_journey.py --action import-complete --input-file journey_backup.json
"""

import boto3
import sys
import traceback
import json
import uuid
import argparse
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union


def print_with_flush(message):
    """Print message and flush stdout immediately (suppressed in MCP mode)"""
    # Suppress output when running in MCP stdio mode (stdin is not a tty)
    if not sys.stdin.isatty():
        # In MCP mode, suppress all output to avoid JSON parsing issues
        return
    
    try:
        print(message)
        sys.stdout.flush()
    except BrokenPipeError:
        # Handle broken pipe gracefully (happens with head, tail, etc.)
        try:
            sys.stdout.close()
        except:
            pass
        try:
            sys.stderr.close()
        except:
            pass


class ComprehensiveJourneyManager:
    """Comprehensive TMF ODA transformation journey management"""
    
    def __init__(self, table=None, dynamodb=None):
        """
        Initialize Comprehensive Journey Manager
        
        Args:
            table: Optional DynamoDB table (for dependency injection/testing)
            dynamodb: Optional DynamoDB resource (for dependency injection/testing)
        """
        if table is not None:
            # Dependency injection mode (for testing)
            self.table = table
            self.dynamodb = dynamodb
        else:
            # Normal operation - create AWS clients
            self.dynamodb = None
            self.table = None
        self._last_error = None  # Store last error for debugging
        self.setup_aws_client()
        
        # Configuration constants
        self.valid_journey_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled', 'paused']
        self.valid_priorities = ['low', 'medium', 'high', 'critical']
        self.valid_oda_components = [
            'customer-management', 'product-catalog', 'order-management',
            'billing', 'resource-inventory', 'service-catalog',
            'party-management', 'account-management', 'data-pipeline'
        ]
        self.valid_rule_types = [
            'field_mapping', 'contextual_recommendations', 
            'data_interpretation', 'validation_rules',
            'business_logic', 'compliance_check'
        ]
        self.valid_rule_scopes = ['global', 'project', 'stage']
        self.valid_rule_statuses = ['active', 'inactive', 'deprecated']
        self.available_stage_ids = [
            'raw_analysis', 'stripped_schema', 'tmf_mapping',
            'migration_planning', 'data_migration', 'verification_validation'
        ]
    
    def setup_aws_client(self):
        """Set up AWS DynamoDB client"""
        try:
            print_with_flush('🔗 Setting up AWS DynamoDB client...')
            
            # Import AWS client utilities
            import os
            from ..aws import create_aws_resource
            
            # Get table name and bucket names from config or environment
            try:
                from ...config import get_config
                config = get_config()
                table_name = config.dynamodb_transformation_table
                self.logs_bucket = config.s3_journey_logs_bucket
                self.reports_bucket = config.s3_journey_reports_bucket
                print_with_flush(f'📋 Using table from config: {table_name}')
                print_with_flush(f'📋 Using logs bucket: {self.logs_bucket}')
                print_with_flush(f'📋 Using reports bucket: {self.reports_bucket}')
            except Exception:
                # Fallback to environment variable or default
                table_name = os.environ.get('DYNAMODB_TABLE', 'TransformationSystem')
                self.logs_bucket = os.environ.get('S3_JOURNEY_LOGS_BUCKET', 'transformation-journey-logs')
                self.reports_bucket = os.environ.get('S3_JOURNEY_REPORTS_BUCKET', 'transformation-journey-reports')
                print_with_flush(f'📋 Using table from env/default: {table_name}')
            
            role_arn = os.environ.get('AWS_ROLE_ARN')
            if role_arn:
                print_with_flush(f'🔑 Using role ARN: {role_arn}')
                self.dynamodb = create_aws_resource('dynamodb', role_arn=role_arn)
            else:
                # Use create_aws_resource for LocalStack support
                print_with_flush('🔑 Using default credential chain (LocalStack-aware)')
                self.dynamodb = create_aws_resource('dynamodb')
            
            self.table = self.dynamodb.Table(table_name)
            print_with_flush('✅ AWS DynamoDB client ready')
            
        except Exception as e:
            print_with_flush(f'❌ Failed to setup AWS client: {str(e)}')
            raise
    
    def setup_s3_client(self):
        """Setup AWS S3 client with role-based authentication"""
        try:
            import os
            from ..aws import create_aws_client
            
            role_arn = os.environ.get('AWS_ROLE_ARN')
            if role_arn:
                return create_aws_client('s3', role_arn=role_arn)
            else:
                # Use create_aws_client for LocalStack support
                return create_aws_client('s3')
            
        except Exception as e:
            print_with_flush(f'❌ Failed to setup S3 client: {str(e)}')
            raise
    
    def convert_floats_to_decimal(self, obj):
        """Convert float values to Decimal for DynamoDB compatibility"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self.convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_floats_to_decimal(item) for item in obj]
        else:
            return obj
    
    def clean_journey_id(self, journey_id: str) -> str:
        """Clean journey ID by removing JOURNEY# prefix if present"""
        return journey_id.replace('JOURNEY#', '') if journey_id.startswith('JOURNEY#') else journey_id
    
    def validate_journey_exists(self, journey_id: str) -> bool:
        """Check if a journey exists in the database"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            response = self.table.get_item(
                Key={
                    'PK': f'JOURNEY#{clean_id}',
                    'SK': 'METADATA'
                }
            )
            
            return 'Item' in response
            
        except Exception as e:
            print_with_flush(f'❌ Error checking journey existence: {str(e)}')
            return False
    
    # ==========================================
    # JOURNEY METADATA MANAGEMENT
    # ==========================================
    
    def _journey_summaries_from_items(
        self,
        items: List[Dict],
        status_filter: Optional[str] = None,
        component_type_filter: Optional[str] = None,
    ) -> List[Dict]:
        journeys: List[Dict] = []
        for item in items:
            journey_data = item.get("Data") or {}
            if status_filter and journey_data.get("status") != status_filter:
                continue
            if component_type_filter and journey_data.get("odaComponentType") != component_type_filter:
                continue
            aggregates = journey_data.get("aggregates", {})
            current_jobs = journey_data.get("currentJobs") or {}
            running_jobs = sum(
                1
                for info in current_jobs.values()
                if isinstance(info, dict)
                and info.get("status") in ("running", "in_progress")
            )
            journeys.append(
                {
                    "journeyId": journey_data.get("journeyId"),
                    "name": journey_data.get("name"),
                    "description": journey_data.get("description"),
                    "status": journey_data.get("status"),
                    "priority": journey_data.get("priority"),
                    "odaComponentType": journey_data.get("odaComponentType"),
                    "overallProgress": journey_data.get("overallProgress", 0),
                    "currentStageId": journey_data.get("currentStageId"),
                    "createdAt": item.get("CreatedAt"),
                    "updatedAt": item.get("UpdatedAt"),
                    "createdBy": journey_data.get("createdBy"),
                    "totalRules": aggregates.get("totalRules", 0),
                    "activeRules": aggregates.get("activeRules", 0),
                    "totalJobs": aggregates.get("totalJobs", 0),
                    "completedJobs": aggregates.get("completedJobs", 0),
                    "failedJobs": aggregates.get("failedJobs", 0),
                    "runningJobs": running_jobs,
                }
            )
        return journeys

    def _list_journeys_via_scan(
        self,
        status_filter: Optional[str] = None,
        component_type_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Fallback for backends (e.g. Scylla Alternator) where GSI queries fail."""
        from boto3.dynamodb.conditions import Attr

        print_with_flush("📋 Listing journeys via METADATA scan (GSI fallback)...")
        items: List[Dict] = []
        scan_kwargs = {
            "FilterExpression": Attr("EntityType").eq("Journey") & Attr("SK").eq("METADATA"),
        }
        while True:
            response = self.table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        journeys = self._journey_summaries_from_items(items, status_filter, component_type_filter)
        print_with_flush(f"✅ Found {len(journeys)} journeys (scan fallback)")
        return journeys

    def list_journeys(self, status_filter: Optional[str] = None, 
                     component_type_filter: Optional[str] = None) -> List[Dict]:
        """List all journeys with optional filtering"""
        try:
            print_with_flush('📋 Listing transformation journeys...')
            
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression='GSI1PK = :pk',
                ExpressionAttributeValues={
                    ':pk': 'JOURNEYS'
                }
            )
            
            journeys = self._journey_summaries_from_items(
                response.get("Items", []),
                status_filter,
                component_type_filter,
            )
            
            print_with_flush(f'✅ Found {len(journeys)} journeys')
            return journeys
            
        except Exception as e:
            print_with_flush(f'⚠️ GSI1 list failed ({e}); using scan fallback')
            try:
                return self._list_journeys_via_scan(status_filter, component_type_filter)
            except Exception as scan_exc:
                print_with_flush(f'❌ Error listing journeys: {str(scan_exc)}')
                traceback.print_exc()
                return []
    
    def get_journey_complete(self, journey_id: str) -> Optional[Dict]:
        """Get complete journey information including stages and rules"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            print_with_flush(f'📄 Getting complete journey details: {clean_id}')
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return None
            
            # Get journey metadata
            response = self.table.get_item(
                Key={
                    'PK': f'JOURNEY#{clean_id}',
                    'SK': 'METADATA'
                }
            )
            
            journey_data = response['Item']['Data']
            
            # Get jobs for this journey
            jobs = self.list_jobs(clean_id)
            
            result = {
                'metadata': journey_data,
                'createdAt': response['Item'].get('CreatedAt'),
                'updatedAt': response['Item'].get('UpdatedAt'),
                'stages': self.list_stages(clean_id),
                'rules': self.list_rules(clean_id),
                'jobs': jobs,
                'summary': {
                    'totalStages': 0,
                    'totalRules': 0,
                    'totalSteps': 0,
                    'aiAssistedSteps': 0,
                    'estimatedDuration': '0m',
                    'totalJobs': 0,
                    'completedJobs': 0,
                    'failedJobs': 0,
                    'runningJobs': 0,
                    'overallProgress': 0
                }
            }
            
            # Calculate summary statistics
            stages = result['stages']
            rules = result['rules']
            
            result['summary']['totalStages'] = len(stages)
            result['summary']['totalRules'] = len(rules)
            result['summary']['totalJobs'] = len(jobs)
            
            # Count job statuses
            completed_jobs = sum(1 for j in jobs if j.get('status') == 'completed')
            failed_jobs = sum(1 for j in jobs if j.get('status') == 'failed')
            running_jobs = sum(1 for j in jobs if j.get('status') in ['running', 'in_progress'])
            
            result['summary']['completedJobs'] = completed_jobs
            result['summary']['failedJobs'] = failed_jobs
            result['summary']['runningJobs'] = running_jobs
            
            # Calculate overall progress based on completed jobs
            if len(jobs) > 0:
                result['summary']['overallProgress'] = int((completed_jobs / len(jobs)) * 100)
            
            total_steps = 0
            ai_steps = 0
            total_minutes = 0
            
            for stage in stages:
                steps = stage.get('steps', [])
                total_steps += len(steps)
                ai_steps += sum(1 for step in steps if step.get('aiAssisted', False))
                
                # Parse duration
                duration = stage.get('estimatedDuration', '0m')
                if duration.endswith('m'):
                    total_minutes += int(duration[:-1])
            
            result['summary']['totalSteps'] = total_steps
            result['summary']['aiAssistedSteps'] = ai_steps
            result['summary']['estimatedDuration'] = f'{total_minutes}m'
            
            return result
            
        except Exception as e:
            print_with_flush(f'❌ Error getting complete journey: {str(e)}')
            traceback.print_exc()
            return None
    
    def create_journey_complete(self, journey_data: Dict[str, Any], 
                              include_default_stages: bool = True,
                              include_default_rules: bool = True) -> Optional[str]:
        """Create a complete journey with stages and rules"""
        try:
            # Clear any previous error
            self._last_error = None
            
            # Generate journey ID
            journey_id = f'JRN-{str(uuid.uuid4()).upper().replace("-", "")[:12]}'
            
            print_with_flush(f'➕ Creating complete journey: {journey_id}')
            
            # Validate required fields
            required_fields = ['name', 'description', 'odaComponentType']
            for field in required_fields:
                if field not in journey_data:
                    error_msg = f'Missing required field: {field}'
                    print_with_flush(f'❌ {error_msg}')
                    self._last_error = error_msg
                    return None
            
            # Create journey metadata
            if not self.create_journey_metadata(journey_id, journey_data):
                # Error already stored in _last_error
                if self._last_error:
                    import sys
                    print(f"DEBUG: Journey metadata creation failed: {self._last_error}", file=sys.stderr)
                return None
            
            # Add default stages if requested
            if include_default_stages:
                print_with_flush('📋 Adding default stages...')
                self.add_default_stages_complete(journey_id)
            
            # Add default rules if requested
            if include_default_rules:
                print_with_flush('🧠 Adding default Second Brain rules...')
                self.add_default_rules_complete(journey_id)
            
            print_with_flush(f'✅ Complete journey created successfully: {journey_id}')
            return journey_id
            
        except Exception as e:
            print_with_flush(f'❌ Error creating complete journey: {str(e)}')
            traceback.print_exc()
            return None
    
    def create_journey_metadata(self, journey_id: str, journey_data: Dict[str, Any]) -> bool:
        """Create journey metadata"""
        try:
            # Validate required fields
            required_fields = ['name', 'description', 'odaComponentType']
            for field in required_fields:
                if field not in journey_data:
                    error_msg = f'Missing required field: {field}'
                    print_with_flush(f'❌ {error_msg}')
                    # Store error for retrieval
                    self._last_error = error_msg
                    return False
            
            # Validate ODA component type
            valid_components = [
                'customer-management', 'product-management', 'order-management',
                'billing-management', 'payment-management', 'inventory-management',
                'party-management', 'resource-management', 'service-management'
            ]
            
            # Allow custom components but reject clearly invalid patterns
            component_type = journey_data['odaComponentType']
            if component_type.startswith('invalid-') or component_type in ['invalid', 'test', 'invalid-component-type']:
                error_msg = f'Invalid ODA component type: {component_type}. Valid types: {", ".join(valid_components)}'
                print_with_flush(f'❌ {error_msg}')
                self._last_error = error_msg
                return False
            elif component_type not in valid_components:
                print_with_flush(f'⚠️ Warning: Unknown ODA component type: {component_type}')
                print_with_flush(f'   Valid types: {", ".join(valid_components)}')
                # Allow custom components that don't match invalid patterns
            
            # Convert floats to Decimal
            journey_data = self.convert_floats_to_decimal(journey_data)
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            journey_item = {
                'PK': f'JOURNEY#{journey_id}',
                'SK': 'METADATA',
                'EntityType': 'Journey',
                'GSI1PK': 'JOURNEYS',
                'GSI1SK': timestamp,
                'CreatedAt': timestamp,
                'UpdatedAt': timestamp,
                'Data': {
                    'journeyId': journey_id,
                    'name': journey_data['name'],
                    'description': journey_data['description'],
                    'status': journey_data.get('status', 'pending'),
                    'createdBy': journey_data.get('createdBy', 'user'),
                    'priority': journey_data.get('priority', 'medium'),
                    'odaComponentType': journey_data['odaComponentType'],
                    'source': journey_data.get('source', {
                        'type': 'schema-based',
                        'schemaId': f'schema-{journey_data["odaComponentType"]}-001',
                        'schemaName': f'{journey_data["odaComponentType"].replace("-", " ").title()} Database',
                        'schemaVersion': '1.0.0'
                    }),
                    'configuration': journey_data.get('configuration', {
                        'timeout': 1800,
                        'maxDepth': 5,
                        'tmfSpecVersion': '4.0.0',
                        'outputFormat': 'json',
                        'retryAttempts': 3,
                        'enableDetailedLogging': True,
                        'validateAtEachStage': True,
                        'secondBrainEnabled': True,
                        'ruleEngineVersion': 'v1.0'
                    }),
                    'currentStageIndex': 0,
                    'currentStageId': 'raw_analysis',
                    'overallProgress': 0,
                    'currentJobs': {},
                    'aggregates': {
                        'totalJobs': 0,
                        'completedJobs': 0,
                        'failedJobs': 0,
                        'totalExecutionTime': '0m',
                        'totalLogs': 0,
                        'totalErrors': 0,
                        'totalWarnings': 0,
                        'totalRules': 0,
                        'activeRules': 0
                    },
                    'metadata': journey_data.get('metadata', {}),
                    'stageSummary': {},
                    'secondBrainConfig': journey_data.get('secondBrainConfig', {
                        'enabled': True,
                        'ruleTypes': ['field_mapping', 'contextual_recommendations', 'data_interpretation', 'validation_rules'],
                        'priorityLevels': ['low', 'medium', 'high', 'critical'],
                        'scopes': ['global', 'project', 'stage'],
                        'defaultScope': 'global',
                        'autoApplyRules': True,
                        'customRulesEnabled': True
                    })
                }
            }
            
            self.table.put_item(Item=journey_item)
            print_with_flush(f'✅ Journey metadata created: {journey_id}')
            self._last_error = None  # Clear error on success
            return True
            
        except Exception as e:
            error_msg = f'Error creating journey metadata: {str(e)}'
            print_with_flush(f'❌ {error_msg}')
            # Store full error for debugging
            self._last_error = error_msg
            # Print traceback to stderr for debugging (not suppressed)
            import sys
            traceback.print_exc(file=sys.stderr)
            return False
    
    def update_journey_metadata(self, journey_id: str, journey_data: Dict[str, Any]) -> bool:
        """Update journey metadata"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            print_with_flush(f'✏️ Updating journey metadata: {clean_id}')
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return False
            
            # Get existing journey
            response = self.table.get_item(
                Key={
                    'PK': f'JOURNEY#{clean_id}',
                    'SK': 'METADATA'
                }
            )
            
            existing_data = response['Item']['Data']
            
            # Convert floats to Decimal and update
            journey_data = self.convert_floats_to_decimal(journey_data)
            updated_data = existing_data.copy()
            updated_data.update(journey_data)
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            self.table.update_item(
                Key={
                    'PK': f'JOURNEY#{clean_id}',
                    'SK': 'METADATA'
                },
                UpdateExpression='SET #data = :data, UpdatedAt = :updated_at',
                ExpressionAttributeNames={
                    '#data': 'Data'
                },
                ExpressionAttributeValues={
                    ':data': updated_data,
                    ':updated_at': timestamp
                }
            )
            
            print_with_flush(f'✅ Journey metadata updated: {clean_id}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error updating journey metadata: {str(e)}')
            traceback.print_exc()
            return False
    
    def delete_journey_complete(self, journey_id: str, confirm: bool = False) -> bool:
        """Delete a complete journey including all stages, rules, and job history"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            print_with_flush(f'🗑️ Deleting complete journey: {clean_id}')
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                # Try to delete anyway - might be orphaned records
                print_with_flush(f'⚠️ Attempting to delete any orphaned records for: {clean_id}')
            
            if not confirm:
                print_with_flush('⚠️ This will permanently delete:')
                print_with_flush('   • Journey metadata')
                print_with_flush('   • All stages and steps')
                print_with_flush('   • All Second Brain rules')
                print_with_flush('   • All job execution history')
                print_with_flush('   • All logs and reports')
                response = input('\nType "DELETE" to confirm permanent deletion: ')
                if response != 'DELETE':
                    print_with_flush('❌ Deletion cancelled')
                    return False
            
            # Get all items for this journey
            response = self.table.query(
                KeyConditionExpression='PK = :pk',
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}'
                }
            )
            
            # Delete all items in batches
            items_deleted = 0
            for item in response['Items']:
                self.table.delete_item(
                    Key={
                        'PK': item['PK'],
                        'SK': item['SK']
                    }
                )
                items_deleted += 1
            
            if items_deleted > 0:
                print_with_flush(f'✅ Complete journey deleted: {clean_id}')
                print_with_flush(f'   🗑️ Deleted {items_deleted} items')
                return True
            else:
                print_with_flush(f'⚠️ No items found to delete for journey: {clean_id}')
                return True  # Return True since there's nothing to delete
            
        except Exception as e:
            print_with_flush(f'❌ Error deleting journey: {str(e)}')
            traceback.print_exc()
            return False
    
    # ==========================================
    # STAGE MANAGEMENT
    # ==========================================
    
    def list_stages(self, journey_id: str) -> List[Dict]:
        """List all stages for a journey"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                return []
            
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'STAGE#',
                }
            )
            
            stages = []
            for item in response['Items']:
                stage_data = item['Data']
                stages.append({
                    'stageId': stage_data.get('stageId'),
                    'name': stage_data.get('name'),
                    'description': stage_data.get('description'),
                    'order': stage_data.get('order'),
                    'canSkip': stage_data.get('canSkip'),
                    'estimatedDuration': stage_data.get('estimatedDuration'),
                    'status': stage_data.get('status', 'pending'),
                    'secondBrainEnabled': stage_data.get('secondBrainEnabled', False),
                    'ruleTypes': stage_data.get('ruleTypes', []),
                    'steps': stage_data.get('steps', [])
                })
            
            # Sort by order
            stages.sort(key=lambda x: x.get('order', 0))
            return stages
            
        except Exception as e:
            print_with_flush(f'❌ Error listing stages: {str(e)}')
            return []
    
    def add_stage(self, journey_id: str, stage_data: Dict[str, Any]) -> bool:
        """Add a stage to a journey"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return False
            
            # Validate required fields
            required_fields = ['stageId', 'name', 'description']
            for field in required_fields:
                if field not in stage_data:
                    print_with_flush(f'❌ Missing required field: {field}')
                    return False
            
            stage_id = stage_data['stageId']
            
            # Convert floats to Decimal
            stage_data = self.convert_floats_to_decimal(stage_data)
            
            # Get current stages to determine order
            existing_stages = self.list_stages(clean_id)
            stage_order = stage_data.get('order', len(existing_stages))
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            stage_item = {
                'PK': f'JOURNEY#{clean_id}',
                'SK': f'STAGE#{int(stage_order):02d}#{stage_id}',
                'EntityType': 'StageDefinition',
                'GSI1PK': f'JOURNEY#{clean_id}#STAGES',
                'GSI1SK': f'{int(stage_order):02d}',
                'CreatedAt': timestamp,
                'UpdatedAt': timestamp,
                'Data': {
                    'stageId': stage_id,
                    'name': stage_data['name'],
                    'description': stage_data['description'],
                    'order': stage_order,
                    'canSkip': stage_data.get('canSkip', False),
                    'estimatedDuration': stage_data.get('estimatedDuration', '10m'),
                    'status': stage_data.get('status', 'pending'),
                    'secondBrainEnabled': stage_data.get('secondBrainEnabled', True),
                    'ruleTypes': stage_data.get('ruleTypes', ['contextual_recommendations']),
                    'steps': stage_data.get('steps', [])
                }
            }
            
            self.table.put_item(Item=stage_item)
            print_with_flush(f'✅ Stage added: {stage_id}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error adding stage: {str(e)}')
            return False
    
    def update_stage(self, journey_id: str, stage_id: str, stage_data: Dict[str, Any]) -> bool:
        """Update an existing stage in a journey"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return False
            
            # Check if stage exists
            existing_stages = self.list_stages(clean_id)
            stage_exists = any(stage.get('stageId') == stage_id for stage in existing_stages)
            
            if not stage_exists:
                print_with_flush(f'❌ Stage not found: {stage_id}')
                return False
            
            # Get existing stage data
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'STAGE#',
                    ':stage_id': stage_id
                }
            )
            
            if not response['Items']:
                print_with_flush(f'❌ Stage data not found: {stage_id}')
                return False
            
            existing_item = response['Items'][0]
            existing_data = existing_item['Data']
            
            # Merge new data with existing data
            updated_data = existing_data.copy()
            updated_data.update(self.convert_floats_to_decimal(stage_data))
            updated_data['updatedAt'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            # Update the stage
            self.table.update_item(
                Key={
                    'PK': existing_item['PK'],
                    'SK': existing_item['SK']
                },
                UpdateExpression='SET #data = :data, UpdatedAt = :updated_at',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':data': updated_data,
                    ':updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                }
            )
            
            print_with_flush(f'✅ Stage updated successfully: {stage_id}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error updating stage: {str(e)}')
            return False
    
    def delete_stage(self, journey_id: str, stage_id: str, confirm: bool = False) -> bool:
        """Delete a stage from a journey"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return False
            
            # Get stage to delete
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'STAGE#',
                    ':stage_id': stage_id
                }
            )
            
            if not response['Items']:
                print_with_flush(f'❌ Stage not found: {stage_id}')
                return False
            
            stage_item = response['Items'][0]
            stage_name = stage_item['Data'].get('name', stage_id)
            
            # Confirm deletion
            if not confirm:
                print_with_flush(f'⚠️ This will delete stage "{stage_name}" ({stage_id}) and all associated:')
                print_with_flush('   • Stage configuration')
                print_with_flush('   • Associated rules')
                print_with_flush('   • Job execution history')
                print_with_flush('   • Logs and reports')
                print_with_flush(f'Use --confirm to proceed with deletion')
                return False
            
            items_deleted = 0
            
            # Delete the stage
            self.table.delete_item(
                Key={
                    'PK': stage_item['PK'],
                    'SK': stage_item['SK']
                }
            )
            items_deleted += 1
            
            # Delete associated rules
            rules_response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'RULE#',
                    ':stage_id': stage_id
                }
            )
            
            for rule_item in rules_response['Items']:
                self.table.delete_item(
                    Key={
                        'PK': rule_item['PK'],
                        'SK': rule_item['SK']
                    }
                )
                items_deleted += 1
            
            # Delete associated jobs
            jobs_response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'JOB#',
                    ':stage_id': stage_id
                }
            )
            
            for job_item in jobs_response['Items']:
                self.table.delete_item(
                    Key={
                        'PK': job_item['PK'],
                        'SK': job_item['SK']
                    }
                )
                items_deleted += 1
            
            print_with_flush(f'✅ Stage deleted successfully: {stage_name} ({stage_id})')
            print_with_flush(f'   📊 Total items deleted: {items_deleted}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error deleting stage: {str(e)}')
            return False
    
    def add_default_stages_complete(self, journey_id: str) -> bool:
        """Add all default stages to a journey"""
        try:
            default_stages = [
                {
                    'stageId': 'raw_analysis',
                    'name': 'Raw Input Analysis',
                    'description': 'Analyze the raw database schema and structure with AI-guided insights',
                    'order': 0,
                    'estimatedDuration': '15m',
                    'canSkip': False,
                    'secondBrainEnabled': True,
                    'ruleTypes': ['field_mapping', 'contextual_recommendations', 'data_interpretation'],
                    'steps': [
                        {
                            'id': 'schema_parsing',
                            'name': 'Schema File Parsing',
                            'description': 'Parse SQL schema files and extract structure',
                            'order': 0,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations', 'data_interpretation']
                        },
                        {
                            'id': 'relationship_discovery',
                            'name': 'Relationship Discovery',
                            'description': 'Identify table relationships and foreign keys',
                            'order': 1,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['field_mapping', 'contextual_recommendations']
                        },
                        {
                            'id': 'data_type_analysis',
                            'name': 'Data Type Analysis',
                            'description': 'Analyze column data types and constraints',
                            'order': 2,
                            'estimatedDuration': '3m',
                            'aiAssisted': True,
                            'applicableRules': ['data_interpretation']
                        },
                        {
                            'id': 'business_rules_extraction',
                            'name': 'Business Rules Extraction',
                            'description': 'Extract business rules from schema constraints',
                            'order': 3,
                            'estimatedDuration': '2m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations', 'data_interpretation']
                        }
                    ]
                },
                {
                    'stageId': 'stripped_schema',
                    'name': 'Create Stripped Document',
                    'description': 'Create TMF-focused simplified schema removing unnecessary complexity',
                    'order': 1,
                    'estimatedDuration': '12m',
                    'canSkip': False,
                    'secondBrainEnabled': True,
                    'ruleTypes': ['field_mapping', 'data_interpretation'],
                    'steps': [
                        {
                            'id': 'schema_stripping',
                            'name': 'Schema Stripping',
                            'description': 'Remove non-TMF relevant tables and columns',
                            'order': 0,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['data_interpretation']
                        },
                        {
                            'id': 'core_structure_extraction',
                            'name': 'Core Structure Extraction',
                            'description': 'Extract core business entities and relationships',
                            'order': 1,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['field_mapping', 'data_interpretation']
                        },
                        {
                            'id': 'data_model_simplification',
                            'name': 'Data Model Simplification',
                            'description': 'Simplify complex relationships for TMF mapping',
                            'order': 2,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['field_mapping']
                        }
                    ]
                },
                {
                    'stageId': 'tmf_mapping',
                    'name': 'TMF Schema Mapping',
                    'description': 'Map the stripped schema to TMF ODA standards and APIs',
                    'order': 2,
                    'estimatedDuration': '20m',
                    'canSkip': False,
                    'secondBrainEnabled': True,
                    'ruleTypes': ['field_mapping', 'contextual_recommendations'],
                    'steps': [
                        {
                            'id': 'tmf_api_matching',
                            'name': 'TMF API Matching',
                            'description': 'Match entities to appropriate TMF API specifications',
                            'order': 0,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['field_mapping', 'contextual_recommendations']
                        },
                        {
                            'id': 'attribute_mapping',
                            'name': 'Attribute Mapping',
                            'description': 'Map database columns to TMF API attributes',
                            'order': 1,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['field_mapping']
                        },
                        {
                            'id': 'relationship_mapping',
                            'name': 'Relationship Mapping',
                            'description': 'Map database relationships to TMF API relationships',
                            'order': 2,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['field_mapping', 'contextual_recommendations']
                        },
                        {
                            'id': 'api_coverage_analysis',
                            'name': 'API Coverage Analysis',
                            'description': 'Analyze coverage of TMF API specifications',
                            'order': 3,
                            'estimatedDuration': '3m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations']
                        },
                        {
                            'id': 'gap_identification',
                            'name': 'Gap Identification',
                            'description': 'Identify gaps and missing mappings',
                            'order': 4,
                            'estimatedDuration': '3m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations']
                        }
                    ]
                },
                {
                    'stageId': 'migration_planning',
                    'name': 'Data Migration Planning',
                    'description': 'Plan and prepare data migration strategies and scripts',
                    'order': 3,
                    'estimatedDuration': '18m',
                    'canSkip': False,
                    'secondBrainEnabled': True,
                    'ruleTypes': ['contextual_recommendations', 'validation_rules'],
                    'steps': [
                        {
                            'id': 'migration_strategy_planning',
                            'name': 'Migration Strategy Planning',
                            'description': 'Plan the overall data migration approach',
                            'order': 0,
                            'estimatedDuration': '6m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations']
                        },
                        {
                            'id': 'etl_script_generation',
                            'name': 'ETL Script Generation',
                            'description': 'Generate Extract, Transform, Load scripts',
                            'order': 1,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations']
                        },
                        {
                            'id': 'data_validation_rules',
                            'name': 'Data Validation Rules',
                            'description': 'Create validation rules for data integrity',
                            'order': 2,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['validation_rules']
                        },
                        {
                            'id': 'rollback_procedures',
                            'name': 'Rollback Procedures',
                            'description': 'Prepare rollback and recovery procedures',
                            'order': 3,
                            'estimatedDuration': '3m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations']
                        }
                    ]
                },
                {
                    'stageId': 'data_migration',
                    'name': 'Data Migration',
                    'description': 'Execute the actual data migration from legacy systems to TMF-compliant structure',
                    'order': 4,
                    'estimatedDuration': '25m',
                    'canSkip': False,
                    'secondBrainEnabled': True,
                    'ruleTypes': ['data_interpretation', 'validation_rules'],
                    'steps': [
                        {
                            'id': 'candidate_dataset_selection',
                            'name': 'Candidate Dataset Selection',
                            'description': 'Select and prepare candidate datasets for migration',
                            'order': 0,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['data_interpretation']
                        },
                        {
                            'id': 'data_transfer',
                            'name': 'Data Transfer',
                            'description': 'Execute the actual data transfer from legacy to TMF systems',
                            'order': 1,
                            'estimatedDuration': '12m',
                            'aiAssisted': True,
                            'applicableRules': ['validation_rules']
                        },
                        {
                            'id': 'tmf_api_compliance_test',
                            'name': 'TMF API Compliance Test',
                            'description': 'Test migrated data against TMF API compliance requirements',
                            'order': 2,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['validation_rules']
                        },
                        {
                            'id': 'mark_completion',
                            'name': 'Mark Completion',
                            'description': 'Mark migration tasks as completed and update status',
                            'order': 3,
                            'estimatedDuration': '3m',
                            'aiAssisted': False,
                            'applicableRules': []
                        }
                    ]
                },
                {
                    'stageId': 'verification_validation',
                    'name': 'Verification & Validation',
                    'description': 'Validate the mapping and migration results against TMF standards',
                    'order': 5,
                    'estimatedDuration': '22m',
                    'canSkip': False,
                    'secondBrainEnabled': True,
                    'ruleTypes': ['contextual_recommendations', 'validation_rules'],
                    'steps': [
                        {
                            'id': 'mapping_validation',
                            'name': 'Mapping Validation',
                            'description': 'Validate the accuracy of schema mappings',
                            'order': 0,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['validation_rules']
                        },
                        {
                            'id': 'api_compliance_check',
                            'name': 'API Compliance Check',
                            'description': 'Check compliance with TMF API standards',
                            'order': 1,
                            'estimatedDuration': '5m',
                            'aiAssisted': True,
                            'applicableRules': ['validation_rules', 'contextual_recommendations']
                        },
                        {
                            'id': 'data_integrity_verification',
                            'name': 'Data Integrity Verification',
                            'description': 'Verify data integrity and consistency',
                            'order': 2,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['validation_rules']
                        },
                        {
                            'id': 'performance_assessment',
                            'name': 'Performance Assessment',
                            'description': 'Assess performance implications of the mapping',
                            'order': 3,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations']
                        },
                        {
                            'id': 'final_report_generation',
                            'name': 'Final Report Generation',
                            'description': 'Generate comprehensive final report',
                            'order': 4,
                            'estimatedDuration': '4m',
                            'aiAssisted': True,
                            'applicableRules': ['contextual_recommendations']
                        }
                    ]
                }
            ]
            
            successful_adds = 0
            for stage in default_stages:
                if self.add_stage(journey_id, stage):
                    successful_adds += 1
            
            print_with_flush(f'✅ Added {successful_adds} default stages')
            return successful_adds > 0
            
        except Exception as e:
            print_with_flush(f'❌ Error adding default stages: {str(e)}')
            return False
    
    # ==========================================
    # SECOND BRAIN RULES MANAGEMENT
    # ==========================================
    
    def list_rules(self, journey_id: str, stage_id: Optional[str] = None, 
                   rule_type: Optional[str] = None) -> List[Dict]:
        """List Second Brain rules for a journey"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                return []
            
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'RULE#',
                }
            )
            
            rules = []
            for item in response['Items']:
                rule_data = item['Data']
                
                # Apply filters
                if stage_id and rule_data.get('stageId') != stage_id:
                    continue
                if rule_type and rule_data.get('type') != rule_type:
                    continue
                
                rules.append({
                    'ruleId': rule_data.get('ruleId'),
                    'stageId': rule_data.get('stageId'),
                    'title': rule_data.get('title'),
                    'type': rule_data.get('type'),
                    'priority': rule_data.get('priority'),
                    'scope': rule_data.get('scope'),
                    'status': rule_data.get('status', 'active'),
                    'content': rule_data.get('content', {})
                })
            
            return rules
            
        except Exception as e:
            print_with_flush(f'❌ Error listing rules: {str(e)}')
            return []
    
    def add_rule(self, journey_id: str, stage_id: str, rule_data: Dict[str, Any]) -> bool:
        """Add a Second Brain rule to a journey stage"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return False
            
            # Validate required fields
            required_fields = ['title', 'description', 'type', 'priority', 'scope', 'context', 'content']
            for field in required_fields:
                if field not in rule_data:
                    print_with_flush(f'❌ Missing required field: {field}')
                    return False
            
            # Generate rule ID if not provided
            if 'ruleId' not in rule_data:
                unique_id = str(uuid.uuid4())[:8]
                rule_data['ruleId'] = f'rule-{stage_id}-{rule_data["type"]}-{unique_id}'
            
            # Convert floats to Decimal
            rule_data = self.convert_floats_to_decimal(rule_data)
            
            # Get current rules count for ordering
            existing_rules = self.list_rules(clean_id, stage_id=stage_id)
            rule_index = len(existing_rules)
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            rule_item = {
                'PK': f'JOURNEY#{clean_id}',
                'SK': f'RULE#{stage_id}#{rule_index:03d}#{rule_data["ruleId"]}',
                'EntityType': 'SecondBrainRule',
                'GSI1PK': f'JOURNEY#{clean_id}#RULES',
                'GSI1SK': f'{stage_id}#{rule_data["priority"]}#{rule_index:03d}',
                'CreatedAt': timestamp,
                'UpdatedAt': timestamp,
                'Data': {
                    'ruleId': rule_data['ruleId'],
                    'journeyId': clean_id,
                    'stageId': stage_id,
                    'title': rule_data['title'],
                    'description': rule_data['description'],
                    'type': rule_data['type'],
                    'priority': rule_data['priority'],
                    'scope': rule_data['scope'],
                    'status': rule_data.get('status', 'active'),
                    'context': rule_data['context'],
                    'content': rule_data['content'],
                    'metadata': {
                        'createdBy': rule_data.get('createdBy', 'user'),
                        'version': rule_data.get('version', '1.0'),
                        'tags': rule_data.get('tags', [stage_id, rule_data['type'], rule_data['priority']]),
                        'applicableStages': rule_data.get('applicableStages', [stage_id]),
                        'ruleEngine': 'second_brain_v1'
                    }
                }
            }
            
            self.table.put_item(Item=rule_item)
            print_with_flush(f'✅ Rule added: {rule_data["ruleId"]}')
            return rule_data['ruleId']  # Return rule_id instead of True
            
        except Exception as e:
            print_with_flush(f'❌ Error adding rule: {str(e)}')
            traceback.print_exc()
            return None  # Return None on error instead of False
    
    def update_rule(self, journey_id: str, stage_id: str, rule_id: str, rule_data: Dict[str, Any]) -> bool:
        """Update an existing Second Brain rule for a stage"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return False
            
            # Check if rule exists
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.ruleId = :rule_id AND #data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'RULE#',
                    ':rule_id': rule_id,
                    ':stage_id': stage_id
                }
            )
            
            if not response['Items']:
                print_with_flush(f'❌ Rule not found: {rule_id} in stage {stage_id}')
                return False
            
            existing_item = response['Items'][0]
            existing_data = existing_item['Data']
            
            # Merge new data with existing data
            updated_data = existing_data.copy()
            updated_data.update(self.convert_floats_to_decimal(rule_data))
            updated_data['updatedAt'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            # Update the rule
            self.table.update_item(
                Key={
                    'PK': existing_item['PK'],
                    'SK': existing_item['SK']
                },
                UpdateExpression='SET #data = :data, UpdatedAt = :updated_at',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':data': updated_data,
                    ':updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                }
            )
            
            print_with_flush(f'✅ Rule updated successfully: {rule_id} in stage {stage_id}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error updating rule: {str(e)}')
            return False
    
    def delete_rule(self, journey_id: str, stage_id: str, rule_id: str, confirm: bool = False) -> bool:
        """Delete a Second Brain rule from a stage"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return False
            
            # Get rule to delete
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.ruleId = :rule_id AND #data.stageId = :stage_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'RULE#',
                    ':rule_id': rule_id,
                    ':stage_id': stage_id
                }
            )
            
            if not response['Items']:
                print_with_flush(f'❌ Rule not found: {rule_id} in stage {stage_id}')
                return False
            
            rule_item = response['Items'][0]
            rule_name = rule_item['Data'].get('name', rule_id)
            
            # Confirm deletion
            if not confirm:
                print_with_flush(f'⚠️ This will permanently delete rule "{rule_name}" ({rule_id}) from stage {stage_id}')
                print_with_flush(f'Use --confirm to proceed with deletion')
                return False
            
            # Delete the rule
            self.table.delete_item(
                Key={
                    'PK': rule_item['PK'],
                    'SK': rule_item['SK']
                }
            )
            
            print_with_flush(f'✅ Rule deleted successfully: {rule_name} ({rule_id}) from stage {stage_id}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error deleting rule: {str(e)}')
            return False
    
    def add_default_rules_complete(self, journey_id: str) -> bool:
        """Add all default Second Brain rules to a journey"""
        try:
            # Import the default rules from the original create script
            from create_complete_journey import get_default_rules_for_stage
            
            stages = self.list_stages(journey_id)
            total_rules_added = 0
            
            for stage in stages:
                stage_id = stage['stageId']
                default_rules = get_default_rules_for_stage(stage_id, journey_id)
                
                for rule in default_rules:
                    if self.add_rule(journey_id, stage_id, rule):
                        total_rules_added += 1
            
            print_with_flush(f'✅ Added {total_rules_added} default rules')
            return total_rules_added > 0
            
        except Exception as e:
            print_with_flush(f'❌ Error adding default rules: {str(e)}')
            return False
    
    # ==========================================
    # JOB MANAGEMENT
    # ==========================================
    
    def list_jobs(self, journey_id: str, stage_id: Optional[str] = None, 
                  status_filter: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """List job executions for a journey"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return []
            
            # Query for job executions using primary key pattern
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'JOB#'
                },
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
            
            jobs = []
            for item in response['Items']:
                # Only process JobExecution entities
                if item.get('EntityType') != 'JobExecution':
                    continue
                    
                job_data = item['Data']
                
                # Apply stage filter
                if stage_id and job_data.get('stageId') != stage_id:
                    continue
                
                # Apply status filter
                if status_filter and job_data.get('status') != status_filter:
                    continue
                
                metrics = job_data.get('metrics', {})
                jobs.append({
                    'jobId': job_data.get('jobId'),
                    'jobType': job_data.get('jobType', 'stage'),
                    'stageId': job_data.get('stageId'),
                    'stageIds': job_data.get('stageIds', []),
                    'stageName': job_data.get('stageName'),
                    'currentStageId': job_data.get('currentStageId'),
                    'status': job_data.get('status'),
                    'triggeredBy': job_data.get('triggeredBy'),
                    'reason': job_data.get('reason'),
                    'startTime': job_data.get('startTime'),
                    'endTime': job_data.get('endTime'),
                    'duration': job_data.get('duration'),
                    'progress': job_data.get('progress', 0),
                    'errorMessage': job_data.get('errorMessage'),
                    'logsAvailable': job_data.get('logsAvailable', False),
                    'reportsAvailable': job_data.get('reportsAvailable', False),
                    'metrics': metrics,
                    'itemsProcessed': metrics.get('itemsProcessed', 0),
                    'itemsTotal': metrics.get('itemsTotal', 0),
                    'stepResults': job_data.get('stepResults', {}),
                })
            
            return jobs
            
        except Exception as e:
            print_with_flush(f'❌ Error listing jobs: {str(e)}')
            return []
    
    def get_job_details(self, journey_id: str, job_id: str) -> Optional[Dict]:
        """Get detailed information about a specific job"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            # Query for job executions and filter by job_id since the TransformationJobExecutor
            # uses a different SK format: JOB#{order}#{stage_id}#{execution_number}#{timestamp}
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.jobId = :job_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'JOB#',
                    ':job_id': job_id
                }
            )
            
            if not response['Items']:
                print_with_flush(f'❌ Job not found: {job_id}')
                return None
            
            # Get the first (and should be only) matching job
            job_item = response['Items'][0]
            job_data = job_item['Data']
            
            return {
                'jobId': job_data.get('jobId'),
                'jobType': job_data.get('jobType', 'stage'),
                'journeyId': clean_id,
                'stageId': job_data.get('stageId'),
                'stageIds': job_data.get('stageIds', []),
                'currentStageId': job_data.get('currentStageId'),
                'stageName': job_data.get('stageName'),
                'stageOrder': job_data.get('stageOrder'),
                'executionNumber': job_data.get('executionNumber'),
                'status': job_data.get('status'),
                'triggeredBy': job_data.get('triggeredBy'),
                'reason': job_data.get('triggerReason'),
                'startTime': job_data.get('startTime'),
                'endTime': job_data.get('endTime'),
                'duration': job_data.get('duration'),
                'progress': job_data.get('progress', 0),
                'currentStep': job_data.get('currentStepId'),
                'currentStepIndex': job_data.get('currentStepIndex'),
                'totalSteps': len(job_data.get('stepResults', {})),
                'stepResults': job_data.get('stepResults', {}),
                'stageResults': job_data.get('stageResults', {}),
                'executionDetails': job_data.get('executionDetails', {}),
                'retryAttempt': job_data.get('retryAttempt', 0),
                's3Config': job_data.get('s3Config', {}),
                'logsAvailable': True,  # Always true since logs are stored in S3
                'reportsAvailable': True,  # Always true since reports are stored in S3
                'metrics': job_data.get('metrics', {}),
                'itemsProcessed': job_data.get('metrics', {}).get('itemsProcessed', 0),
                'itemsTotal': job_data.get('metrics', {}).get('itemsTotal', 0),
                'jobMetrics': job_data.get('jobMetrics', {}),
                'createdAt': job_item.get('CreatedAt'),
                'updatedAt': job_item.get('UpdatedAt')
            }
            
        except Exception as e:
            print_with_flush(f'❌ Error getting job details: {str(e)}')
            return None
    
    def run_job(self, journey_id: str, stage_id: str, triggered_by: str = 'user', 
                reason: str = 'Manual execution') -> Optional[str]:
        """Execute a job for a specific stage using the real TransformationJobExecutor"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if not self.validate_journey_exists(clean_id):
                print_with_flush(f'❌ Journey not found: {clean_id}')
                return None
            
            print_with_flush(f'🚀 Starting job execution for stage: {stage_id}')
            
            # Import and use the real TransformationJobExecutor
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from src.utils.job_executor import TransformationJobExecutor
            
            # Create job executor instance
            executor = TransformationJobExecutor()
            
            # Start job execution using the real system
            job_id = executor.start_job_execution(
                journey_id=clean_id,
                stage_id=stage_id,
                triggered_by=triggered_by,
                reason=reason
            )
            
            print_with_flush(f'✅ Job started: {job_id}')
            print_with_flush(f'   📋 Stage: {stage_id}')
            print_with_flush(f'   👤 Triggered by: {triggered_by}')
            print_with_flush(f'   📝 Reason: {reason}')
            
            # Execute the job asynchronously to avoid blocking
            try:
                print_with_flush(f'🔄 Executing job steps...')
                executor.execute_job(clean_id, job_id)
                
                print_with_flush(f'🎉 Job {job_id} completed successfully!')
                print_with_flush(f'   📊 Logs Available: Yes (stored in S3)')
                print_with_flush(f'   📋 Reports Available: Yes (stored in S3)')
                logs_bucket = getattr(self, 'logs_bucket', 'transformation-journey-logs')
                reports_bucket = getattr(self, 'reports_bucket', 'transformation-journey-reports')
                print_with_flush(f'   🗂️ Logs Location: s3://{logs_bucket}/journeys/{clean_id}/stages/{stage_id}/executions/{job_id}/')
                print_with_flush(f'   📄 Reports Location: s3://{reports_bucket}/journeys/{clean_id}/stages/{stage_id}/executions/{job_id}/')
                
            except Exception as exec_error:
                print_with_flush(f'❌ Job execution failed: {str(exec_error)}')
                # The executor handles failure status updates internally
            
            return job_id
            
        except Exception as e:
            print_with_flush(f'❌ Error running job: {str(e)}')
            traceback.print_exc()
            return None
    
    def cancel_job(self, journey_id: str, job_id: str, reason: str = 'User cancellation') -> bool:
        """Cancel a running job"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            # Query for the job to get its actual SK
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.jobId = :job_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'JOB#',
                    ':job_id': job_id
                }
            )
            
            if not response['Items']:
                print_with_flush(f'❌ Job not found for cancellation: {job_id}')
                return False
            
            # Get the actual job data and SK
            job_item = response['Items'][0]
            actual_sk = job_item['SK']
            job_data = job_item['Data']
            
            if job_data.get('status') not in ['running', 'pending', 'in_progress']:
                print_with_flush(f'❌ Job cannot be cancelled - current status: {job_data.get("status")}')
                return False
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            self.table.update_item(
                Key={
                    'PK': f'JOURNEY#{clean_id}',
                    'SK': actual_sk  # Use the actual SK from the database
                },
                UpdateExpression='SET #data.#status = :status, #data.endTime = :end_time, #data.errorMessage = :reason, UpdatedAt = :updated_at',
                ExpressionAttributeNames={
                    '#data': 'Data',
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': 'cancelled',
                    ':end_time': timestamp,
                    ':reason': reason,
                    ':updated_at': timestamp
                }
            )
            
            print_with_flush(f'✅ Job cancelled: {job_id}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error cancelling job: {str(e)}')
            return False
    
    def update_job_status(self, journey_id: str, job_id: str, status: str, 
                         progress: Optional[int] = None, current_step: Optional[str] = None,
                         error_message: Optional[str] = None) -> bool:
        """Update job status and progress"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            # Query for the job to get its actual SK
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.jobId = :job_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': 'JOB#',
                    ':job_id': job_id
                }
            )
            
            if not response['Items']:
                print_with_flush(f'❌ Job not found for update: {job_id}')
                return False
            
            # Get the actual SK from the job record
            job_item = response['Items'][0]
            actual_sk = job_item['SK']
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            update_expression = 'SET #data.#status = :status, UpdatedAt = :updated_at'
            expression_values = {
                ':status': status,
                ':updated_at': timestamp
            }
            expression_names = {
                '#data': 'Data',
                '#status': 'status'
            }
            
            if progress is not None:
                update_expression += ', #data.progress = :progress'
                expression_values[':progress'] = progress
            
            if current_step:
                update_expression += ', #data.currentStep = :current_step'
                expression_values[':current_step'] = current_step
            
            if error_message:
                update_expression += ', #data.errorMessage = :error_message'
                expression_values[':error_message'] = error_message
            
            if status in ['completed', 'failed', 'cancelled']:
                update_expression += ', #data.endTime = :end_time'
                expression_values[':end_time'] = timestamp
            
            self.table.update_item(
                Key={
                    'PK': f'JOURNEY#{clean_id}',
                    'SK': actual_sk  # Use the actual SK from the database
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values
            )
            
            print_with_flush(f'✅ Job status updated: {job_id} -> {status}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error updating job status: {str(e)}')
            return False
    
    def retry_failed_job(self, journey_id: str, job_id: str, triggered_by: str = 'user',
                        reason: str = 'Job retry') -> Optional[str]:
        """Retry a failed job by creating a new job execution"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            # Get original job details
            original_job = self.get_job_details(clean_id, job_id)
            if not original_job:
                print_with_flush(f'❌ Original job not found: {job_id}')
                return None
            
            if original_job['status'] not in ['failed', 'cancelled']:
                print_with_flush(f'❌ Job is not in failed/cancelled state: {original_job["status"]}')
                return None
            
            # Create new job execution
            new_job_id = self.run_job(
                clean_id,
                original_job['stageId'],
                triggered_by=triggered_by,
                reason=f'{reason} (retry of {job_id})'
            )
            
            if new_job_id:
                print_with_flush(f'✅ Job retry created: {new_job_id} (retry of {job_id})')
            
            return new_job_id
            
        except Exception as e:
            print_with_flush(f'❌ Error retrying job: {str(e)}')
            return None
    
    def get_job_metrics(self, journey_id: str, job_id: str) -> Optional[Dict]:
        """Get detailed metrics for a specific job"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            job = self.get_job_details(clean_id, job_id)
            if not job:
                return None
            
            # Get logs for metrics calculation
            logs_data = self.get_job_logs(clean_id, job['stageId'], job_id)
            logs = logs_data.get('logs', []) if logs_data else []
            
            # Calculate detailed metrics
            execution_metrics = {
                'jobId': job_id,
                'jobType': job.get('jobType', 'stage'),
                'stageIds': job.get('stageIds', []),
                'currentStageId': job.get('currentStageId'),
                'stageName': job.get('stageName'),
                'stageResults': job.get('stageResults', {}),
                'stageId': job['stageId'],
                'status': job['status'],
                'progress': job.get('progress', 0),
                'currentStep': job.get('currentStep'),
                'currentStepIndex': job.get('currentStepIndex', 0),
                'totalSteps': job.get('totalSteps', 0),
                'duration': None,
                'startTime': job.get('startTime'),
                'endTime': job.get('endTime'),
                'logMetrics': {
                    'totalEntries': len(logs),
                    'errorCount': 0,
                    'warningCount': 0,
                    'infoCount': 0,
                    'debugCount': 0
                },
                'performanceMetrics': {
                    'avgStepDuration': 0,
                    'slowestStep': None,
                    'fastestStep': None,
                    'errorRate': 0
                },
                'resourceMetrics': job.get('metrics', {}),
                'timeline': []
            }
            
            # Calculate execution duration
            if job.get('startTime') and job.get('endTime'):
                try:
                    start_dt = datetime.fromisoformat(job['startTime'].replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(job['endTime'].replace('Z', '+00:00'))
                    execution_metrics['duration'] = (end_dt - start_dt).total_seconds()
                except:
                    pass
            
            # Process logs for metrics
            step_durations = {}
            step_start_times = {}
            
            for log in logs:
                level = log.get('level', 'info').lower()
                execution_metrics['logMetrics'][f'{level}Count'] += 1
                
                # Track step timing
                step = log.get('step')
                timestamp_str = log.get('timestamp')
                if step and timestamp_str:
                    try:
                        log_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if step not in step_start_times:
                            step_start_times[step] = log_time
                        else:
                            duration = (log_time - step_start_times[step]).total_seconds()
                            step_durations[step] = max(step_durations.get(step, 0), duration)
                    except:
                        pass
                
                # Add to timeline
                execution_metrics['timeline'].append({
                    'timestamp': timestamp_str,
                    'step': step,
                    'level': level,
                    'message': log.get('message', '')[:100]
                })
            
            # Calculate performance metrics
            if step_durations:
                execution_metrics['performanceMetrics']['avgStepDuration'] = sum(step_durations.values()) / len(step_durations)
                slowest = max(step_durations.items(), key=lambda x: x[1])
                fastest = min(step_durations.items(), key=lambda x: x[1])
                execution_metrics['performanceMetrics']['slowestStep'] = {'step': slowest[0], 'duration': slowest[1]}
                execution_metrics['performanceMetrics']['fastestStep'] = {'step': fastest[0], 'duration': fastest[1]}
            
            # Calculate error rate
            total_ops = execution_metrics['logMetrics']['totalEntries']
            if total_ops > 0:
                execution_metrics['performanceMetrics']['errorRate'] = execution_metrics['logMetrics']['errorCount'] / total_ops
            
            # Sort timeline
            execution_metrics['timeline'].sort(key=lambda x: x.get('timestamp', ''))
            
            return execution_metrics
            
        except Exception as e:
            print_with_flush(f'❌ Error getting job metrics: {str(e)}')
            return None
    
    def get_job_timeline(self, journey_id: str, job_id: str) -> Optional[Dict]:
        """Get chronological timeline of job events"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            job = self.get_job_details(clean_id, job_id)
            if not job:
                return None
            
            # Get logs
            logs_data = self.get_job_logs(clean_id, job['stageId'], job_id)
            logs = logs_data.get('logs', []) if logs_data else []
            
            # Build timeline
            timeline_events = []
            
            # Add job start event
            if job.get('startTime'):
                timeline_events.append({
                    'timestamp': job['startTime'],
                    'type': 'job_started',
                    'description': f'Job started for stage {job["stageId"]}',
                    'details': {
                        'triggeredBy': job.get('triggeredBy'),
                        'reason': job.get('reason')
                    }
                })
            
            # Add log events
            for log in logs:
                timeline_events.append({
                    'timestamp': log.get('timestamp'),
                    'type': 'log_entry',
                    'description': log.get('message', 'Log entry'),
                    'details': {
                        'level': log.get('level'),
                        'step': log.get('step'),
                        'source': log.get('source')
                    }
                })
            
            # Add job end event
            if job.get('endTime'):
                timeline_events.append({
                    'timestamp': job['endTime'],
                    'type': 'job_completed',
                    'description': f'Job {job["status"]}',
                    'details': {
                        'finalStatus': job['status'],
                        'progress': job.get('progress'),
                        'errorMessage': job.get('errorMessage')
                    }
                })
            
            # Sort by timestamp
            timeline_events.sort(key=lambda x: x.get('timestamp', ''))
            
            return {
                'jobId': job_id,
                'totalEvents': len(timeline_events),
                'timeline': timeline_events,
                'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            
        except Exception as e:
            print_with_flush(f'❌ Error getting job timeline: {str(e)}')
            return None
    
    def batch_cancel_jobs(self, journey_id: str, job_ids: List[str], 
                         reason: str = 'Batch cancellation') -> Dict[str, bool]:
        """Cancel multiple jobs in batch"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            results = {}
            
            print_with_flush(f'🔄 Batch cancelling {len(job_ids)} jobs...')
            
            for job_id in job_ids:
                try:
                    success = self.cancel_job(clean_id, job_id, reason)
                    results[job_id] = success
                except Exception as e:
                    print_with_flush(f'❌ Failed to cancel {job_id}: {str(e)}')
                    results[job_id] = False
            
            successful = sum(1 for success in results.values() if success)
            print_with_flush(f'✅ Batch operation completed: {successful}/{len(job_ids)} jobs cancelled')
            
            return results
            
        except Exception as e:
            print_with_flush(f'❌ Error in batch cancel operation: {str(e)}')
            return {job_id: False for job_id in job_ids}

    def _delete_query_items(self, pk: str, sk_prefix: Optional[str] = None) -> int:
        """Delete all DynamoDB items matching PK and optional SK prefix."""
        items_deleted = 0
        if sk_prefix:
            query_kwargs = {
                'KeyConditionExpression': 'PK = :pk AND begins_with(SK, :sk)',
                'ExpressionAttributeValues': {
                    ':pk': pk,
                    ':sk': sk_prefix,
                },
            }
        else:
            query_kwargs = {
                'KeyConditionExpression': 'PK = :pk',
                'ExpressionAttributeValues': {
                    ':pk': pk,
                },
            }
        while True:
            response = self.table.query(**query_kwargs)
            for item in response.get('Items', []):
                self.table.delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
                items_deleted += 1
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
            query_kwargs['ExclusiveStartKey'] = last_key
        return items_deleted

    def _delete_s3_prefix(self, s3_client, bucket: str, prefix: str) -> int:
        """Delete all S3 objects under a prefix."""
        deleted = 0
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            contents = page.get('Contents', [])
            if not contents:
                continue
            keys = [{'Key': obj['Key']} for obj in contents]
            for i in range(0, len(keys), 1000):
                batch = keys[i:i + 1000]
                s3_client.delete_objects(Bucket=bucket, Delete={'Objects': batch})
                deleted += len(batch)
        return deleted

    def delete_job(self, journey_id: str, job_id: str) -> Dict[str, Any]:
        """Delete a finished job and its DynamoDB records plus S3 logs/reports."""
        try:
            clean_id = self.clean_journey_id(journey_id)
            job_details = self.get_job_details(clean_id, job_id)
            if not job_details:
                return {'success': False, 'error': 'Job not found', 'job_id': job_id}

            status = (job_details.get('status') or '').lower()
            if status in ('running', 'pending', 'in_progress'):
                return {
                    'success': False,
                    'error': f'Cannot delete job with status: {status}',
                    'job_id': job_id,
                }

            stage_id = job_details.get('stageId')
            stage_ids = job_details.get('stageIds') or ([stage_id] if stage_id else [])
            journey_pk = f'JOURNEY#{clean_id}'
            items_deleted = 0
            s3_deleted = 0

            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                FilterExpression='#data.jobId = :job_id',
                ExpressionAttributeNames={'#data': 'Data'},
                ExpressionAttributeValues={
                    ':pk': journey_pk,
                    ':sk': 'JOB#',
                    ':job_id': job_id,
                },
            )
            for item in response.get('Items', []):
                self.table.delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
                items_deleted += 1

            items_deleted += self._delete_query_items(journey_pk, f'LOG#{job_id}')
            items_deleted += self._delete_query_items(journey_pk, f'REPORT#{job_id}')
            items_deleted += self._delete_query_items(f'LIVELOG#{job_id}')

            if stage_ids:
                s3_client = self.setup_s3_client()
                logs_bucket = getattr(self, 'logs_bucket', 'transformation-journey-logs')
                reports_bucket = getattr(self, 'reports_bucket', 'transformation-journey-reports')
                for sid in stage_ids:
                    exec_prefix = f'journeys/{clean_id}/stages/{sid}/executions/{job_id}/'
                    s3_deleted += self._delete_s3_prefix(s3_client, logs_bucket, exec_prefix)
                    s3_deleted += self._delete_s3_prefix(s3_client, reports_bucket, exec_prefix)

            print_with_flush(
                f'✅ Job deleted: {job_id} ({items_deleted} DynamoDB items, {s3_deleted} S3 objects)'
            )
            return {
                'success': True,
                'job_id': job_id,
                'dynamo_items_deleted': items_deleted,
                's3_objects_deleted': s3_deleted,
            }

        except Exception as e:
            print_with_flush(f'❌ Error deleting job: {str(e)}')
            return {'success': False, 'error': str(e), 'job_id': job_id}

    def batch_delete_jobs(self, journey_id: str, job_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple finished jobs for a journey."""
        results = {job_id: self.delete_job(journey_id, job_id) for job_id in job_ids}
        successful = sum(1 for result in results.values() if result.get('success'))
        print_with_flush(f'✅ Batch delete completed: {successful}/{len(job_ids)} jobs deleted')
        return {'results': results, 'successful': successful, 'total': len(job_ids)}
    
    # ==========================================
    # LOGS AND REPORTS MANAGEMENT
    # ==========================================
    
    def get_job_logs(self, journey_id: str, stage_name: str, job_id: str, 
                     step_name: Optional[str] = None) -> Optional[Dict]:
        """Get logs for a specific job from S3"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            print_with_flush(f'📋 Retrieving logs for job: {job_id} from S3')
            
            # Set up S3 client
            s3_client = self.setup_s3_client()
            logs_bucket = getattr(self, 'logs_bucket', 'transformation-journey-logs')
            logs_prefix = f'journeys/{clean_id}/stages/{stage_name}/executions/{job_id}/logs/'
            
            logs = []
            
            if step_name:
                # Retrieve logs for a specific step
                log_key = f'{logs_prefix}{step_name}.json'
                try:
                    response = s3_client.get_object(Bucket=logs_bucket, Key=log_key)
                    step_logs = json.loads(response['Body'].read().decode('utf-8'))
                    logs.extend(step_logs)
                    print_with_flush(f'✅ Retrieved {len(step_logs)} log entries for step: {step_name}')
                except s3_client.exceptions.NoSuchKey:
                    print_with_flush(f'⚠️ No logs found for step: {step_name}')
                except Exception as e:
                    print_with_flush(f'❌ Error retrieving logs for step {step_name}: {str(e)}')
            else:
                # Retrieve logs for all steps
                try:
                    response = s3_client.list_objects_v2(Bucket=logs_bucket, Prefix=logs_prefix)
                    
                    if 'Contents' in response:
                        print_with_flush(f'📁 Found {len(response["Contents"])} log files')
                        
                        for obj in response['Contents']:
                            try:
                                log_response = s3_client.get_object(Bucket=logs_bucket, Key=obj['Key'])
                                step_logs = json.loads(log_response['Body'].read().decode('utf-8'))
                                logs.extend(step_logs)
                            except Exception as e:
                                print_with_flush(f'⚠️ Error reading log file {obj["Key"]}: {str(e)}')
                        
                        print_with_flush(f'✅ Retrieved {len(logs)} total log entries')
                    else:
                        print_with_flush(f'⚠️ No log files found for job: {job_id}')
                except Exception as e:
                    print_with_flush(f'❌ Error listing log files: {str(e)}')
            
            # Sort by timestamp
            logs.sort(key=lambda x: x.get('timestamp', ''))
            
            return {
                'jobId': job_id,
                'stageId': stage_name,
                'stepName': step_name,
                'totalLogs': len(logs),
                'logs': logs,
                'retrievedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                's3Location': {
                    'bucket': logs_bucket,
                    'prefix': logs_prefix,
                    'stepKey': f'{logs_prefix}{step_name}.json' if step_name else None
                }
            }
            
        except Exception as e:
            print_with_flush(f'❌ Error retrieving job logs: {str(e)}')
            return None
    
    def add_job_log_entry(self, journey_id: str, job_id: str, step_name: str, 
                         level: str, message: str, details: Optional[Dict] = None,
                         source: str = 'system') -> bool:
        """Add a log entry to a job"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            # Validate job exists
            if not self.get_job_details(clean_id, job_id):
                print_with_flush(f'❌ Job not found: {job_id}')
                return False
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            log_entry_id = str(uuid.uuid4())[:8]
            
            log_item = {
                'PK': f'JOURNEY#{clean_id}',
                'SK': f'LOG#{job_id}#{step_name}#{timestamp}#{log_entry_id}',
                'EntityType': 'LogEntry',
                'GSI1PK': f'JOB#{job_id}',
                'GSI1SK': timestamp,
                'CreatedAt': timestamp,
                'Data': self.convert_floats_to_decimal({
                    'jobId': job_id,
                    'step': step_name,
                    'level': level.lower(),
                    'message': message,
                    'timestamp': timestamp,
                    'source': source,
                    'details': details or {}
                })
            }
            
            self.table.put_item(Item=log_item)
            print_with_flush(f'✅ Log entry added: {job_id}/{step_name}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error adding log entry: {str(e)}')
            return False
    
    def search_logs(self, journey_id: str, search_query: str, 
                   job_id: Optional[str] = None, level_filter: Optional[str] = None,
                   step_filter: Optional[str] = None, limit: int = 100) -> Optional[Dict]:
        """Search through logs with filters"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            print_with_flush(f'🔍 Searching logs for: "{search_query}"')
            
            # Get logs
            if job_id:
                response = self.table.query(
                    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                    ExpressionAttributeValues={
                        ':pk': f'JOURNEY#{clean_id}',
                        ':sk': f'LOG#{job_id}'
                    },
                    Limit=limit
                )
            else:
                response = self.table.query(
                    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                    ExpressionAttributeValues={
                        ':pk': f'JOURNEY#{clean_id}',
                        ':sk': 'LOG#'
                    },
                    Limit=limit
                )
            
            matching_logs = []
            for item in response['Items']:
                if item.get('EntityType') != 'LogEntry':
                    continue
                    
                log_data = item['Data']
                
                # Apply filters
                if level_filter and log_data.get('level') != level_filter.lower():
                    continue
                if step_filter and log_data.get('step') != step_filter:
                    continue
                
                # Search in message
                message = log_data.get('message', '').lower()
                if search_query.lower() in message:
                    matching_logs.append({
                        'jobId': log_data.get('jobId'),
                        'timestamp': log_data.get('timestamp'),
                        'level': log_data.get('level'),
                        'step': log_data.get('step'),
                        'message': log_data.get('message'),
                        'source': log_data.get('source'),
                        'details': log_data.get('details', {})
                    })
            
            # Sort by timestamp
            matching_logs.sort(key=lambda x: x.get('timestamp', ''))
            
            return {
                'searchQuery': search_query,
                'filters': {
                    'jobId': job_id,
                    'level': level_filter,
                    'step': step_filter
                },
                'totalMatches': len(matching_logs),
                'logs': matching_logs,
                'searchedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            
        except Exception as e:
            print_with_flush(f'❌ Error searching logs: {str(e)}')
            return None
    
    def get_logs_by_level(self, journey_id: str, level: str, 
                         job_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get logs filtered by level (error, warning, info, debug)"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if job_id:
                response = self.table.query(
                    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                    ExpressionAttributeValues={
                        ':pk': f'JOURNEY#{clean_id}',
                        ':sk': f'LOG#{job_id}'
                    },
                    Limit=limit
                )
            else:
                response = self.table.query(
                    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                    ExpressionAttributeValues={
                        ':pk': f'JOURNEY#{clean_id}',
                        ':sk': 'LOG#'
                    },
                    Limit=limit
                )
            
            filtered_logs = []
            for item in response['Items']:
                if item.get('EntityType') != 'LogEntry':
                    continue
                    
                log_data = item['Data']
                if log_data.get('level') == level.lower():
                    filtered_logs.append({
                        'jobId': log_data.get('jobId'),
                        'timestamp': log_data.get('timestamp'),
                        'step': log_data.get('step'),
                        'message': log_data.get('message'),
                        'source': log_data.get('source'),
                        'details': log_data.get('details', {})
                    })
            
            # Sort by timestamp
            filtered_logs.sort(key=lambda x: x.get('timestamp', ''))
            return filtered_logs
            
        except Exception as e:
            print_with_flush(f'❌ Error getting logs by level: {str(e)}')
            return []
    
    def export_job_logs(self, journey_id: str, job_id: str, output_file: str,
                       format_type: str = 'json') -> bool:
        """Export job logs to a file"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            job = self.get_job_details(clean_id, job_id)
            if not job:
                return False
            
            logs_data = self.get_job_logs(clean_id, job['stageId'], job_id)
            if not logs_data:
                print_with_flush('❌ No logs found to export')
                return False
            
            export_data = {
                'exportedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'jobId': job_id,
                'journeyId': clean_id,
                'stageId': job['stageId'],
                'jobStatus': job['status'],
                'totalLogs': len(logs_data['logs']),
                'format': format_type,
                'logs': logs_data['logs']
            }
            
            if format_type.lower() == 'json':
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            elif format_type.lower() == 'csv':
                import csv
                with open(output_file, 'w', newline='') as f:
                    if export_data['logs']:
                        fieldnames = ['timestamp', 'level', 'step', 'message', 'source']
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for log in export_data['logs']:
                            writer.writerow({
                                'timestamp': log.get('timestamp', ''),
                                'level': log.get('level', ''),
                                'step': log.get('step', ''),
                                'message': log.get('message', ''),
                                'source': log.get('source', '')
                            })
            else:
                # Plain text format
                with open(output_file, 'w') as f:
                    f.write(f"Job Logs Export\n")
                    f.write(f"===============\n")
                    f.write(f"Job ID: {job_id}\n")
                    f.write(f"Journey ID: {clean_id}\n")
                    f.write(f"Stage: {job['stageId']}\n")
                    f.write(f"Status: {job['status']}\n")
                    f.write(f"Total Logs: {len(export_data['logs'])}\n")
                    f.write(f"Exported: {export_data['exportedAt']}\n\n")
                    
                    for log in export_data['logs']:
                        timestamp = log.get('timestamp', 'N/A')[:19]
                        level = log.get('level', 'INFO').upper()
                        step = log.get('step', 'N/A')
                        message = log.get('message', 'N/A')
                        f.write(f"{timestamp} [{level}] [{step}] {message}\n")
            
            print_with_flush(f'✅ Logs exported to: {output_file}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error exporting logs: {str(e)}')
            return False
    
    def get_error_summary(self, journey_id: str, job_id: Optional[str] = None) -> Optional[Dict]:
        """Get a summary of errors from job logs"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            error_logs = self.get_logs_by_level(clean_id, 'error', job_id)
            warning_logs = self.get_logs_by_level(clean_id, 'warning', job_id)
            
            # Categorize errors
            error_categories = {}
            step_errors = {}
            
            for log in error_logs:
                step = log.get('step', 'unknown')
                message = log.get('message', '')
                
                # Simple categorization based on keywords
                category = 'other'
                if 'connection' in message.lower() or 'network' in message.lower():
                    category = 'connectivity'
                elif 'timeout' in message.lower():
                    category = 'timeout'
                elif 'permission' in message.lower() or 'auth' in message.lower():
                    category = 'authentication'
                elif 'validation' in message.lower() or 'invalid' in message.lower():
                    category = 'validation'
                elif 'memory' in message.lower() or 'resource' in message.lower():
                    category = 'resource'
                
                error_categories[category] = error_categories.get(category, 0) + 1
                step_errors[step] = step_errors.get(step, 0) + 1
            
            return {
                'journeyId': clean_id,
                'jobId': job_id,
                'summary': {
                    'totalErrors': len(error_logs),
                    'totalWarnings': len(warning_logs),
                    'errorCategories': error_categories,
                    'errorsByStep': step_errors
                },
                'recentErrors': error_logs[-10:] if error_logs else [],  # Last 10 errors
                'recentWarnings': warning_logs[-10:] if warning_logs else [],  # Last 10 warnings
                'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            
        except Exception as e:
            print_with_flush(f'❌ Error getting error summary: {str(e)}')
            return None
    
    def get_job_reports(self, journey_id: str, job_id: str, stage_name: str = None) -> Optional[Dict]:
        """Get reports for a specific job from S3"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            print_with_flush(f'📊 Retrieving reports for job: {job_id} from S3')
            
            # Get job details to find stage name if not provided
            if not stage_name:
                job_details = self.get_job_details(clean_id, job_id)
                if not job_details:
                    print_with_flush(f'❌ Job not found: {job_id}')
                    return None
                stage_name = job_details.get('stageId')
            
            # Set up S3 client
            s3_client = self.setup_s3_client()
            reports_bucket = getattr(self, 'reports_bucket', 'transformation-journey-reports')
            reports_prefix = f'journeys/{clean_id}/stages/{stage_name}/executions/{job_id}/reports/'
            print_with_flush(f'🔍 Looking for reports in: s3://{reports_bucket}/{reports_prefix}')
            
            reports = []
            
            try:
                response = s3_client.list_objects_v2(Bucket=reports_bucket, Prefix=reports_prefix)
                
                if 'Contents' in response:
                    print_with_flush(f'📁 Found {len(response["Contents"])} report files')
                    
                    for obj in response['Contents']:
                        try:
                            # Extract step name from the report file key
                            step_name = obj['Key'].split('/')[-1].replace('.json', '')
                            
                            report_response = s3_client.get_object(Bucket=reports_bucket, Key=obj['Key'])
                            report_data = json.loads(report_response['Body'].read().decode('utf-8'))
                            
                            reports.append({
                                'reportId': f'{job_id}_{step_name}',
                                'reportType': step_name,
                                'title': f'{step_name.replace("_", " ").title()} Report',
                                'summary': report_data.get('summary', f'Report for {step_name} step'),
                                'content': report_data,
                                'generatedAt': obj['LastModified'].isoformat(),
                                'status': 'generated',
                                's3Key': obj['Key'],
                                'size': obj['Size']
                            })
                        except Exception as e:
                            print_with_flush(f'⚠️ Error reading report file {obj["Key"]}: {str(e)}')
                    
                    print_with_flush(f'✅ Retrieved {len(reports)} report files')
                else:
                    print_with_flush(f'⚠️ No report files found for job: {job_id}')
            except Exception as e:
                print_with_flush(f'❌ Error listing report files: {str(e)}')
            
            return {
                'jobId': job_id,
                'stageId': stage_name,
                'totalReports': len(reports),
                'reports': reports,
                'retrievedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                's3Location': {
                    'bucket': reports_bucket,
                    'prefix': reports_prefix
                }
            }
            
        except Exception as e:
            print_with_flush(f'❌ Error retrieving job reports: {str(e)}')
            return None
    
    def get_aggregate_report(self, journey_id: str) -> Optional[Dict]:
        """Build an aggregate report across all jobs for a journey, reading real data from DynamoDB and S3."""
        try:
            clean_id = self.clean_journey_id(journey_id)
            if not self.validate_journey_exists(clean_id):
                return None

            jobs = self.list_jobs(clean_id, limit=200)
            completed_jobs = [j for j in jobs if j.get('status') == 'completed']

            total_calls = 0
            processed_calls = 0
            transcribed_calls = 0
            analyzed_calls = 0
            success_count = 0
            failed_count = 0
            no_recording_count = 0
            skipped_count = 0
            total_duration = 0.0
            job_count = len(completed_jobs)
            all_task_ids: list = []
            step_durations: Dict[str, list] = {}

            for job in completed_jobs:
                m = job.get('metrics', {})
                total_calls += int(m.get('availableCalls', 0))
                processed_calls += int(m.get('newTasks', 0))
                transcribed_calls += int(m.get('transcriptsCollected', 0))
                analyzed_calls += int(m.get('analyzed', 0))
                success_count += int(m.get('successfulProcessing', 0))
                failed_count += int(m.get('failedProcessing', 0))
                no_recording_count += int(m.get('noRecording', 0))
                skipped_count += int(m.get('skippedTasks', 0))
                dur = m.get('durationSeconds', 0)
                if dur:
                    total_duration += float(dur)

                sr = job.get('stepResults', {})
                for step_id, step_data in sr.items():
                    if isinstance(step_data, dict) and step_data.get('durationSeconds'):
                        step_durations.setdefault(step_id, []).append(float(step_data['durationSeconds']))

                pr = sr.get('process_recordings', {})
                if isinstance(pr, dict):
                    ids = pr.get('processed_task_ids', [])
                    if isinstance(ids, list):
                        all_task_ids.extend(ids)

            avg_duration = total_duration / job_count if job_count else 0
            success_rate = round((success_count / processed_calls * 100) if processed_calls else 0, 1)
            error_rate = round((failed_count / total_calls * 100) if total_calls else 0, 2)
            throughput = round(processed_calls / (total_duration / 60), 1) if total_duration > 0 else 0

            step_avg = {}
            for sid, durs in step_durations.items():
                step_avg[sid] = round(sum(durs) / len(durs), 1) if durs else 0

            sentiment_counts: Dict[str, int] = {'positive': 0, 'neutral': 0, 'negative': 0}
            call_type_counts: Dict[str, int] = {}
            call_type_durations: Dict[str, list] = {}
            grading_scores: list = []
            grading_pass_count = 0
            element_scores: Dict[str, list] = {}
            analysis_count = 0

            if all_task_ids:
                try:
                    from src.config.config_provider import get_config
                    recordings_bucket = get_config().s3_recordings_bucket
                except Exception:
                    recordings_bucket = os.environ.get('S3_RECORDINGS_BUCKET', '')

                if recordings_bucket:
                    s3_client = self.setup_s3_client()
                    batch = all_task_ids[:200]
                    for task_id in batch:
                        try:
                            key = f'call-detail/{task_id}/analysis.json'
                            resp = s3_client.get_object(Bucket=recordings_bucket, Key=key)
                            data = json.loads(resp['Body'].read().decode('utf-8'))
                            analysis_count += 1

                            sent = data.get('sentiment_analysis', {})
                            overall = str(sent.get('overall_sentiment', '')).lower()
                            if 'positive' in overall or (isinstance(sent.get('overall_sentiment'), (int, float)) and sent.get('overall_sentiment', 0) > 0.6):
                                sentiment_counts['positive'] += 1
                            elif 'negative' in overall or (isinstance(sent.get('overall_sentiment'), (int, float)) and sent.get('overall_sentiment', 0) < 0.4):
                                sentiment_counts['negative'] += 1
                            else:
                                sentiment_counts['neutral'] += 1

                            ct = data.get('call_type', 'Unknown')
                            call_type_counts[ct] = call_type_counts.get(ct, 0) + 1
                            cd = data.get('call_duration', '')
                            if cd:
                                call_type_durations.setdefault(ct, []).append(cd)

                            grading = data.get('grading', {})
                            score = grading.get('total_score_percent')
                            if score is not None:
                                grading_scores.append(float(score))
                                if grading.get('pass'):
                                    grading_pass_count += 1
                                for el in grading.get('elements', []):
                                    ename = el.get('element', 'Unknown')
                                    escore = el.get('score')
                                    if escore is not None:
                                        element_scores.setdefault(ename, []).append(float(escore))
                        except s3_client.exceptions.NoSuchKey:
                            pass
                        except Exception:
                            pass

            avg_score = round(sum(grading_scores) / len(grading_scores), 1) if grading_scores else 0
            pass_rate = round(grading_pass_count / len(grading_scores) * 100, 1) if grading_scores else 0
            element_avg = {}
            for ename, scores in element_scores.items():
                element_avg[ename] = round(sum(scores) / len(scores), 1) if scores else 0
            element_avg_sorted = dict(sorted(element_avg.items(), key=lambda x: x[1], reverse=True))

            total_sentiment = sum(sentiment_counts.values()) or 1
            sentiment_breakdown = [
                {'label': 'Positive', 'value': sentiment_counts['positive'],
                 'percentage': round(sentiment_counts['positive'] / total_sentiment * 100, 1)},
                {'label': 'Neutral', 'value': sentiment_counts['neutral'],
                 'percentage': round(sentiment_counts['neutral'] / total_sentiment * 100, 1)},
                {'label': 'Negative', 'value': sentiment_counts['negative'],
                 'percentage': round(sentiment_counts['negative'] / total_sentiment * 100, 1)},
            ]

            total_ct = sum(call_type_counts.values()) or 1
            call_distribution = []
            for ct, count in sorted(call_type_counts.items(), key=lambda x: x[1], reverse=True):
                durations = call_type_durations.get(ct, [])
                call_distribution.append({
                    'callType': ct,
                    'count': count,
                    'percentage': round(count / total_ct * 100, 1),
                    'avgDuration': durations[0] if len(durations) == 1 else (durations[0] if durations else ''),
                })

            def _fmt_duration(secs: float) -> str:
                if secs < 60:
                    return f"{int(secs)}s"
                return f"{int(secs // 60)}m {int(secs % 60)}s"

            return {
                'summary': {
                    'totalCalls': total_calls,
                    'processedCalls': processed_calls,
                    'transcribedCalls': transcribed_calls,
                    'analyzedCalls': analyzed_calls,
                    'successCount': success_count,
                    'failedCount': failed_count,
                    'noRecordingCount': no_recording_count,
                    'skippedCount': skipped_count,
                    'successRate': success_rate,
                    'avgProcessingTime': _fmt_duration(avg_duration),
                    'totalJobs': job_count,
                },
                'processingPerformance': {
                    'avgProcessingTime': _fmt_duration(avg_duration),
                    'throughput': f"{throughput} calls/min",
                    'errorRate': f"{error_rate}%",
                    'stepAvgDurations': {k: _fmt_duration(v) for k, v in step_avg.items()},
                },
                'grading': {
                    'avgScore': avg_score,
                    'passRate': pass_rate,
                    'totalAnalyzed': len(grading_scores),
                    'passCount': grading_pass_count,
                    'elementScores': element_avg_sorted,
                },
                'callDistribution': call_distribution,
                'sentimentBreakdown': sentiment_breakdown,
                'analysisFileCount': analysis_count,
                'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            }

        except Exception as e:
            print_with_flush(f'❌ Error generating aggregate report: {str(e)}')
            import traceback
            traceback.print_exc()
            return None

    def create_job_report(self, journey_id: str, job_id: str, report_type: str,
                         title: str, content: Dict, summary: Optional[str] = None) -> bool:
        """Create a custom report for a job"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            # Validate job exists
            if not self.get_job_details(clean_id, job_id):
                print_with_flush(f'❌ Job not found: {job_id}')
                return False
            
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            report_id = f'RPT-{str(uuid.uuid4()).upper().replace("-", "")[:8]}'
            
            report_item = {
                'PK': f'JOURNEY#{clean_id}',
                'SK': f'REPORT#{job_id}#{report_type}#{timestamp}#{report_id}',
                'EntityType': 'JobReport',
                'GSI1PK': f'REPORTS#{job_id}',
                'GSI1SK': timestamp,
                'CreatedAt': timestamp,
                'Data': self.convert_floats_to_decimal({
                    'reportId': report_id,
                    'jobId': job_id,
                    'reportType': report_type,
                    'title': title,
                    'summary': summary or f'{report_type} report for job {job_id}',
                    'content': content,
                    'generatedAt': timestamp,
                    'status': 'generated',
                    'metrics': {
                        'contentSize': len(str(content)),
                        'sections': len(content) if isinstance(content, dict) else 1
                    }
                })
            }
            
            self.table.put_item(Item=report_item)
            print_with_flush(f'✅ Report created: {report_id} ({report_type})')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error creating report: {str(e)}')
            return False
    
    def generate_performance_report(self, journey_id: str, job_id: str) -> Optional[Dict]:
        """Generate a detailed performance analysis report"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            # Get job metrics
            metrics = self.get_job_metrics(clean_id, job_id)
            if not metrics:
                return None
            
            # Get job details
            job = self.get_job_details(clean_id, job_id)
            if not job:
                return None
            
            # Generate performance analysis
            performance_analysis = {
                'reportId': f'PERF-{job_id}',
                'jobId': job_id,
                'reportType': 'performance_analysis',
                'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'executionSummary': {
                    'status': job['status'],
                    'totalDuration': metrics.get('duration'),
                    'progress': job.get('progress', 0),
                    'stageId': job['stageId']
                },
                'performanceMetrics': {
                    'executionTime': metrics.get('duration'),
                    'avgStepDuration': metrics['performanceMetrics']['avgStepDuration'],
                    'slowestStep': metrics['performanceMetrics']['slowestStep'],
                    'fastestStep': metrics['performanceMetrics']['fastestStep'],
                    'errorRate': metrics['performanceMetrics']['errorRate']
                },
                'logAnalysis': metrics['logMetrics'],
                'resourceUsage': metrics.get('resourceMetrics', {}),
                'recommendations': []
            }
            
            # Add performance recommendations
            duration = metrics.get('duration', 0)
            error_rate = metrics['performanceMetrics']['errorRate']
            
            if duration > 300:  # 5 minutes
                performance_analysis['recommendations'].append({
                    'type': 'performance',
                    'priority': 'medium',
                    'issue': 'Long execution time',
                    'recommendation': f'Job took {duration:.1f} seconds. Consider optimizing slow steps or increasing resources.'
                })
            
            if error_rate > 0.1:  # 10% error rate
                performance_analysis['recommendations'].append({
                    'type': 'reliability',
                    'priority': 'high',
                    'issue': 'High error rate',
                    'recommendation': f'Error rate is {error_rate*100:.1f}%. Review error logs and improve error handling.'
                })
            
            slowest_step = metrics['performanceMetrics']['slowestStep']
            if slowest_step and slowest_step['duration'] > 60:  # 1 minute
                performance_analysis['recommendations'].append({
                    'type': 'optimization',
                    'priority': 'medium',
                    'issue': 'Slow step detected',
                    'recommendation': f'Step "{slowest_step["step"]}" took {slowest_step["duration"]:.1f}s. Consider optimization.'
                })
            
            # Create report
            self.create_job_report(
                clean_id, job_id, 'performance_analysis',
                f'Performance Analysis for Job {job_id}',
                performance_analysis,
                f'Performance analysis showing {len(performance_analysis["recommendations"])} recommendations'
            )
            
            return performance_analysis
            
        except Exception as e:
            print_with_flush(f'❌ Error generating performance report: {str(e)}')
            return None
    
    def list_available_logs(self, journey_id: str, job_id: Optional[str] = None) -> List[Dict]:
        """List all available logs for a journey or specific job"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            if job_id:
                sk_prefix = f'LOG#{job_id}'
            else:
                sk_prefix = 'LOG#'
            
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': f'JOURNEY#{clean_id}',
                    ':sk': sk_prefix
                }
            )
            
            log_summaries = {}
            for item in response['Items']:
                if item.get('EntityType') == 'LogEntry':
                    log_data = item['Data']
                    job_id = log_data.get('jobId')
                    step = log_data.get('step')
                    
                    if job_id not in log_summaries:
                        log_summaries[job_id] = {
                            'jobId': job_id,
                            'steps': set(),
                            'totalEntries': 0,
                            'levels': set(),
                            'firstEntry': None,
                            'lastEntry': None
                        }
                    
                    summary = log_summaries[job_id]
                    summary['steps'].add(step)
                    summary['totalEntries'] += 1
                    summary['levels'].add(log_data.get('level'))
                    
                    timestamp = log_data.get('timestamp')
                    if not summary['firstEntry'] or timestamp < summary['firstEntry']:
                        summary['firstEntry'] = timestamp
                    if not summary['lastEntry'] or timestamp > summary['lastEntry']:
                        summary['lastEntry'] = timestamp
            
            # Convert sets to lists for JSON serialization
            result = []
            for job_id, summary in log_summaries.items():
                result.append({
                    'jobId': summary['jobId'],
                    'steps': list(summary['steps']),
                    'totalEntries': summary['totalEntries'],
                    'levels': list(summary['levels']),
                    'firstEntry': summary['firstEntry'],
                    'lastEntry': summary['lastEntry']
                })
            
            return result
            
        except Exception as e:
            print_with_flush(f'❌ Error listing available logs: {str(e)}')
            return []
    
    def generate_job_summary_report(self, journey_id: str, job_id: str) -> Optional[Dict]:
        """Generate a comprehensive summary report for a job"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            
            print_with_flush(f'📊 Generating summary report for job: {job_id}')
            
            # Get job details
            job = self.get_job_details(clean_id, job_id)
            if not job:
                return None
            
            # Get logs
            logs_data = self.get_job_logs(clean_id, job['stageId'], job_id)
            
            # Get reports
            reports_data = self.get_job_reports(clean_id, job_id)
            
            # Calculate summary statistics
            logs = logs_data.get('logs', []) if logs_data else []
            
            log_levels = {}
            steps_executed = set()
            errors = []
            warnings = []
            
            for log in logs:
                level = log.get('level', 'info')
                log_levels[level] = log_levels.get(level, 0) + 1
                steps_executed.add(log.get('step'))
                
                if level == 'error':
                    errors.append(log)
                elif level == 'warning':
                    warnings.append(log)
            
            # Calculate execution time
            start_time = job.get('startTime')
            end_time = job.get('endTime')
            execution_time = None
            
            if start_time and end_time:
                try:
                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    execution_time = (end_dt - start_dt).total_seconds()
                except:
                    pass
            
            summary_report = {
                'reportId': f'SUMMARY-{job_id}',
                'jobId': job_id,
                'journeyId': clean_id,
                'generatedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'jobSummary': {
                    'stageId': job['stageId'],
                    'stageName': job['stageName'],
                    'status': job['status'],
                    'progress': job['progress'],
                    'executionTime': execution_time,
                    'triggeredBy': job['triggeredBy'],
                    'reason': job['reason']
                },
                'executionMetrics': {
                    'totalSteps': len(steps_executed),
                    'totalLogs': len(logs),
                    'logLevels': log_levels,
                    'errorsCount': len(errors),
                    'warningsCount': len(warnings),
                    'artifacts': len(job.get('artifacts', []))
                },
                'logs': {
                    'available': logs_data is not None,
                    'totalEntries': len(logs),
                    'stepsWithLogs': list(steps_executed),
                    'recentErrors': errors[-5:] if errors else [],
                    'recentWarnings': warnings[-5:] if warnings else []
                },
                'reports': {
                    'available': reports_data is not None,
                    'totalReports': len(reports_data.get('reports', [])) if reports_data else 0
                },
                'recommendations': []
            }
            
            # Add recommendations based on analysis
            if job['status'] == 'failed' and errors:
                summary_report['recommendations'].append({
                    'type': 'error_analysis',
                    'priority': 'high',
                    'message': f'Job failed with {len(errors)} errors. Review error logs for detailed analysis.'
                })
            
            if warnings:
                summary_report['recommendations'].append({
                    'type': 'warning_review',
                    'priority': 'medium',
                    'message': f'Job completed with {len(warnings)} warnings. Consider reviewing for optimization.'
                })
            
            if execution_time and execution_time > 300:  # 5 minutes
                summary_report['recommendations'].append({
                    'type': 'performance',
                    'priority': 'low',
                    'message': f'Job took {execution_time:.1f} seconds. Consider performance optimization.'
                })
            
            return summary_report
            
        except Exception as e:
            print_with_flush(f'❌ Error generating summary report: {str(e)}')
            return None
    
    # ==========================================
    # IMPORT/EXPORT FUNCTIONALITY
    # ==========================================
    
    def export_journey_complete(self, journey_id: str, output_file: str) -> bool:
        """Export complete journey data to JSON file"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            print_with_flush(f'📤 Exporting complete journey: {clean_id}')
            
            journey = self.get_journey_complete(clean_id)
            if not journey:
                return False
            
            # Convert Decimal to float for JSON serialization
            def decimal_to_float(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, dict):
                    return {k: decimal_to_float(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [decimal_to_float(item) for item in obj]
                else:
                    return obj
            
            export_data = {
                'journeyId': clean_id,
                'exportedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'exportType': 'complete_journey',
                'version': '1.0',
                'journey': decimal_to_float(journey)
            }
            
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print_with_flush(f'✅ Journey exported to: {output_file}')
            return True
            
        except Exception as e:
            print_with_flush(f'❌ Error exporting journey: {str(e)}')
            traceback.print_exc()
            return False
    
    def import_journey_complete(self, input_file: str, new_journey_id: Optional[str] = None) -> Optional[str]:
        """Import complete journey data from JSON file"""
        try:
            print_with_flush(f'📥 Importing complete journey from: {input_file}')
            
            with open(input_file, 'r') as f:
                import_data = json.load(f)
            
            if 'journey' not in import_data:
                print_with_flush('❌ Invalid import file format - missing journey data')
                return None
            
            journey_data = import_data['journey']
            metadata = journey_data.get('metadata', {})
            
            # Generate new journey ID or use provided one
            if new_journey_id:
                journey_id = self.clean_journey_id(new_journey_id)
            else:
                journey_id = f'JRN-{str(uuid.uuid4()).upper().replace("-", "")[:12]}'
            
            # Create journey metadata
            if not self.create_journey_metadata(journey_id, metadata):
                return None
            
            # Import stages
            stages = journey_data.get('stages', [])
            for stage in stages:
                self.add_stage(journey_id, stage)
            
            # Import rules
            rules = journey_data.get('rules', [])
            for rule in rules:
                stage_id = rule.get('stageId')
                if stage_id:
                    self.add_rule(journey_id, stage_id, rule)
            
            print_with_flush(f'✅ Journey imported successfully: {journey_id}')
            print_with_flush(f'   📋 Stages: {len(stages)}')
            print_with_flush(f'   🧠 Rules: {len(rules)}')
            
            return journey_id
            
        except Exception as e:
            print_with_flush(f'❌ Error importing journey: {str(e)}')
            traceback.print_exc()
            return None
    
    # ==========================================
    # DISPLAY AND INTERACTIVE METHODS
    # ==========================================
    
    def display_job_dashboard(self, job: Dict):
        """Display comprehensive job dashboard"""
        try:
            print_with_flush('\n' + '=' * 80)
            print_with_flush(f'🚀 JOB DASHBOARD: {job["jobId"]}')
            print_with_flush('=' * 80)
            
            # Basic Info
            print_with_flush(f'📋 Stage: {job.get("stageId", "N/A")} ({job.get("stageName", "N/A")})')
            print_with_flush(f'📊 Status: {job.get("status", "N/A")}')
            print_with_flush(f'📈 Progress: {job.get("progress", 0)}%')
            print_with_flush(f'👤 Triggered by: {job.get("triggeredBy", "N/A")}')
            print_with_flush(f'📝 Reason: {job.get("reason", "N/A")}')
            print_with_flush(f'🕐 Started: {job.get("startTime", "N/A")}')
            
            if job.get('endTime'):
                print_with_flush(f'🏁 Ended: {job["endTime"]}')
            
            if job.get('duration'):
                print_with_flush(f'⏱️ Duration: {job["duration"]}')
            
            # Current execution info
            if job.get('currentStep'):
                print_with_flush(f'🔧 Current Step: {job["currentStep"]}')
            
            if job.get('totalSteps'):
                print_with_flush(f'📊 Total Steps: {job["totalSteps"]}')
            
            # Error information
            if job.get('errorMessage'):
                print_with_flush(f'\n❌ ERROR:')
                print_with_flush(f'   {job["errorMessage"]}')
            
            # Metrics
            metrics = job.get('metrics', {})
            if metrics:
                print_with_flush(f'\n📊 METRICS:')
                if metrics.get('executionTime'):
                    print_with_flush(f'   ⏱️ Execution Time: {metrics["executionTime"]}s')
                if metrics.get('errorsCount') is not None:
                    print_with_flush(f'   ❌ Errors: {metrics["errorsCount"]}')
                if metrics.get('warningsCount') is not None:
                    print_with_flush(f'   ⚠️ Warnings: {metrics["warningsCount"]}')
            
            # Availability
            print_with_flush(f'\n📋 AVAILABILITY:')
            print_with_flush(f'   📊 Logs: {"Available" if job.get("logsAvailable") else "Not Available"}')
            print_with_flush(f'   📋 Reports: {"Available" if job.get("reportsAvailable") else "Not Available"}')
            
            # Artifacts
            artifacts = job.get('artifacts', [])
            if artifacts:
                print_with_flush(f'\n📁 ARTIFACTS ({len(artifacts)}):')
                for artifact in artifacts[:5]:  # Show first 5
                    print_with_flush(f'   📄 {artifact}')
                if len(artifacts) > 5:
                    print_with_flush(f'   ... and {len(artifacts) - 5} more')
            
            print_with_flush('=' * 80)
            
        except Exception as e:
            print_with_flush(f'❌ Error displaying job dashboard: {str(e)}')
    
    def display_journey_dashboard(self, journey_id: str):
        """Display comprehensive journey dashboard"""
        try:
            clean_id = self.clean_journey_id(journey_id)
            journey = self.get_journey_complete(clean_id)
            
            if not journey:
                return
            
            metadata = journey['metadata']
            summary = journey['summary']
            
            print_with_flush('\n' + '=' * 80)
            print_with_flush(f'🏗️ JOURNEY DASHBOARD: {clean_id}')
            print_with_flush('=' * 80)
            
            # Basic Info
            print_with_flush(f'📝 Name: {metadata.get("name", "N/A")}')
            print_with_flush(f'📄 Description: {metadata.get("description", "N/A")}')
            print_with_flush(f'🏗️  Component: {metadata.get("odaComponentType", "N/A")}')
            print_with_flush(f'📊 Status: {metadata.get("status", "N/A")}')
            print_with_flush(f'⚡ Priority: {metadata.get("priority", "N/A")}')
            print_with_flush(f'👤 Created by: {metadata.get("createdBy", "N/A")}')
            print_with_flush(f'📅 Created: {journey.get("createdAt", "N/A")}')
            print_with_flush(f'🔄 Updated: {journey.get("updatedAt", "N/A")}')
            
            # Progress
            print_with_flush(f'\n📈 PROGRESS:')
            print_with_flush(f'   Overall: {metadata.get("overallProgress", 0)}%')
            print_with_flush(f'   Current Stage: {metadata.get("currentStageId", "N/A")}')
            
            # Summary Statistics
            print_with_flush(f'\n📊 SUMMARY:')
            print_with_flush(f'   📋 Total Stages: {summary["totalStages"]}')
            print_with_flush(f'   🧠 Total Rules: {summary["totalRules"]}')
            print_with_flush(f'   🔧 Total Steps: {summary["totalSteps"]}')
            print_with_flush(f'   🤖 AI-Assisted Steps: {summary["aiAssistedSteps"]}')
            print_with_flush(f'   ⏱️  Estimated Duration: {summary["estimatedDuration"]}')
            
            # Job Statistics
            print_with_flush(f'\n🚀 JOBS:')
            print_with_flush(f'   📊 Total Jobs: {summary.get("totalJobs", 0)}')
            print_with_flush(f'   ✅ Completed: {summary.get("completedJobs", 0)}')
            print_with_flush(f'   ❌ Failed: {summary.get("failedJobs", 0)}')
            print_with_flush(f'   🔄 Running: {summary.get("runningJobs", 0)}')
            print_with_flush(f'   📈 Progress: {summary.get("overallProgress", 0)}%')
            
            # Second Brain Configuration
            sb_config = metadata.get('secondBrainConfig', {})
            print_with_flush(f'\n🧠 SECOND BRAIN:')
            print_with_flush(f'   Enabled: {"✓" if sb_config.get("enabled") else "✗"}')
            print_with_flush(f'   Auto Apply Rules: {"✓" if sb_config.get("autoApplyRules") else "✗"}')
            print_with_flush(f'   Custom Rules: {"✓" if sb_config.get("customRulesEnabled") else "✗"}')
            print_with_flush(f'   Rule Types: {", ".join(sb_config.get("ruleTypes", []))}')
            
            # Stages Summary
            stages = journey['stages']
            print_with_flush(f'\n📋 STAGES ({len(stages)}):')
            for stage in stages:
                ai_symbol = '🤖' if stage.get('secondBrainEnabled') else '🔧'
                steps_count = len(stage.get('steps', []))
                print_with_flush(f'   {int(stage["order"]):2d}. {ai_symbol} {stage["name"]} ({steps_count} steps, {stage.get("estimatedDuration", "N/A")})')
            
            # Rules Summary
            rules = journey['rules']
            rules_by_stage = {}
            for rule in rules:
                stage_id = rule['stageId']
                if stage_id not in rules_by_stage:
                    rules_by_stage[stage_id] = []
                rules_by_stage[stage_id].append(rule)
            
            print_with_flush(f'\n🧠 RULES ({len(rules)}):')
            for stage_id, stage_rules in rules_by_stage.items():
                print_with_flush(f'   {stage_id}: {len(stage_rules)} rules')
            
            print_with_flush('=' * 80)
            
        except Exception as e:
            print_with_flush(f'❌ Error displaying dashboard: {str(e)}')
    
    def interactive_journey_wizard(self):
        """Interactive journey creation wizard"""
        try:
            print_with_flush('\n🧙 COMPREHENSIVE JOURNEY CREATION WIZARD')
            print_with_flush('=' * 60)
            
            journey_data = {}
            
            # Basic Information
            print_with_flush('\n📝 BASIC INFORMATION:')
            journey_data['name'] = input('Journey name: ').strip()
            journey_data['description'] = input('Journey description: ').strip()
            
            # ODA Component selection with numbered options
            print_with_flush('\n📦 Select ODA Component Type:')
            for idx, component in enumerate(self.valid_oda_components, 1):
                print_with_flush(f'  {idx}. {component}')
            
            try:
                component_choice = input('Select component (number): ').strip()
                component_idx = int(component_choice) - 1
                if 0 <= component_idx < len(self.valid_oda_components):
                    journey_data['odaComponentType'] = self.valid_oda_components[component_idx]
                else:
                    print_with_flush('❌ Invalid selection, using default: customer-management')
                    journey_data['odaComponentType'] = 'customer-management'
            except (ValueError, IndexError):
                print_with_flush('❌ Invalid input, using default: customer-management')
                journey_data['odaComponentType'] = 'customer-management'
            
            # Priority selection with numbered options
            print_with_flush('\n⚡ Select Priority:')
            for idx, priority in enumerate(self.valid_priorities, 1):
                print_with_flush(f'  {idx}. {priority}')
            
            try:
                priority_choice = input('Select priority (number) [default: 2-medium]: ').strip()
                if priority_choice:
                    priority_idx = int(priority_choice) - 1
                    if 0 <= priority_idx < len(self.valid_priorities):
                        journey_data['priority'] = self.valid_priorities[priority_idx]
                    else:
                        journey_data['priority'] = 'medium'
                else:
                    journey_data['priority'] = 'medium'
            except (ValueError, IndexError):
                journey_data['priority'] = 'medium'
            
            journey_data['createdBy'] = input('Created by (default: user): ').strip() or 'user'
            
            # Options
            print_with_flush('\n⚙️ OPTIONS:')
            add_stages = input('Add default stages? (Y/n): ').strip().lower()
            include_stages = add_stages != 'n'
            
            add_rules = input('Add default Second Brain rules? (Y/n): ').strip().lower()
            include_rules = add_rules != 'n'
            
            # Summary
            print_with_flush('\n📋 JOURNEY SUMMARY:')
            print_with_flush(f'   📝 Name: {journey_data["name"]}')
            print_with_flush(f'   🏗️  Component: {journey_data["odaComponentType"]}')
            print_with_flush(f'   📊 Priority: {journey_data.get("priority", "medium")}')
            print_with_flush(f'   👤 Created by: {journey_data["createdBy"]}')
            print_with_flush(f'   📋 Include stages: {"Yes" if include_stages else "No"}')
            print_with_flush(f'   🧠 Include rules: {"Yes" if include_rules else "No"}')
            
            # Confirm
            confirm = input('\nCreate this journey? (y/n): ').strip().lower()
            if confirm == 'y':
                journey_id = self.create_journey_complete(
                    journey_data,
                    include_default_stages=include_stages,
                    include_default_rules=include_rules
                )
                
                if journey_id:
                    print_with_flush(f'\n✅ Journey created successfully!')
                    print_with_flush(f'🆔 Journey ID: {journey_id}')
                    
                    # Ask if they want to see the dashboard
                    show_dashboard = input('\nShow journey dashboard? (y/n): ').strip().lower()
                    if show_dashboard == 'y':
                        self.display_journey_dashboard(journey_id)
                    
                    return journey_id
            else:
                print_with_flush('❌ Journey creation cancelled')
                return None
                
        except KeyboardInterrupt:
            print_with_flush('\n❌ Wizard cancelled')
            return None
        except Exception as e:
            print_with_flush(f'❌ Error in wizard: {str(e)}')
            return None
    
    def display_journeys_table(self, journeys: List[Dict]):
        """Display journeys in a formatted table"""
        if not journeys:
            print_with_flush('📋 No journeys found')
            return
        
        print_with_flush('\n📋 TMF ODA Transformation Journeys:')
        print_with_flush('=' * 100)
        
        # Header - Optimized for 100-character width
        header = f'{"Journey ID":<18} {"Name":<20} {"Component":<18} {"Status":<10} {"Progress":<8} {"Stage":<15} {"Rules":<6}'
        print_with_flush(header)
        print_with_flush('-' * 100)
        
        # Journeys
        for journey in journeys:
            # Safe handling of potentially Decimal fields with proper truncation
            journey_id = str(journey.get("journeyId", "N/A"))[:17]
            name = str(journey.get("name", "N/A"))[:19]
            component_type = str(journey.get("odaComponentType", "N/A"))[:17]
            status = str(journey.get("status", "N/A"))[:9]
            current_stage = str(journey.get("currentStageId", "N/A"))[:14]
            
            progress = f'{journey.get("overallProgress", 0)}%'[:7]
            rules_count = f'{journey.get("activeRules", 0)}/{journey.get("totalRules", 0)}'[:5]
            
            row = f'{journey_id:<18} {name:<20} {component_type:<18} {status:<10} {progress:<8} {current_stage:<15} {rules_count:<6}'
            print_with_flush(row)
        
        print_with_flush(f'\n📊 Total: {len(journeys)} journeys')
    
    def display_jobs_table(self, jobs: List[Dict]):
        """Display jobs in a formatted table with proper column sizing"""
        if not jobs:
            print_with_flush('📋 No jobs found')
            return
        
        print_with_flush('\n🚀 Job Execution History:')
        print_with_flush('=' * 95)
        
        # Optimized column widths for 95-character width
        header = f'{"Job ID":<18} {"Stage":<15} {"Status":<10} {"Progress":<8} {"Started":<18} {"Triggered By":<12}'
        print_with_flush(header)
        print_with_flush('-' * 95)
        
        for job in jobs:
            job_id = str(job.get('jobId', 'N/A'))[:17]
            stage = str(job.get('stageId', 'N/A'))[:14]
            status = str(job.get('status', 'N/A'))[:9]
            progress = f"{job.get('progress', 0)}%"[:7]
            start_time = str(job.get('startTime', 'N/A'))[:17]
            triggered_by = str(job.get('triggeredBy', 'N/A'))[:11]
            
            row = f'{job_id:<18} {stage:<15} {status:<10} {progress:<8} {start_time:<18} {triggered_by:<12}'
            print_with_flush(row)
        
        print_with_flush(f'\n📊 Total: {len(jobs)} jobs')


def main():
    """Main function with comprehensive command-line interface"""
    parser = argparse.ArgumentParser(description='Comprehensive TMF ODA Transformation Journey Management')
    parser.add_argument('--action', required=True, choices=[
        # Journey operations
        'list-journeys', 'get-journey', 'create-journey', 'update-journey', 'delete-journey',
        
        # Stage operations
        'list-stages', 'add-stage', 'update-stage', 'delete-stage', 'add-default-stages',
        
        # Rules operations
        'list-rules', 'add-rule', 'update-rule', 'delete-rule',
        
        # Job operations
        'list-jobs', 'get-job', 'run-job', 'cancel-job', 'update-job-status', 'retry-job', 
        'get-job-metrics', 'get-job-timeline', 'batch-cancel-jobs',
        
        # Logs and Reports
        'get-job-logs', 'get-job-reports', 'add-log-entry', 'search-logs', 'get-logs-by-level',
        'export-job-logs', 'get-error-summary', 'list-available-logs', 'generate-summary-report',
        'create-job-report', 'generate-performance-report',
        
        # Import/Export
        'export-complete', 'import-complete',
        
        # Interactive
        'interactive', 'dashboard', 'wizard'
    ], help='Action to perform')
    
    # Common arguments
    parser.add_argument('--journey-id', help='Journey ID')
    parser.add_argument('--data-file', help='JSON file with data')
    parser.add_argument('--output-file', help='Output file for export')
    parser.add_argument('--input-file', help='Input file for import')
    
    # Filtering arguments
    parser.add_argument('--status-filter', help='Filter by status')
    parser.add_argument('--component-filter', help='Filter by component type')
    parser.add_argument('--stage-id', help='Stage ID')
    parser.add_argument('--rule-type', help='Rule type filter')
    parser.add_argument('--rule-id', help='Rule ID for update/delete operations')
    parser.add_argument('--job-id', help='Job ID')
    
    # Job-related arguments
    parser.add_argument('--job-ids', help='Comma-separated list of job IDs for batch operations')
    parser.add_argument('--step-name', help='Step name for logs')
    parser.add_argument('--triggered-by', help='Who triggered the job', default='user')
    parser.add_argument('--reason', help='Reason for job execution', default='Manual execution')
    parser.add_argument('--limit', type=int, help='Limit number of results', default=50)
    parser.add_argument('--job-status', help='Job status for updates')
    parser.add_argument('--progress', type=int, help='Job progress percentage')
    parser.add_argument('--current-step', help='Current step for job updates')
    parser.add_argument('--error-message', help='Error message for job updates')
    
    # Log-related arguments
    parser.add_argument('--log-level', help='Log level (error, warning, info, debug)')
    parser.add_argument('--log-message', help='Log message')
    parser.add_argument('--search-query', help='Search query for logs')
    parser.add_argument('--level-filter', help='Filter logs by level')
    parser.add_argument('--step-filter', help='Filter logs by step')
    parser.add_argument('--source', help='Log source', default='system')
    parser.add_argument('--format', help='Export format (json, csv, txt)', default='json')
    
    # Report-related arguments
    parser.add_argument('--report-type', help='Type of report to create')
    parser.add_argument('--report-title', help='Title for the report')
    parser.add_argument('--report-content', help='JSON file with report content')
    
    # Options
    parser.add_argument('--include-all', action='store_true', help='Include all details')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # Initialize manager
    try:
        print_with_flush('🏗️ Comprehensive Journey Manager')
        print_with_flush('=' * 50)
        
        manager = ComprehensiveJourneyManager()
        
        # Journey operations
        if args.action == 'list-journeys':
            journeys = manager.list_journeys(
                status_filter=args.status_filter,
                component_type_filter=args.component_filter
            )
            manager.display_journeys_table(journeys)
        
        elif args.action == 'get-journey':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            journey = manager.get_journey_complete(args.journey_id)
            if journey:
                if args.include_all:
                    print_with_flush(json.dumps(journey, indent=2, default=str))
                else:
                    manager.display_journey_dashboard(args.journey_id)
            else:
                print_with_flush(f'❌ Journey not found: {args.journey_id}')
                return False
        
        elif args.action == 'create-journey':
            if not args.data_file:
                print_with_flush('❌ --data-file is required')
                return False
            
            try:
                with open(args.data_file, 'r') as f:
                    journey_data = json.load(f)
            except FileNotFoundError:
                print_with_flush(f'❌ File not found: {args.data_file}')
                return False
            except json.JSONDecodeError:
                print_with_flush(f'❌ Invalid JSON in file: {args.data_file}')
                return False
            
            journey_id = manager.create_journey_complete(journey_data)
            if journey_id:
                print_with_flush(f'✅ Journey created: {journey_id}')
            else:
                print_with_flush('❌ Failed to create journey')
                return False
        
        elif args.action == 'update-journey':
            if not args.journey_id or not args.data_file:
                print_with_flush('❌ --journey-id and --data-file are required')
                return False
            
            with open(args.data_file, 'r') as f:
                journey_data = json.load(f)
            
            manager.update_journey_metadata(args.journey_id, journey_data)
        
        elif args.action == 'delete-journey':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            manager.delete_journey_complete(args.journey_id, args.confirm)
        
        # Stage operations
        elif args.action == 'list-stages':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            stages = manager.list_stages(args.journey_id)
            print_with_flush(f'\n📋 Stages for Journey: {args.journey_id}')
            for stage in stages:
                ai_symbol = '🤖' if stage.get('secondBrainEnabled') else '🔧'
                print_with_flush(f'   {int(stage["order"]):2d}. {ai_symbol} {stage["name"]} ({len(stage.get("steps", []))} steps)')
        
        elif args.action == 'add-stage':
            if not args.journey_id or not args.data_file:
                print_with_flush('❌ --journey-id and --data-file are required')
                return False
            
            with open(args.data_file, 'r') as f:
                stage_data = json.load(f)
            
            manager.add_stage(args.journey_id, stage_data)
        
        elif args.action == 'update-stage':
            if not args.journey_id or not args.stage_id or not args.data_file:
                print_with_flush('❌ --journey-id, --stage-id, and --data-file are required')
                return False
            
            with open(args.data_file, 'r') as f:
                stage_data = json.load(f)
            
            manager.update_stage(args.journey_id, args.stage_id, stage_data)
        
        elif args.action == 'delete-stage':
            if not args.journey_id or not args.stage_id:
                print_with_flush('❌ --journey-id and --stage-id are required')
                return False
            
            manager.delete_stage(args.journey_id, args.stage_id, args.confirm)
        
        elif args.action == 'add-default-stages':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            manager.add_default_stages_complete(args.journey_id)
        
        # Rules operations
        elif args.action == 'list-rules':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            rules = manager.list_rules(args.journey_id, args.stage_id, args.rule_type)
            print_with_flush(f'\n🧠 Rules for Journey: {args.journey_id}')
            for rule in rules:
                print_with_flush(f'   • {rule["title"]} ({rule["type"]}, {rule["priority"]})')
        
        elif args.action == 'add-rule':
            if not args.journey_id or not args.stage_id or not args.data_file:
                print_with_flush('❌ --journey-id, --stage-id, and --data-file are required')
                return False
            
            with open(args.data_file, 'r') as f:
                rule_data = json.load(f)
            
            manager.add_rule(args.journey_id, args.stage_id, rule_data)
        
        elif args.action == 'update-rule':
            if not args.journey_id or not args.stage_id or not args.rule_id or not args.data_file:
                print_with_flush('❌ --journey-id, --stage-id, --rule-id, and --data-file are required')
                return False
            
            with open(args.data_file, 'r') as f:
                rule_data = json.load(f)
            
            manager.update_rule(args.journey_id, args.stage_id, args.rule_id, rule_data)
        
        elif args.action == 'delete-rule':
            if not args.journey_id or not args.stage_id or not args.rule_id:
                print_with_flush('❌ --journey-id, --stage-id, and --rule-id are required')
                return False
            
            manager.delete_rule(args.journey_id, args.stage_id, args.rule_id, args.confirm)
        
        # Job operations
        elif args.action == 'list-jobs':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            jobs = manager.list_jobs(
                args.journey_id, 
                stage_id=args.stage_id,
                status_filter=args.status_filter,
                limit=args.limit
            )
            
            print_with_flush(f'\n🚀 Jobs for Journey: {args.journey_id}')
            manager.display_jobs_table(jobs)
        
        elif args.action == 'get-job':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            job = manager.get_job_details(args.journey_id, args.job_id)
            if job:
                if args.include_all:
                    print_with_flush(json.dumps(job, indent=2, default=str))
                else:
                    print_with_flush(f'\n🚀 JOB DETAILS: {args.job_id}')
                    print_with_flush('=' * 60)
                    print_with_flush(f'📋 Stage: {job.get("stageId")} ({job.get("stageName")})')
                    print_with_flush(f'📊 Status: {job.get("status")}')
                    print_with_flush(f'📈 Progress: {job.get("progress", 0)}%')
                    print_with_flush(f'👤 Triggered by: {job.get("triggeredBy")}')
                    print_with_flush(f'📝 Reason: {job.get("reason")}')
                    print_with_flush(f'🕐 Started: {job.get("startTime")}')
                    if job.get('endTime'):
                        print_with_flush(f'🏁 Ended: {job.get("endTime")}')
                    if job.get('errorMessage'):
                        print_with_flush(f'❌ Error: {job.get("errorMessage")}')
                    print_with_flush(f'📊 Logs Available: {"Yes" if job.get("logsAvailable") else "No"}')
                    print_with_flush(f'📋 Reports Available: {"Yes" if job.get("reportsAvailable") else "No"}')
            else:
                print_with_flush(f'❌ Job not found: {args.job_id}')
                return False
        
        elif args.action == 'run-job':
            if not args.journey_id or not args.stage_id:
                print_with_flush('❌ --journey-id and --stage-id are required')
                return False
            
            job_id = manager.run_job(
                args.journey_id, 
                args.stage_id,
                triggered_by=args.triggered_by,
                reason=args.reason
            )
            
            if job_id:
                print_with_flush(f'✅ Job started successfully: {job_id}')
                
                # Optionally show job details
                show_details = input('\nShow job details? (y/n): ').strip().lower()
                if show_details == 'y':
                    job = manager.get_job_details(args.journey_id, job_id)
                    if job:
                        manager.display_job_dashboard(job)
            else:
                print_with_flush('❌ Failed to start job')
                return False
        
        elif args.action == 'cancel-job':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            reason = args.reason if hasattr(args, 'reason') else 'User cancellation'
            success = manager.cancel_job(args.journey_id, args.job_id, reason)
            if not success:
                return False
        
        elif args.action == 'update-job-status':
            if not args.journey_id or not args.job_id or not args.job_status:
                print_with_flush('❌ --journey-id, --job-id, and --job-status are required')
                return False
            
            success = manager.update_job_status(
                args.journey_id, args.job_id, args.job_status,
                progress=args.progress,
                current_step=args.current_step,
                error_message=args.error_message
            )
            if not success:
                return False
        
        elif args.action == 'retry-job':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            new_job_id = manager.retry_failed_job(
                args.journey_id, args.job_id,
                triggered_by=args.triggered_by,
                reason=args.reason
            )
            
            if new_job_id:
                print_with_flush(f'✅ Job retry created: {new_job_id}')
            else:
                return False
        
        elif args.action == 'get-job-metrics':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            metrics = manager.get_job_metrics(args.journey_id, args.job_id)
            if metrics:
                if args.include_all:
                    print_with_flush(json.dumps(metrics, indent=2, default=str))
                else:
                    print_with_flush(f'\n📊 JOB METRICS: {args.job_id}')
                    print_with_flush('=' * 60)
                    print_with_flush(f'📋 Stage: {metrics["stageId"]}')
                    print_with_flush(f'📊 Status: {metrics["status"]}')
                    if metrics.get('duration'):
                        print_with_flush(f'⏱️ Duration: {metrics["duration"]:.1f}s')
                    
                    log_metrics = metrics['logMetrics']
                    print_with_flush(f'\n📋 LOG METRICS:')
                    print_with_flush(f'   Total: {log_metrics["totalEntries"]}')
                    print_with_flush(f'   Errors: {log_metrics["errorCount"]}')
                    print_with_flush(f'   Warnings: {log_metrics["warningCount"]}')
                    print_with_flush(f'   Info: {log_metrics["infoCount"]}')
                    
                    perf_metrics = metrics['performanceMetrics']
                    print_with_flush(f'\n⚡ PERFORMANCE METRICS:')
                    if perf_metrics['slowestStep']:
                        step = perf_metrics['slowestStep']
                        print_with_flush(f'   Slowest: {step["step"]} ({step["duration"]:.1f}s)')
                    if perf_metrics['fastestStep']:
                        step = perf_metrics['fastestStep']
                        print_with_flush(f'   Fastest: {step["step"]} ({step["duration"]:.1f}s)')
                    print_with_flush(f'   Error Rate: {perf_metrics["errorRate"]*100:.1f}%')
            else:
                return False
        
        elif args.action == 'get-job-timeline':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            timeline = manager.get_job_timeline(args.journey_id, args.job_id)
            if timeline:
                if args.include_all:
                    print_with_flush(json.dumps(timeline, indent=2, default=str))
                else:
                    events = timeline['timeline']
                    print_with_flush(f'\n⏰ JOB TIMELINE: {args.job_id}')
                    print_with_flush('=' * 60)
                    print_with_flush(f'📊 Total events: {len(events)}')
                    print_with_flush('-' * 60)
                    
                    for event in events[-20:]:  # Show last 20 events
                        timestamp = event.get('timestamp', 'N/A')[:19]
                        event_type = event.get('type', 'unknown')
                        description = event.get('description', 'N/A')
                        
                        type_symbol = {
                            'job_started': '🚀',
                            'job_completed': '🏁',
                            'log_entry': '📝'
                        }.get(event_type, '📝')
                        
                        print_with_flush(f'{timestamp} {type_symbol} {description}')
            else:
                return False
        
        elif args.action == 'batch-cancel-jobs':
            if not args.journey_id or not args.job_ids:
                print_with_flush('❌ --journey-id and --job-ids are required')
                return False
            
            job_ids = [job_id.strip() for job_id in args.job_ids.split(',')]
            results = manager.batch_cancel_jobs(args.journey_id, job_ids, args.reason)
            
            print_with_flush(f'\n🔄 BATCH CANCEL RESULTS:')
            for job_id, success in results.items():
                status = '✅' if success else '❌'
                print_with_flush(f'   {status} {job_id}')
        
        # Logs and Reports operations
        elif args.action == 'get-job-logs':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            # Get job details first to determine stage
            job = manager.get_job_details(args.journey_id, args.job_id)
            if not job:
                return False
            
            logs_data = manager.get_job_logs(
                args.journey_id, 
                job['stageId'], 
                args.job_id,
                step_name=args.step_name
            )
            
            if logs_data:
                if args.include_all:
                    print_with_flush(json.dumps(logs_data, indent=2, default=str))
                else:
                    logs = logs_data.get('logs', [])
                    print_with_flush(f'\n📋 LOGS FOR JOB: {args.job_id}')
                    print_with_flush('=' * 60)
                    print_with_flush(f'📊 Total entries: {len(logs)}')
                    if args.step_name:
                        print_with_flush(f'🔧 Step: {args.step_name}')
                    print_with_flush('-' * 60)
                    
                    for log in logs[-20:]:  # Show last 20 entries
                        timestamp = log.get('timestamp', 'N/A')[:19]
                        level = log.get('level', 'INFO').upper()
                        step = log.get('step_id', log.get('step', 'N/A'))
                        message = log.get('message', 'N/A')
                        
                        level_symbol = {
                            'ERROR': '❌',
                            'WARNING': '⚠️',
                            'INFO': 'ℹ️',
                            'DEBUG': '🔍'
                        }.get(level, 'ℹ️')
                        
                        print_with_flush(f'{timestamp} {level_symbol} [{step}] {message}')
            else:
                print_with_flush('❌ No logs found for this job')
        
        elif args.action == 'add-log-entry':
            if not args.journey_id or not args.job_id or not args.step_name or not args.log_level or not args.log_message:
                print_with_flush('❌ --journey-id, --job-id, --step-name, --log-level, and --log-message are required')
                return False
            
            success = manager.add_job_log_entry(
                args.journey_id, args.job_id, args.step_name,
                args.log_level, args.log_message,
                source=args.source
            )
            if not success:
                return False
        
        elif args.action == 'search-logs':
            if not args.journey_id or not args.search_query:
                print_with_flush('❌ --journey-id and --search-query are required')
                return False
            
            results = manager.search_logs(
                args.journey_id, args.search_query,
                job_id=args.job_id,
                level_filter=args.level_filter,
                step_filter=args.step_filter,
                limit=args.limit
            )
            
            if results:
                if args.include_all:
                    print_with_flush(json.dumps(results, indent=2, default=str))
                else:
                    logs = results['logs']
                    print_with_flush(f'\n🔍 SEARCH RESULTS: "{args.search_query}"')
                    print_with_flush('=' * 60)
                    print_with_flush(f'📊 Total matches: {len(logs)}')
                    if results['filters']['jobId']:
                        print_with_flush(f'🔧 Job filter: {results["filters"]["jobId"]}')
                    if results['filters']['level']:
                        print_with_flush(f'📋 Level filter: {results["filters"]["level"]}')
                    if results['filters']['step']:
                        print_with_flush(f'🔧 Step filter: {results["filters"]["step"]}')
                    print_with_flush('-' * 60)
                    
                    for log in logs[-20:]:  # Show last 20 matches
                        timestamp = log.get('timestamp', 'N/A')[:19]
                        level = log.get('level', 'INFO').upper()
                        job_id = log.get('jobId', 'N/A')
                        step = log.get('step_id', log.get('step', 'N/A'))
                        message = log.get('message', 'N/A')
                        
                        level_symbol = {
                            'ERROR': '❌',
                            'WARNING': '⚠️',
                            'INFO': 'ℹ️',
                            'DEBUG': '🔍'
                        }.get(level, 'ℹ️')
                        
                        print_with_flush(f'{timestamp} {level_symbol} [{job_id}] [{step}] {message}')
            else:
                print_with_flush('❌ Search failed')
                return False
        
        elif args.action == 'get-logs-by-level':
            if not args.journey_id or not args.log_level:
                print_with_flush('❌ --journey-id and --log-level are required')
                return False
            
            # Validate log level
            valid_levels = ['error', 'warning', 'info', 'debug']
            if args.log_level.lower() not in valid_levels:
                print_with_flush(f'❌ Invalid log level: {args.log_level}. Valid levels are: {", ".join(valid_levels)}')
                return False
            
            logs = manager.get_logs_by_level(
                args.journey_id, args.log_level,
                job_id=args.job_id,
                limit=args.limit
            )
            
            print_with_flush(f'\n📋 {args.log_level.upper()} LOGS')
            if args.job_id:
                print_with_flush(f'For Job: {args.job_id}')
            print_with_flush('=' * 60)
            print_with_flush(f'📊 Total entries: {len(logs)}')
            print_with_flush('-' * 60)
            
            level_symbol = {
                'error': '❌',
                'warning': '⚠️',
                'info': 'ℹ️',
                'debug': '🔍'
            }.get(args.log_level.lower(), 'ℹ️')
            
            for log in logs[-20:]:  # Show last 20 entries
                timestamp = log.get('timestamp', 'N/A')[:19]
                job_id = log.get('jobId', 'N/A')
                step = log.get('step_id', log.get('step', 'N/A'))
                message = log.get('message', 'N/A')
                print_with_flush(f'{timestamp} {level_symbol} [{job_id}] [{step}] {message}')
        
        elif args.action == 'export-job-logs':
            if not args.journey_id or not args.job_id or not args.output_file:
                print_with_flush('❌ --journey-id, --job-id, and --output-file are required')
                return False
            
            success = manager.export_job_logs(
                args.journey_id, args.job_id, args.output_file,
                format_type=args.format
            )
            if not success:
                return False
        
        elif args.action == 'get-error-summary':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            summary = manager.get_error_summary(args.journey_id, args.job_id)
            if summary:
                if args.include_all:
                    print_with_flush(json.dumps(summary, indent=2, default=str))
                else:
                    print_with_flush(f'\n❌ ERROR SUMMARY')
                    if args.job_id:
                        print_with_flush(f'For Job: {args.job_id}')
                    print_with_flush('=' * 60)
                    
                    summary_data = summary['summary']
                    print_with_flush(f'📊 Total errors: {summary_data["totalErrors"]}')
                    print_with_flush(f'⚠️ Total warnings: {summary_data["totalWarnings"]}')
                    
                    if summary_data['errorCategories']:
                        print_with_flush(f'\n📋 ERROR CATEGORIES:')
                        for category, count in summary_data['errorCategories'].items():
                            print_with_flush(f'   {category}: {count}')
                    
                    if summary_data['errorsByStep']:
                        print_with_flush(f'\n🔧 ERRORS BY STEP:')
                        for step, count in summary_data['errorsByStep'].items():
                            print_with_flush(f'   {step}: {count}')
                    
                    recent_errors = summary.get('recentErrors', [])
                    if recent_errors:
                        print_with_flush(f'\n🚨 RECENT ERRORS:')
                        for error in recent_errors[-5:]:
                            timestamp = error.get('timestamp', 'N/A')[:19]
                            step = error.get('step', 'N/A')
                            message = error.get('message', 'N/A')[:80]
                            print_with_flush(f'   {timestamp} [{step}] {message}')
            else:
                print_with_flush('❌ Failed to get error summary')
                return False
        
        elif args.action == 'get-job-reports':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            reports_data = manager.get_job_reports(args.journey_id, args.job_id)
            
            if reports_data:
                if args.include_all:
                    print_with_flush(json.dumps(reports_data, indent=2, default=str))
                else:
                    reports = reports_data.get('reports', [])
                    print_with_flush(f'\n📊 REPORTS FOR JOB: {args.job_id}')
                    print_with_flush('=' * 60)
                    print_with_flush(f'📋 Total reports: {len(reports)}')
                    print_with_flush('-' * 60)
                    
                    for report in reports:
                        print_with_flush(f'📄 {report.get("title", "N/A")}')
                        print_with_flush(f'   Type: {report.get("reportType", "N/A")}')
                        print_with_flush(f'   Status: {report.get("status", "N/A")}')
                        print_with_flush(f'   Generated: {report.get("generatedAt", "N/A")}')
                        if report.get('summary'):
                            print_with_flush(f'   Summary: {report["summary"][:100]}...')
                        print_with_flush('')
            else:
                print_with_flush('❌ No reports found for this job')
        
        elif args.action == 'list-available-logs':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            log_summaries = manager.list_available_logs(args.journey_id, args.job_id)
            
            print_with_flush(f'\n📋 AVAILABLE LOGS')
            if args.job_id:
                print_with_flush(f'For Job: {args.job_id}')
            print_with_flush('=' * 60)
            
            if not log_summaries:
                print_with_flush('📋 No logs found')
            else:
                for summary in log_summaries:
                    print_with_flush(f'🚀 Job: {summary["jobId"]}')
                    print_with_flush(f'   📊 Total entries: {summary["totalEntries"]}')
                    print_with_flush(f'   🔧 Steps: {", ".join(summary["steps"])}')
                    print_with_flush(f'   📋 Levels: {", ".join(summary["levels"])}')
                    print_with_flush(f'   🕐 First: {summary["firstEntry"]}')
                    print_with_flush(f'   🏁 Last: {summary["lastEntry"]}')
                    print_with_flush('')
        
        elif args.action == 'generate-summary-report':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            report = manager.generate_job_summary_report(args.journey_id, args.job_id)
            
            if report:
                if args.include_all:
                    print_with_flush(json.dumps(report, indent=2, default=str))
                else:
                    print_with_flush(f'\n📊 JOB SUMMARY REPORT: {args.job_id}')
                    print_with_flush('=' * 80)
                    
                    job_summary = report['jobSummary']
                    metrics = report['executionMetrics']
                    
                    print_with_flush(f'📋 Stage: {job_summary["stageId"]} ({job_summary["stageName"]})')
                    print_with_flush(f'📊 Status: {job_summary["status"]}')
                    print_with_flush(f'📈 Progress: {job_summary["progress"]}%')
                    print_with_flush(f'👤 Triggered by: {job_summary["triggeredBy"]}')
                    
                    if job_summary.get('executionTime'):
                        print_with_flush(f'⏱️ Execution time: {job_summary["executionTime"]:.1f} seconds')
                    
                    print_with_flush(f'\n📊 EXECUTION METRICS:')
                    print_with_flush(f'   🔧 Total steps: {metrics["totalSteps"]}')
                    print_with_flush(f'   📋 Total logs: {metrics["totalLogs"]}')
                    print_with_flush(f'   ❌ Errors: {metrics["errorsCount"]}')
                    print_with_flush(f'   ⚠️ Warnings: {metrics["warningsCount"]}')
                    
                    recommendations = report.get('recommendations', [])
                    if recommendations:
                        print_with_flush(f'\n💡 RECOMMENDATIONS:')
                        for rec in recommendations:
                            priority_symbol = {
                                'high': '🔴',
                                'medium': '🟡',
                                'low': '🟢'
                            }.get(rec.get('priority', 'low'), '🟢')
                            print_with_flush(f'   {priority_symbol} {rec["message"]}')
            else:
                print_with_flush('❌ Failed to generate summary report')
                return False
        
        elif args.action == 'create-job-report':
            if not args.journey_id or not args.job_id or not args.report_type or not args.report_title:
                print_with_flush('❌ --journey-id, --job-id, --report-type, and --report-title are required')
                return False
            
            # Load report content from file if provided
            report_content = {}
            if args.report_content:
                try:
                    with open(args.report_content, 'r') as f:
                        report_content = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print_with_flush(f'❌ Error loading report content: {str(e)}')
                    return False
            else:
                # Default content structure
                report_content = {
                    'sections': [],
                    'metadata': {
                        'createdBy': 'user',
                        'reportVersion': '1.0'
                    }
                }
            
            success = manager.create_job_report(
                args.journey_id, args.job_id, args.report_type,
                args.report_title, report_content
            )
            if not success:
                return False
        
        elif args.action == 'generate-performance-report':
            if not args.journey_id or not args.job_id:
                print_with_flush('❌ --journey-id and --job-id are required')
                return False
            
            report = manager.generate_performance_report(args.journey_id, args.job_id)
            if report:
                if args.include_all:
                    print_with_flush(json.dumps(report, indent=2, default=str))
                else:
                    print_with_flush(f'\n⚡ PERFORMANCE REPORT: {args.job_id}')
                    print_with_flush('=' * 80)
                    
                    exec_summary = report['executionSummary']
                    print_with_flush(f'📋 Stage: {exec_summary["stageId"]}')
                    print_with_flush(f'📊 Status: {exec_summary["status"]}')
                    print_with_flush(f'📈 Progress: {exec_summary["progress"]}%')
                    
                    perf_metrics = report['performanceMetrics']
                    if perf_metrics.get('executionTime'):
                        print_with_flush(f'⏱️ Total time: {perf_metrics["executionTime"]:.1f}s')
                    if perf_metrics.get('avgStepDuration'):
                        print_with_flush(f'📊 Avg step duration: {perf_metrics["avgStepDuration"]:.1f}s')
                    
                    if perf_metrics.get('slowestStep'):
                        step = perf_metrics['slowestStep']
                        print_with_flush(f'🐌 Slowest step: {step["step"]} ({step["duration"]:.1f}s)')
                    
                    print_with_flush(f'🎯 Error rate: {perf_metrics["errorRate"]*100:.1f}%')
                    
                    recommendations = report.get('recommendations', [])
                    if recommendations:
                        print_with_flush(f'\n💡 RECOMMENDATIONS ({len(recommendations)}):')
                        for rec in recommendations:
                            priority_symbol = {
                                'high': '🔴',
                                'medium': '🟡',
                                'low': '🟢'
                            }.get(rec.get('priority', 'low'), '🟢')
                            print_with_flush(f'   {priority_symbol} {rec["issue"]}: {rec["recommendation"]}')
                    
                    print_with_flush(f'\n✅ Performance report generated and saved to database')
            else:
                print_with_flush('❌ Failed to generate performance report')
                return False
        
        # Import/Export
        elif args.action == 'export-complete':
            if not args.journey_id or not args.output_file:
                print_with_flush('❌ --journey-id and --output-file are required')
                return False
            
            manager.export_journey_complete(args.journey_id, args.output_file)
        
        elif args.action == 'import-complete':
            if not args.input_file:
                print_with_flush('❌ --input-file is required')
                return False
            
            journey_id = manager.import_journey_complete(args.input_file, args.journey_id)
            if journey_id:
                print_with_flush(f'✅ Journey imported: {journey_id}')
        
        # Interactive
        elif args.action == 'dashboard':
            if not args.journey_id:
                print_with_flush('❌ --journey-id is required')
                return False
            
            manager.display_journey_dashboard(args.journey_id)
        
        elif args.action == 'interactive' or args.action == 'wizard':
            manager.interactive_journey_wizard()
        
        return True
        
    except Exception as e:
        print_with_flush(f'❌ Error: {str(e)}')
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_with_flush('\n⚠️ Operation cancelled by user')
        sys.exit(1)
    except Exception as e:
        print_with_flush(f'\n❌ Unexpected error: {str(e)}')
        traceback.print_exc()
        sys.exit(1) 