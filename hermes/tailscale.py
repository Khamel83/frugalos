"""
Hermes Tailscale Communication Module
Handles communication with Talos (Mac Mini) via Tailscale
"""

import json
import logging
import requests
import socket
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

from .config import Config

logger = logging.getLogger(__name__)

class TailscaleClient:
    """Client for communicating with Talos over Tailscale network"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.tailscale_config = self.config.get_tailscale_config()
        self.timeout = self.tailscale_config.get('timeout', 30)

    def test_connection(self) -> bool:
        """Test if we can reach Talos via Tailscale"""
        try:
            # Try to resolve the Talos hostname
            talos_endpoint = self.config.get('talos.endpoint')
            if not talos_endpoint:
                logger.warning("No Talos endpoint configured")
                return False

            # Parse hostname from endpoint
            if '://' in talos_endpoint:
                talos_endpoint = talos_endpoint.split('://')[1]
            if ':' in talos_endpoint:
                talos_endpoint = talos_endpoint.split(':')[0]

            # Test DNS resolution
            socket.gethostbyname(talos_endpoint)

            # Test HTTP connectivity
            health_url = urljoin(self.config.get('talos.endpoint'), '/health')
            response = requests.get(health_url, timeout=5)
            return response.status_code == 200

        except Exception as e:
            logger.debug(f"Tailscale connection test failed: {e}")
            return False

    def send_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send command to Talos

        Args:
            command: Command to execute (e.g., 'run', 'status', 'cancel')
            params: Additional parameters for the command

        Returns:
            Response from Talos
        """
        talos_endpoint = self.config.get('talos.endpoint')
        if not talos_endpoint:
            raise ValueError("No Talos endpoint configured")

        url = urljoin(talos_endpoint, f'/api/{command}')
        payload = params or {}

        try:
            logger.info(f"Sending command to Talos: {command}")
            logger.debug(f"Talos URL: {url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'Hermes/0.1.0'
                }
            )

            logger.debug(f"Talos response status: {response.status_code}")
            logger.debug(f"Talos response: {response.text}")

            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Talos command failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except requests.exceptions.Timeout:
            error_msg = f"Talos command timed out after {self.timeout}s"
            logger.error(error_msg)
            raise Exception(error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Failed to connect to Talos: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error sending command to Talos: {e}"
            logger.error(error_msg)
            raise

    def run_frugalos_job(self, idea: str, job_id: int, **kwargs) -> Dict[str, Any]:
        """
        Execute a FrugalOS job on Talos

        Args:
            idea: The idea/job description
            job_id: Hermes job ID for tracking
            **kwargs: Additional FrugalOS parameters

        Returns:
            Job execution results
        """
        params = {
            'idea': idea,
            'job_id': job_id,
            'working_dir': f'hermes_jobs/{job_id}',
            'timestamp': time.time()
        }

        # Add optional parameters
        if 'context' in kwargs:
            params['context'] = kwargs['context']
        if 'schema' in kwargs:
            params['schema'] = kwargs['schema']
        if 'budget_cents' in kwargs:
            params['budget_cents'] = kwargs['budget_cents']
        if 'models' in kwargs:
            params['models'] = kwargs['models']
        if 'project' in kwargs:
            params['project'] = kwargs['project']

        return self.send_command('run', params)

    def get_job_status(self, talos_job_id: str) -> Dict[str, Any]:
        """Get status of a job running on Talos"""
        return self.send_command('status', {'job_id': talos_job_id})

    def cancel_job(self, talos_job_id: str) -> Dict[str, Any]:
        """Cancel a job running on Talos"""
        return self.send_command('cancel', {'job_id': talos_job_id})

    def get_system_info(self) -> Dict[str, Any]:
        """Get system information from Talos"""
        try:
            return self.send_command('system_info')
        except Exception as e:
            logger.warning(f"Failed to get system info from Talos: {e}")
            return {}

    def list_available_models(self) -> List[str]:
        """Get list of available models on Talos"""
        try:
            response = self.send_command('list_models')
            return response.get('models', [])
        except Exception as e:
            logger.warning(f"Failed to get model list from Talos: {e}")
            return []

    def test_frugalos(self) -> bool:
        """Test if FrugalOS is working on Talos"""
        try:
            response = self.send_command('test', {'command': 'version'})
            return response.get('success', False)
        except Exception as e:
            logger.error(f"FrugalOS test failed: {e}")
            return False

    def wait_for_completion(
        self,
        talos_job_id: str,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for job completion with polling

        Args:
            talos_job_id: Job ID on Talos
            timeout: Maximum time to wait in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Final job results
        """
        start_time = time.time()
        last_status = None

        while time.time() - start_time < timeout:
            try:
                status = self.get_job_status(talos_job_id)
                current_state = status.get('state', 'unknown')

                if current_state != last_status:
                    logger.info(f"Talos job {talos_job_id} status: {current_state}")
                    last_status = current_state

                if current_state in ['completed', 'failed', 'cancelled']:
                    logger.info(f"Talos job {talos_job_id} finished with status: {current_state}")
                    return status

                time.sleep(poll_interval)

            except Exception as e:
                logger.warning(f"Error checking job status: {e}")
                time.sleep(poll_interval)

        # Timeout reached
        raise TimeoutError(f"Job {talos_job_id} did not complete within {timeout} seconds")

class MockTailscaleClient:
    """Mock Tailscale client for testing/development"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()

    def test_connection(self) -> bool:
        """Always return True for mock"""
        return True

    def send_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Mock command execution"""
        logger.info(f"MOCK: Sending command {command} with params: {params}")

        if command == 'run':
            return {
                'success': True,
                'job_id': f'mock_job_{int(time.time())}',
                'status': 'queued',
                'message': 'Job queued successfully (mock)'
            }
        elif command == 'status':
            return {
                'status': 'completed',
                'result': 'Mock job completed successfully',
                'execution_time': 1.5
            }
        elif command == 'system_info':
            return {
                'hostname': 'mock-talos',
                'os': 'macOS',
                'frugalos_version': '0.1.0',
                'models_available': ['llama3.1:8b-instruct', 'qwen2.5-coder:7b']
            }
        else:
            return {'success': True, 'message': f'Mock command {command} executed'}

def get_tailscale_client(config: Optional[Config] = None) -> TailscaleClient:
    """Factory function to get Tailscale client"""
    # Use mock client if configured
    if config and config.get('tailscale.use_mock', False):
        logger.info("Using mock Tailscale client")
        return MockTailscaleClient(config)

    return TailscaleClient(config)