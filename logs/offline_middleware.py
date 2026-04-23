"""
Offline Mode Middleware
Handles offline detection and offline-related HTTP headers
"""

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
import json


class OfflineModeMiddleware(MiddlewareMixin):
    """
    Middleware to support offline mode functionality
    - Sets headers for offline detection
    - Handles offline requests gracefully
    - Caches responses for offline use
    """

    def process_request(self, request):
        """Process incoming request"""
        # Mark request if it's from offline mode
        request.is_offline_request = request.META.get('HTTP_X_OFFLINE_MODE') == 'true'
        return None

    def process_response(self, request, response):
        """Process outgoing response"""
        # Add offline support headers
        if response.status_code == 200:
            # Allow caching for GET requests
            if request.method == 'GET':
                response['Cache-Control'] = 'public, max-age=3600'
                response['X-Cache-Control'] = 'offline-enabled'
            
            # Add offline detection header
            response['X-Offline-Capable'] = 'true'
            response['Service-Worker-Allowed'] = '/'
        
        # Add CORS headers for offline sync
        response['Access-Control-Allow-Origin'] = '*'
        
        return response

    def process_exception(self, request, exception):
        """Handle exceptions - useful for offline scenarios"""
        if request.is_offline_request:
            return HttpResponse(
                json.dumps({'error': 'Offline', 'offline': True}),
                status=503,
                content_type='application/json'
            )
        return None


class OfflineFormMiddleware(MiddlewareMixin):
    """
    Middleware to add offline form support
    Marks forms that should be queued when offline
    """

    def process_response(self, request, response):
        """Add offline markers to form submissions"""
        if request.method == 'POST' and 'form' in response.content.decode('utf-8', errors='ignore'):
            # This is handled in templates with data-offline-queue attribute
            pass
        return response
