import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from ctxsnap.app_storage import app_dir
from ctxsnap.constants import APP_NAME

def setup_logging() -> Path:
    r"""Configure rotating file logs under %APPDATA%\ctxsnap\logs."""
    log_dir = app_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "ctxsnap.log"

    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.INFO)
    
    # clear existing handlers to avoid duplicates if called multiple times (though practically once)
    if not logger.handlers:
        handler = RotatingFileHandler(str(log_file), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        
        # Also log to stdout for dev if needed, or if no console attached it goes nowhere
        # console = logging.StreamHandler(sys.stdout)
        # console.setFormatter(fmt)
        # logger.addHandler(console)

    return log_file

def get_logger() -> logging.Logger:
    return logging.getLogger(APP_NAME)
