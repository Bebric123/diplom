# error_monitor_sdk/logs.py
import os
import requests
import logging
import threading
from typing import Optional, Dict, Any
from .client import get_client

logger = logging.getLogger("error_monitor_sdk")

def send_log_file(
    filepath: str,
    lines: int = 50,
    server_name: Optional[str] = None,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
    error_group_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Отправляет последние N строк лог-файла на сервер
    
    Args:
        filepath: Путь к лог-файлу
        lines: Количество последних строк для отправки
        server_name: Имя сервера
        service_name: Имя сервиса
        environment: Окружение (production, staging, etc)
        error_group_id: ID группы ошибок (если привязано)
        metadata: Дополнительные метаданные
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Call init_monitor() first")

    try:
        # Проверяем существование файла
        if not os.path.exists(filepath):
            logger.error(f"Log file not found: {filepath}")
            return False
        
        # Читаем последние N строк
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            total_lines = len(all_lines)
            last_lines = all_lines[-lines:] if lines > 0 else all_lines
            content = ''.join(last_lines)
        
        if not content:
            logger.warning(f"⚠️ Log file {filepath} is empty")
            return False
        
        filename = os.path.basename(filepath)
        
        # Формируем данные для отправки
        data = {
            "project_id": client.project_id,
            "filename": filename,
            "content": content,
            "lines_sent": min(lines, total_lines),
            "total_lines": total_lines,
            "server_name": server_name or os.environ.get('HOSTNAME', os.environ.get('COMPUTERNAME', 'unknown')),
            "service_name": service_name,
            "environment": environment or client.context.get('environment', 'production'),
            "error_group_id": error_group_id,
            "metadata": metadata or {}
        }

        thread = threading.Thread(
            target=_send_log_sync,
            args=(data,),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Log file {filename} queued for sending (last {min(lines, total_lines)} of {total_lines} lines)")
        return True
        
    except Exception as e:
        logger.error(f"Error reading/sending log file: {e}")
        return False

def _send_log_sync(data: dict):
    """Синхронная отправка лога"""
    client = get_client()
    if client is None:
        logger.error("SDK not initialized, log upload skipped")
        return
    try:
        response = requests.post(
            f"{client.endpoint}/logs/upload",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code == 200:
            logger.info(f"Log file sent successfully: {response.json().get('id', 'unknown')}")
        else:
            logger.error(f"Failed to send log: {response.status_code} - {response.text}")
    except requests.exceptions.Timeout:
        logger.error("Timeout sending log file")
    except requests.exceptions.ConnectionError:
        logger.error("Connection error to %s", client.endpoint)
    except Exception as e:
        logger.error(f"Error sending log: {e}")