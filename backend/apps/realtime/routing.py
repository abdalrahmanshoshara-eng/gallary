from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/system/", consumers.SystemConsumer.as_asgi()),
    path("ws/me/", consumers.MeConsumer.as_asgi()),
]
