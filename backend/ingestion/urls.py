from django.urls import path
from .views import (
    IngestionUploadView,
    ActivityRecordListView,
    ActivityRecordActionView,
    ActivityRecordEditView,
    ESGAnalyticsView
)

urlpatterns = [
    path('ingestion/upload/', IngestionUploadView.as_view(), name='ingestion-upload'),
    path('records/', ActivityRecordListView.as_view(), name='records-list'),
    path('records/<int:pk>/edit/', ActivityRecordEditView.as_view(), name='record-edit'),
    path('records/<int:pk>/<str:action>/', ActivityRecordActionView.as_view(), name='record-action'),
    path('analytics/', ESGAnalyticsView.as_view(), name='analytics-summary'),
]
