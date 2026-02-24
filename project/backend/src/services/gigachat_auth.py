import os
import base64
import requests
import time
import uuid 

class GigaChatAuth:
    def __init__(self):
        self.credentials = os.getenv("GIGACHAT_AUTH_KEY")
        if not self.credentials:
            raise ValueError("GIGACHAT_AUTH_KEY не задан в .env")
        
        self._access_token = None
        self._expires_at = 0

    def get_access_token(self):
        """Возвращает действующий Access Token"""
        now = time.time()
        if self._access_token and now < self._expires_at - 60:
            return self._access_token

        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self.credentials}"
        }
        data = {"scope": "GIGACHAT_API_PERS"}

        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        
        token_data = response.json()
        self._access_token = token_data["access_token"]

        expires_in = token_data.get("expires_in", 1800)
        self._expires_at = now + expires_in
        
        return self._access_token