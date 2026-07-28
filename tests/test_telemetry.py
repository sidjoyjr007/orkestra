import pytest
import logging
import json
import sys
from orkestra.core.telemetry import JSONFormatter, setup_telemetry, get_logger

def test_json_formatter_basic():
    formatter = JSONFormatter()
    record = logging.LogRecord("test_logger", logging.INFO, "path.py", 10, "Test message", None, None)
    
    output = formatter.format(record)
    parsed = json.loads(output)
    
    assert parsed["level"] == "INFO"
    assert parsed["component"] == "test_logger"
    assert parsed["message"] == "Test message"
    assert "timestamp" in parsed

def test_json_formatter_with_extra():
    formatter = JSONFormatter()
    record = logging.LogRecord("test_logger", logging.INFO, "path.py", 10, "Test message", None, None)
    record.extra_data = {"user_id": "123", "action": "test"}
    
    output = formatter.format(record)
    parsed = json.loads(output)
    
    assert parsed["user_id"] == "123"
    assert parsed["action"] == "test"

def test_json_formatter_with_exception():
    formatter = JSONFormatter()
    try:
        1 / 0
    except ZeroDivisionError:
        exc_info = sys.exc_info()
        
    record = logging.LogRecord("test_logger", logging.ERROR, "path.py", 10, "Error occurred", None, exc_info)
    
    output = formatter.format(record)
    parsed = json.loads(output)
    
    assert parsed["level"] == "ERROR"
    assert "ZeroDivisionError" in parsed["exception"]

def test_setup_telemetry():
    # Keep original handlers
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    
    setup_telemetry(logging.DEBUG)
    
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0], logging.StreamHandler)
    assert isinstance(root.handlers[0].formatter, JSONFormatter)
    
    # Restore original handlers
    root.handlers = original_handlers

def test_get_logger():
    logger = get_logger("my_custom_logger")
    assert logger.name == "my_custom_logger"
    assert isinstance(logger, logging.Logger)
