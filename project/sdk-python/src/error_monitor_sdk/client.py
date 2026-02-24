import os
import json
import logging
import threading
from typing import Optional, Dict, Any
import requests

_logger = logging.getLogger("error_monitor_sdk")

class MonitorClient:
    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def send_event(self, user_id: str, action: str, metadata: Optional[Dict[str, Any]] = None):
        payload = {
            "user_id": user_id,
            "action": action,
            "page_url": "server-side",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "metadata": metadata or {}
        }

        try:
            thread = threading.Thread(
                target=self._send_sync,
                args=(payload,),
                daemon=True
            )
            thread.start()
        except Exception as e:
            _logger.warning(f"Failed to queue event: {e}")

    def _send_sync(self, payload: dict):
        try:
            response = self.session.post(
                f"{self.endpoint}/track",
                json=payload,
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            _logger.warning(f"Failed to send event to {self.endpoint}: {e}")

_client: Optional[MonitorClient] = None

def init_monitor(endpoint: str, api_key: Optional[str] = None):
    global _client
    _client = MonitorClient(endpoint, api_key)
    _logger.info(f"ErrorMonitor SDK initialized for {endpoint}")

def track_event(user_id: str, action: str, metadata: Optional[Dict[str, Any]] = None):
    if _client is None:
        raise RuntimeError("Call init_monitor() first")
    _client.send_event(user_id, action, metadata)