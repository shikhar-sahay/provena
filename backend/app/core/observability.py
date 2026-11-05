"""Bounded structured request diagnostics without paths, credentials or evidence."""
import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger=logging.getLogger('provena.operations')
request_context=ContextVar('provena_request_id',default=None)
if not logger.handlers:
    handler=logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class RequestDiagnostics(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        incoming=request.headers.get('X-Request-ID','')
        request_id=incoming if re.fullmatch('[A-Za-z0-9_-]{1,64}',incoming) else uuid.uuid4().hex
        request.state.request_id=request_id
        context_token=request_context.set(request_id)
        started=time.perf_counter()
        try:
            response=await call_next(request)
            category='server_error' if response.status_code>=500 else 'rejected' if response.status_code>=400 else 'completed'
            response.headers['X-Request-ID']=request_id
            return response
        except Exception:
            category='unhandled_error'
            return JSONResponse(status_code=503,content={'detail':'An internal operation failed. Inspect operation history before retrying.'},headers={'X-Request-ID':request_id})
        finally:
            # Route template only, never query strings, raw source paths or request bodies.
            route=getattr(request.scope.get('route'),'path','unmatched')
            logger.info(json.dumps({'operation':'http_request','request_id':request_id,'method':request.method,
                'route':route,'outcome':category,'duration_ms':round((time.perf_counter()-started)*1000,2)}))
            request_context.reset(context_token)
