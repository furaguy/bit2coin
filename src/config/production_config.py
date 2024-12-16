# File: src/config/production_config.py

import yaml
import os
from typing import Dict, Any

class ProductionConfig:
    def __init__(self, config_path: str = "config/production.yaml"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return self._create_default_config()
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _create_default_config(self) -> Dict[str, Any]:
        config = {
            "network": {
                "host": "0.0.0.0",
                "port": 8000,
                "max_peers": 50,
                "bootstrap_nodes": [
                    {
                        "host": "bootstrap1.bit2coin.net",
                        "port": 8000
                    }
                ]
            },
            "consensus": {
                "min_stake_amount": 1000,
                "lockup_period": 86400,
                "finality_threshold": 0.67,
                "vote_timeout": 300
            },
            "monitoring": {
                "metrics_port": 9090,
                "log_dir": "logs",
                "log_level": "INFO"
            },
            "security": {
                "max_block_size": 1048576,  # 1MB
                "max_transaction_size": 16384,  # 16KB
                "rate_limit_requests": 100,
                "rate_limit_period": 60
            }
        }
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
        
        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def update(self, key: str, value: Any):
        """Update configuration value."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f)
