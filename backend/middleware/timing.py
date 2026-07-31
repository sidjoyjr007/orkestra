import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from backend.core.logging import get_logger

logger = get_logger("api.timing")

class TimingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that tracks the execution time of every request.
    Injects a unique request_id for distributed tracing.
    """
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        
        # Attach request_id to the request state so routes can access it
        request.state.request_id = request_id
        
        start_time = time.time()
        
        # Bind the request_id to all logs emitted within this scope
        log = logger.bind(request_id=request_id, path=request.url.path, method=request.method)
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Add custom header for clients
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = request_id
            
            log.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2)
            )
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            log.error(
                "request_failed",
                error=str(e),
                duration_ms=round(process_time * 1000, 2)
            )
            raise e
