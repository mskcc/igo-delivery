"""
Centralized logging setup for igo-delivery scripts.

Provides a factory function that configures Python's standard logging with:
  - Console output (StreamHandler) -- always enabled
  - Splunk HEC batched logging (SplunkHandler) -- enabled when configured in .env

Configuration is loaded exclusively from a .env file (via python-dotenv).
See .env.example for all available settings.

Usage:
    from splunk_logging import setup_logging, flush_and_shutdown

    logger = setup_logging("MyScript")
    logger.info("Hello from MyScript")

    # At script exit, flush any queued Splunk events
    flush_and_shutdown()
"""

import logging
import os
from pathlib import Path

from dotenv import dotenv_values
import json
import requests
import time as time_module
import queue
import threading

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_config = None          # Loaded .env values (dict)
_splunk_enabled = False # Whether SplunkHandler was attached
_splunk_handlers = []   # List of all custom handlers (one per logger)


class JSONSplunkHandler(logging.Handler):
    """
    Custom Splunk HEC handler that sends events in the correct JSON format:
    {"event": {"message": "..."}, "sourcetype": "_json", "index": "..."}
    """
    
    def __init__(self, host, port, token, index, sourcetype, source, verify=True, timeout=10):
        super().__init__()
        self.url = f"https://{host}:{port}/services/collector/event"
        self.token = token
        self.index = index
        self.sourcetype = sourcetype
        self.source = source
        self.verify = verify
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Splunk {token}",
            "Content-Type": "application/json"
        })
        self._queue = queue.Queue()
        self._shutdown = False
        self._worker = threading.Thread(target=self._send_worker, daemon=True)
        self._worker.start()
    
    def emit(self, record):
        try:
            payload = {
                "event": {
                    "message": self.format(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "timestamp": record.created
                },
                "host": getattr(record, 'hostname', None) or __import__('socket').gethostname(),
                "index": self.index,
                "source": self.source,
                "sourcetype": self.sourcetype,
                "time": record.created
            }
            self._queue.put(payload)
            print(f"[JSONSplunkHandler] Queued: {json.dumps(payload)}")
        except Exception as e:
            print(f"[JSONSplunkHandler] Error queueing: {e}")
    
    def _send_worker(self):
        while not self._shutdown:
            try:
                payload = self._queue.get(timeout=1)
                self._send(payload)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[JSONSplunkHandler] Worker error: {e}")
    
    def _send(self, payload):
        try:
            response = self.session.post(
                self.url,
                data=json.dumps(payload),
                verify=self.verify,
                timeout=self.timeout
            )
            print(f"[JSONSplunkHandler] Response: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[JSONSplunkHandler] Send error: {e}")
    
    def flush(self):
        # Wait for queue to empty
        while not self._queue.empty():
            time_module.sleep(0.1)
    
    def close(self):
        self._shutdown = True
        self.flush()
        super().close()


def _load_config():
    """
    Load configuration from .env file, falling back to system environment variables.
    
    Priority:
    1. .env file (if exists)
    2. .env.deploy file (if exists, for committed config)
    3. System environment variables (for secrets like SPLUNK_HEC_TOKEN)
    """
    global _config
    if _config is not None:
        return _config

    base_path = Path(__file__).resolve().parent
    
    # Try .env first, then .env.deploy
    env_path = base_path / ".env"
    if not env_path.exists():
        env_path = base_path / ".env.deploy"
    
    if env_path.exists():
        _config = dotenv_values(env_path)
    else:
        _config = {}
    
    # Fall back to system environment variables for any missing/empty values
    env_keys = [
        "SPLUNK_HEC_HOST", "SPLUNK_HEC_TOKEN", "SPLUNK_HEC_PORT",
        "SPLUNK_HEC_INDEX", "SPLUNK_HEC_SOURCETYPE", "SPLUNK_HEC_SSL_VERIFY",
        "SPLUNK_FLUSH_INTERVAL", "SPLUNK_QUEUE_SIZE"
    ]
    for key in env_keys:
        file_value = _config.get(key, "").strip()
        # Check if value is empty or is a variable reference like ${SPLUNK_HEC_TOKEN}
        if not file_value or file_value.startswith("${"):
            env_value = os.environ.get(key, "")
            if env_value:
                _config[key] = env_value
    
    return _config


def setup_logging(script_name, level=logging.INFO):
    """
    Create and return a configured logger for *script_name*.

    - Always attaches a StreamHandler (console).
    - Attaches a SplunkHandler if SPLUNK_HEC_HOST and SPLUNK_HEC_TOKEN
      are present in the .env file.

    Calling this function multiple times with the same *script_name*
    returns the same logger (standard logging behaviour) without
    adding duplicate handlers.
    """
    global _splunk_enabled

    logger = logging.getLogger(script_name)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # --- Console handler (always) -------------------------------------------
    console = logging.StreamHandler()
    console.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(formatter)
    logger.addHandler(console)

    # --- Splunk HEC handler (conditional) ------------------------------------
    cfg = _load_config()
    splunk_host = cfg.get("SPLUNK_HEC_HOST", "").strip()
    splunk_token = cfg.get("SPLUNK_HEC_TOKEN", "").strip()
    
    # Log all Splunk config for debugging
    splunk_port = cfg.get("SPLUNK_HEC_PORT", "8088")
    splunk_url = f"https://{splunk_host}:{splunk_port}/services/collector/event" if splunk_host else "NOT CONFIGURED"
    logger.info("Splunk config: URL=%s, INDEX=%s, SOURCETYPE=%s, SSL_VERIFY=%s, TOKEN=%s",
                splunk_url,
                cfg.get("SPLUNK_HEC_INDEX", "main"),
                cfg.get("SPLUNK_HEC_SOURCETYPE", "json"),
                cfg.get("SPLUNK_HEC_SSL_VERIFY", "true"),
                splunk_token if splunk_token else "NOT SET")

    if splunk_host and splunk_token:
        try:
            splunk = JSONSplunkHandler(
                host=splunk_host,
                port=int(cfg.get("SPLUNK_HEC_PORT", "8088")),
                token=splunk_token,
                index=cfg.get("SPLUNK_HEC_INDEX", "main"),
                sourcetype=cfg.get("SPLUNK_HEC_SOURCETYPE", "_json"),
                source=script_name,
                verify=cfg.get("SPLUNK_HEC_SSL_VERIFY", "true").lower() == "true",
                timeout=10,
            )
            splunk.setLevel(level)
            splunk.setFormatter(formatter)
            logger.addHandler(splunk)
            _splunk_handlers.append(splunk)
            _splunk_enabled = True
            logger.debug("JSONSplunkHandler attached (%s:%s)",
                         splunk_host, cfg.get("SPLUNK_HEC_PORT", "8088"))
        except Exception as e:
            logger.warning("Failed to create Splunk handler: %s", e)
    else:
        logger.debug("Splunk HEC not configured in .env -- console logging only")

    return logger


def flush_and_shutdown():
    """
    Flush all queued Splunk events and shut down logging.

    Call this at the very end of a script's execution to ensure
    no events are lost.
    """
    print(f"flush_and_shutdown called, _splunk_enabled={_splunk_enabled}, handlers={len(_splunk_handlers)}")
    if _splunk_enabled and _splunk_handlers:
        for i, handler in enumerate(_splunk_handlers):
            try:
                print(f"Flushing Splunk handler {i+1}/{len(_splunk_handlers)}...")
                handler.flush()
                handler.close()
                print(f"Splunk handler {i+1} flushed and closed")
            except Exception as e:
                print(f"Splunk flush error for handler {i+1}: {e}")
    
    logging.shutdown()
    print("logging.shutdown() completed")
