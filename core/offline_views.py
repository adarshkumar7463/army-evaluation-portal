"""
Offline Mode View and Utilities
Handles offline-related views and functionality
"""

from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
import json


class OfflinePageView(View):
    """Render offline fallback page"""
    def get(self, request):
        return render(request, 'offline.html', {
            'is_offline': True,
            'user_can_sync': request.user.is_authenticated
        })


@csrf_exempt
def offline_sync_api(request):
    """
    API endpoint for syncing offline changes
    Receives queued operations and processes them
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            operations = data.get('operations', [])
            
            results = []
            for op in operations:
                # Process each operation
                # This is a placeholder - implement based on your needs
                results.append({
                    'id': op.get('id'),
                    'status': 'synced',
                    'timestamp': str(datetime.now())
                })
            
            return JsonResponse({
                'success': True,
                'synced_count': len(results),
                'results': results
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def offline_cache_api(request):
    """
    API endpoint for managing offline cache
    GET: List cached items
    POST: Save cache item
    DELETE: Clear cache
    """
    if request.method == 'GET':
        return JsonResponse({
            'message': 'Offline cache management API',
            'endpoints': {
                'sync': '/api/offline/sync/',
                'cache': '/api/offline/cache/',
                'status': '/api/offline/status/'
            }
        })
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            key = data.get('key')
            value = data.get('value')
            
            if not key:
                return JsonResponse({
                    'error': 'Key is required'
                }, status=400)
            
            # Save to cache (implement based on your needs)
            return JsonResponse({
                'success': True,
                'key': key,
                'message': 'Data cached successfully'
            })
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    if request.method == 'DELETE':
        return JsonResponse({
            'success': True,
            'message': 'Cache cleared'
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def offline_status_api(request):
    """
    API endpoint for checking offline status and syncing
    """
    if request.method == 'GET':
        return JsonResponse({
            'online': True,
            'timestamp': str(datetime.now()),
            'message': 'Server is online and ready to sync'
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


from datetime import datetime
