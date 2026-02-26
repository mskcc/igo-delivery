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

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_config = None          # Loaded .env values (dict)
_splunk_enabled = False # Whether SplunkHandler was attached


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
            from splunk_handler import SplunkHandler

            splunk = SplunkHandler(
                host=splunk_host,
                port=int(cfg.get("SPLUNK_HEC_PORT", "8088")),
                token=splunk_token,
                index=cfg.get("SPLUNK_HEC_INDEX", "main"),
                sourcetype=cfg.get("SPLUNK_HEC_SOURCETYPE", "_json"),
                source=script_name,
                verify=cfg.get("SPLUNK_HEC_SSL_VERIFY", "true").lower() == "true",
                flush_interval=float(cfg.get("SPLUNK_FLUSH_INTERVAL", "5.0")),
                queue_size=int(cfg.get("SPLUNK_QUEUE_SIZE", "5000")),
                timeout=10,  # 10 second connection timeout
                record_format=True,  # Send as JSON object: {"event": {"message": "..."}, ...}
                debug=True,  # Log payloads to console
            )
            splunk.setLevel(level)
            logger.addHandler(splunk)
            _splunk_enabled = True
            logger.debug("Splunk HEC handler attached (%s:%s)",
                         splunk_host, cfg.get("SPLUNK_HEC_PORT", "8088"))
        except ImportError:
            logger.warning(
                "splunk_handler package not installed -- "
                "Splunk logging disabled. Install with: pip install splunk_handler"
            )
    else:
        logger.debug("Splunk HEC not configured in .env -- console logging only")

    return logger


def flush_and_shutdown():
    """
    Flush all queued Splunk events and shut down logging.

    Call this at the very end of a script's execution to ensure
    no events are lost.
    """
    print(f"flush_and_shutdown called, _splunk_enabled={_splunk_enabled}")
    if _splunk_enabled:
        try:
            from splunk_handler import force_flush
            print("Calling force_flush()...")
            force_flush()
            print("force_flush() completed")
        except Exception as e:
            print(f"Splunk flush error: {e}")
    
    logging.shutdown()
    print("logging.shutdown() completed")
