from django.http import JsonResponse


def health(request):
    return JsonResponse({'ok': True})


def boom(request):
    raise RuntimeError('тестовая ошибка Django MVP для Error Monitor SDK')
