"""
Hermes Configuration Management
Handles environment variables and configuration settings
"""

import os
import yaml
from typing import Dict, Any, Optional

class Config:
    """Configuration manager for Hermes application"""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.getenv('HERMES_CONFIG_FILE', 'hermes/config.yaml')
        self._config = {}
        self.load_config()

    def load_config(self):
        """Load configuration from file and environment"""
        # Load from YAML file if it exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Could not load config file {self.config_file}: {e}")
                self._config = {}

        # Override with environment variables
        env_overrides = {
            'hermes.debug': os.getenv('HERMES_DEBUG', 'false').lower() == 'true',
            'hermes.host': os.getenv('HERMES_HOST', '0.0.0.0'),
            'hermes.port': int(os.getenv('HERMES_PORT', '5000')),
            'hermes.secret_key': os.getenv('HERMES_SECRET_KEY'),
            'database.path': os.getenv('HERMES_DB_PATH', 'hermes.db'),
            'tailscale.api_key': os.getenv('TAILSCALE_API_KEY'),
            'tailscale.network': os.getenv('TAILSCALE_NETWORK'),
            'talos.endpoint': os.getenv('TALOS_ENDPOINT'),
            'frugalos.allow_remote': os.getenv('FRUGAL_ALLOW_REMOTE', '0') == '1',
            'frugalos.timeout': int(os.getenv('FRUGALOS_TIMEOUT', '300')),
            'metalearning.enabled': os.getenv('HERMES_METALEARNING_ENABLED', 'true').lower() == 'true',
            'metalearning.max_questions': int(os.getenv('HERMES_METALEARNING_MAX_QUESTIONS', '3')),
        }

        for key, value in env_overrides.items():
            if value is not None:
                self.set(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split('.')
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """Set configuration value by key (supports dot notation)"""
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return {
            'path': self.get('database.path', 'hermes.db'),
            'timeout': self.get('database.timeout', 30),
            'check_same_thread': False
        }

    def get_tailscale_config(self) -> Dict[str, Any]:
        """Get Tailscale configuration"""
        return {
            'api_key': self.get('tailscale.api_key'),
            'network': self.get('tailscale.network'),
            'timeout': self.get('tailscale.timeout', 30)
        }

    def get_frugalos_config(self) -> Dict[str, Any]:
        """Get FrugalOS configuration"""
        return {
            'allow_remote': self.get('frugalos.allow_remote', False),
            'timeout': self.get('frugalos.timeout', 300),
            'working_dir': self.get('frugalos.working_dir', 'out'),
            'models': {
                'text': self.get('frugalos.models.text', 'llama3.1:8b-instruct'),
                'code': self.get('frugalos.models.code', 'qwen2.5-coder:7b')
            }
        }

    def get_metalearning_config(self) -> Dict[str, Any]:
        """Get meta-learning configuration"""
        return {
            'enabled': self.get('metalearning.enabled', True),
            'max_questions': self.get('metalearning.max_questions', 3),
            'min_confidence': self.get('metalearning.min_confidence', 0.7),
            'learning_rate': self.get('metalearning.learning_rate', 0.1)
        }

    def get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get configuration for a specific backend"""
        return self.get(f'backends.{backend_name}', {})

    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled"""
        return self.get('hermes.debug', False)

    def __getitem__(self, key: str) -> Any:
        """Dictionary-style access"""
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        """Dictionary-style assignment"""
        self.set(key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Return complete configuration as dictionary"""
        return self._config.copy()