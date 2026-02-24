from flask import request, g
import sys
from ..client import _client, track_event

def enable_flask_integration(app, user_id_func=None):

    @app.errorhandler(Exception)
    def handle_exception(e):
        if _client is None:
            app.logger.warning("ErrorMonitor SDK not initialized. Call init_monitor() first.")
            raise
        user_id = "anonymous"
        if user_id_func:
            try:
                user_id = user_id_func()
            except:
                pass

        track_event(
            user_id=user_id,
            action="flask_unhandled_exception",
            metadata={
                "path": request.path,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "exception_type": type(e).__name__,
                "message": str(e),
                "traceback": "".join(__import__("traceback").format_exception(*sys.exc_info()))
            }
        )
        raise