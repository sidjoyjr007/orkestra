import logging
import json
from datetime import datetime
import sys

class JSONFormatter(logging.Formatter):
    """
    Standardizes log output to JSON format, allowing external systems 
    (Datadog, ELK, CloudWatch) to easily parse Orkestra's telemetry.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage()
        }
        
        # Capture any extra structured kwargs passed during logging
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

def setup_telemetry(level: int = logging.INFO):
    """
    Configures the root logger to use Orkestra's JSONFormatter.
    This should be called once by the framework consumer.
    """
    root_logger = logging.getLogger()
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

def get_logger(name: str) -> logging.Logger:
    """Wrapper to easily get a structured logger."""
    return logging.getLogger(name)
