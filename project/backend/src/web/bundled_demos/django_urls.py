from django.urls import path

from monitoring import views

urlpatterns = [
    path('health/', views.health),
    path('boom/', views.boom),
    path('', views.health),
]
