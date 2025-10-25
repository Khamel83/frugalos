"""
Hermes Local Execution Module
Direct integration with local AI execution capabilities
"""

import subprocess
import json
import os
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .config import Config
from .database import Database

logger = logging.getLogger(__name__)

@dataclass
class FrugalOSResult:
    """Result from FrugalOS execution"""
    success: bool
    job_id: str
    result_data: Any = None
    error_message: str = None
    cost_cents: int = 0
    execution_time_ms: int = 0
    backend_used: str = None
    model_used: str = None
    validation_passed: bool = True
    consensus_score: float = 0.0

class LocalExecutionEngine:
    """Local execution engine for AI tasks"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.hermes_config = self.config.get_local_execution_config()
        self.working_dir = Path(self.hermes_config.get('working_dir', 'out'))
        self.timeout = self.hermes_config.get('timeout', 300)

    def test_local_execution(self) -> bool:
        """Test if local execution capabilities are available"""
        try:
            # Check if Ollama is running and models are available
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Local execution test failed: {e}")
            return False

    def get_available_models(self) -> List[str]:
        """Get list of available local models"""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Parse output to extract models
                models = []
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split()
                        if parts:
                            models.append(parts[0])
                return models
            return []
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []

    def run_idea(
        self,
        idea: str,
        job_id: int,
        context: Optional[str] = None,
        schema: Optional[str] = None,
        budget_cents: int = 0,
        project: Optional[str] = None,
        models: Optional[Dict[str, str]] = None
    ) -> FrugalOSResult:
        """
        Execute an idea using local AI capabilities

        Args:
            idea: The idea/task to execute
            job_id: Hermes job ID for tracking
            context: Optional context file path
            schema: Optional schema file path
            budget_cents: Budget in cents (0 = local only)
            project: Project name for organization
            models: Model preferences

        Returns:
            Execution result
        """
        start_time = __import__('time').time()

        try:
            # Create project directory
            if not project:
                project = f"hermes_job_{job_id}"

            project_dir = self.working_dir / project
            project_dir.mkdir(parents=True, exist_ok=True)

            # Determine which model to use
            model_to_use = models.get('text') if models else 'llama3.1:8b-instruct'

            # Build Ollama command for direct execution
            cmd = [
                'ollama', 'run', model_to_use,
                f"Execute this task: {idea}"
            ]

            # Add context if provided
            if context and os.path.exists(context):
                with open(context, 'r') as f:
                    context_content = f.read()
                cmd[-1] = f"Context: {context_content}\n\nTask: {idea}"

            logger.info(f"Executing with local model {model_to_use}: {idea[:100]}...")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.working_dir)
            )

            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                execution_time = (__import__('time').time() - start_time) * 1000

                if process.returncode == 0:
                    # Parse successful result
                    result_data = self._parse_local_output(stdout, project_dir)
                    return FrugalOSResult(
                        success=True,
                        job_id=str(job_id),
                        result_data=result_data,
                        execution_time_ms=int(execution_time),
                        backend_used='local',
                        model_used=model_to_use,
                        validation_passed=True,
                        consensus_score=1.0
                    )
                else:
                    # Handle execution error
                    error_message = self._parse_local_error(stderr, stdout)
                    return FrugalOSResult(
                        success=False,
                        job_id=str(job_id),
                        error_message=error_message,
                        execution_time_ms=int(execution_time)
                    )

            except subprocess.TimeoutExpired:
                process.kill()
                error_message = f"Local execution timed out after {self.timeout} seconds"
                logger.error(error_message)
                return FrugalOSResult(
                    success=False,
                    job_id=str(job_id),
                    error_message=error_message,
                    execution_time_ms=int((__import__('time').time() - start_time) * 1000)
                )

        except Exception as e:
            error_message = f"Unexpected error executing locally: {str(e)}"
            logger.error(error_message, exc_info=True)
            return FrugalOSResult(
                success=False,
                job_id=str(job_id),
                error_message=error_message,
                execution_time_ms=int((__import__('time').time() - start_time) * 1000)
            )

    def _parse_local_output(self, stdout: str, project_dir: Path) -> Dict[str, Any]:
        """Parse local execution output to extract results and metadata"""
        result = {
            'raw_output': stdout,
            'response': stdout.strip(),
            'backend': 'local',
            'model': 'unknown'
        }

        try:
            # Try to extract structured data from response
            lines = stdout.strip().split('\n')

            # Look for JSON in the output
            for line in lines:
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        json_data = json.loads(line)
                        result.update(json_data)
                        result['response'] = json.dumps(json_data, indent=2)
                        break
                    except json.JSONDecodeError:
                        continue

            # Save output to file
            if project_dir.exists():
                output_file = project_dir / 'result.json'
                try:
                    with open(output_file, 'w') as f:
                        json.dump(result, f, indent=2)
                    result['output_file'] = str(output_file)
                except Exception as e:
                    logger.warning(f"Failed to save output file: {e}")

        except Exception as e:
            logger.warning(f"Error parsing local output: {e}")

        return result

    def _parse_local_error(self, stderr: str, stdout: str) -> str:
        """Parse local execution error output"""
        error_lines = []

        # Parse stderr for error messages
        if stderr:
            for line in stderr.strip().split('\n'):
                line = line.strip()
                if line and 'error' in line.lower():
                    error_lines.append(line)

        # Parse stdout for error messages
        if stdout:
            for line in stdout.strip().split('\n'):
                line = line.strip()
                if 'error' in line.lower() or 'failed' in line.lower():
                    error_lines.append(line)

        # Return the most relevant error message
        if error_lines:
            return error_lines[-1]  # Usually the last error is most specific

        return "Local execution failed with unknown error"

    def get_job_history(self, project: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get job history from local execution"""
        if not self.working_dir.exists():
            return []

        try:
            project_dir = self.working_dir / project
            if not project_dir.exists():
                return []

            # Look for result files
            result_files = list(project_dir.glob('**/*.json'))
            history = []

            for result_file in result_files:
                try:
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                    data['file_path'] = str(result_file)
                    data['modified_time'] = result_file.stat().st_mtime
                    history.append(data)
                except Exception as e:
                    logger.warning(f"Failed to parse result file {result_file}: {e}")

            # Sort by modification time and limit
            history.sort(key=lambda x: x.get('modified_time', 0), reverse=True)
            return history[:limit]

        except Exception as e:
            logger.error(f"Failed to get job history: {e}")
            return []

    def cleanup_old_jobs(self, days_to_keep: int = 7):
        """Clean up old job data from working directory"""
        try:
            cutoff_time = __import__('time').time() - (days_to_keep * 24 * 60 * 60)

            for project_dir in self.working_dir.iterdir():
                if project_dir.is_dir():
                    try:
                        dir_mtime = project_dir.stat().st_mtime
                        if dir_mtime < cutoff_time:
                            logger.info(f"Cleaning up old project: {project_dir.name}")
                            shutil.rmtree(project_dir)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup {project_dir}: {e}")

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get local execution system status"""
        status = {
            'available': False,
            'models': [],
            'disk_usage': 0,
            'recent_jobs': 0
        }

        try:
            # Check if local execution is available
            status['available'] = self.test_local_execution()

            if status['available']:
                # Get available models
                status['models'] = self.get_available_models()

                # Get disk usage
                if self.working_dir.exists():
                    total_size = sum(f.stat().st_size for f in self.working_dir.rglob('*') if f.is_file())
                    status['disk_usage'] = total_size

                # Count recent projects (last 24 hours)
                cutoff_time = __import__('time').time() - (24 * 60 * 60)
                recent_projects = 0
                for project_dir in self.working_dir.iterdir():
                    if project_dir.is_dir() and project_dir.stat().st_mtime > cutoff_time:
                        recent_projects += 1
                status['recent_jobs'] = recent_projects

        except Exception as e:
            logger.error(f"Failed to get local execution status: {e}")

        return status