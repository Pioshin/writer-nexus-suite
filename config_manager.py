import os
import json
import logging
import threading

# Default configuration structure
DEFAULT_CONFIG = {
    "ai": {
        "provider": "ollama",
        "model": "adam:latest",
        "url": "http://127.0.0.1:11434",
        "api_key": "",
        "ctx": 32768,
        "timeout": 180,
        "keep_alive": "5m"
    },
    "ui": {
        "theme": "amber",
        "font_size": "medium"
    },
    "paths": {
        "sandbox_root": "./sandbox",
        "bibbia_root": "./bibbia"
    }
}

class UnifiedConfigManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, config_path=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(UnifiedConfigManager, cls).__new__(cls)
                    cls._instance.initialized = False
        return cls._instance

    def __init__(self, config_path=None):
        if self.initialized:
            return
            
        self.logger = logging.getLogger("Nexus.Config")
        
        # Determine config path: defaults to same dir as this file
        if config_path:
            self.config_path = config_path
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(base_dir, "config.json")
            
        self.config = self._load_config()
        self.initialized = True

    def _load_config(self):
        """Loads config from JSON or returns defaults."""
        if not os.path.exists(self.config_path):
            self.logger.info(f"Config file not found at {self.config_path}, creating defaults.")
            self._save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Merge with defaults to ensure all keys exist
            merged = DEFAULT_CONFIG.copy()
            for section, values in data.items():
                if section in merged and isinstance(values, dict):
                    merged[section].update(values)
                else:
                    merged[section] = values
            return merged
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return DEFAULT_CONFIG

    def _save_config(self, data):
        """Saves config to JSON."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False

    def get_ai_config(self):
        return self.config.get("ai", DEFAULT_CONFIG["ai"])

    def update_ai_config(self, **kwargs):
        """Updates AI settings. kwargs match keys in 'ai' section."""
        with self._lock:
            current = self.config.get("ai", DEFAULT_CONFIG["ai"].copy())
            
            changed = False
            for k, v in kwargs.items():
                if k in current and current[k] != v:
                    current[k] = v
                    changed = True
                elif k not in current:
                    # Allow new keys? intent is yes.
                    current[k] = v
                    changed = True
            
            if changed:
                self.config["ai"] = current
                self._save_config(self.config)
                return True
            return False

    def get_ui_config(self):
        return self.config.get("ui", DEFAULT_CONFIG["ui"])
        
    def get_all(self):
        return self.config
