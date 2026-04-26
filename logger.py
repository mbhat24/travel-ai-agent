"""
Structured Logging Module
Extreme Professional Grade Logging with JSON output, correlation IDs, and context
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional, Callable
from contextvars import ContextVar

# Context variable for request correlation ID
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')


class StructuredLogFormatter(logging.Formatter):
    """JSON structured log formatter for production environments"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': _correlation_id.get() or 'system',
        }
        
        # Add standard fields
        if hasattr(record, 'pathname'):
            log_data['file'] = f"{record.pathname}:{record.lineno}"
        
        if record.funcName:
            log_data['function'] = record.funcName
        
        # Add extra fields from record
        if hasattr(record, 'extras'):
            log_data.update(record.extras)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add any custom attributes
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'getMessage',
                'extras', 'correlation_id'
            }:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development environments"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        correlation = _correlation_id.get()
        corr_str = f" [{correlation[:8]}...]" if correlation else ""
        
        return f"{color}[{timestamp}] {record.levelname:8}{corr_str} {record.name}: {record.getMessage()}{self.RESET}"


class StructuredLogger:
    """Structured logger with context support"""
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        """Internal log method with context handling"""
        extra = kwargs.get('extra', {})
        extra['extras'] = {**self._context, **extra.get('extras', {})}
        extra['correlation_id'] = _correlation_id.get() or 'system'
        kwargs['extra'] = extra
        self._logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        kwargs['exc_info'] = True
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def with_context(self, **context):
        """Create a new logger with additional context"""
        new_logger = StructuredLogger(self._logger.name)
        new_logger._context = {**self._context, **context}
        return new_logger
    
    def bind(self, **context):
        """Bind context to this logger (alias for with_context)"""
        self._context.update(context)
        return self


def setup_logging(
    level: str = "INFO",
    structured: bool = True,
    include_timestamp: bool = True,
    log_file: Optional[str] = None
):
    """Setup structured logging for the application"""
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if structured:
        formatter = StructuredLogFormatter()
    else:
        formatter = ColoredFormatter()
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredLogFormatter())
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for the current context"""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    _correlation_id.set(correlation_id)
    return correlation_id


def get_correlation_id() -> str:
    """Get current correlation ID"""
    return _correlation_id.get() or str(uuid.uuid4())


def clear_correlation_id():
    """Clear the current correlation ID"""
    _correlation_id.set('')


def log_execution_time(logger: Optional[StructuredLogger] = None):
    """Decorator to log function execution time"""
    def decorator(func: Callable) -> Callable:
        log = logger or get_logger(func.__module__)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                log.debug(
                    f"Function {func.__name__} executed",
                    extra={'extras': {'duration_ms': duration * 1000, 'status': 'success'}}
                )
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                log.error(
                    f"Function {func.__name__} failed",
                    extra={'extras': {'duration_ms': duration * 1000, 'status': 'failed', 'error': str(e)}},
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


class LogContext:
    """Context manager for temporary log context"""
    
    def __init__(self, **context):
        self.context = context
        self._previous_context = {}
        self._logger = None
    
    def __enter__(self):
        self._previous_correlation = _correlation_id.get()
        for key, value in self.context.items():
            if key == 'correlation_id':
                _correlation_id.set(value)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _correlation_id.set(self._previous_correlation)
        return False


# Performance monitoring
class PerformanceTimer:
    """Context manager for timing operations"""
    
    def __init__(self, operation: str, logger: Optional[StructuredLogger] = None):
        self.operation = operation
        self.logger = logger or get_logger('performance')
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        log_level = 'error' if exc_type else 'info'
        getattr(self.logger, log_level)(
            f"Operation {self.operation} completed",
            extra={
                'extras': {
                    'operation': self.operation,
                    'duration_ms': duration * 1000,
                    'success': exc_type is None,
                    'error': str(exc_val) if exc_val else None
                }
            }
        )
        return False
    
    @property
    def elapsed_ms(self) -> float:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds() * 1000
        return 0.0
