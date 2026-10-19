from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.upcoming, name="upcoming"),
    path("tasks/<int:pk>/done/", views.mark_done, name="mark_done"),
]
