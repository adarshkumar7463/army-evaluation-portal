"""
Logs App - Middleware
"""


class ActivityLogMiddleware:
    """
    Middleware to track user activity.
    Only logs specific page views to avoid noise.
    """
    TRACK_PATHS = ['/reports/', '/evaluation/', '/departments/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
