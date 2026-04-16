from django.urls import path
from .views import ReceiveSMSView, OutgoingSMSView, SMSSentView
urlpatterns = [
    path('receive/', ReceiveSMSView.as_view()),
    path('outgoing/', OutgoingSMSView.as_view()),
    path('sent/', SMSSentView.as_view()),
]
