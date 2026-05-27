"""
URL configuration for breathe_esg project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
import os
from django.http import HttpResponse
from django.conf import settings

def serve_react(request):
    # In production, serve the built React index.html from static folder
    index_path = os.path.join(settings.BASE_DIR, 'static', 'index.html')
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='text/html')
    else:
        return HttpResponse(
            "<div style='font-family: system-ui, sans-serif; text-align: center; padding: 4rem;'>"
            "  <h1 style='color: #059669;'>🍃 Breathe ESG Platform Backend</h1>"
            "  <p style='font-size: 1.2rem; color: #4b5563;'>The Django REST API is running successfully!</p>"
            "  <p style='color: #6b7280;'>To view the analyst review dashboard, start the Vite development server in the <code>frontend/</code> directory or run a production build using <code>npm run build</code>.</p>"
            "  <div style='margin-top: 2rem; padding: 1rem; background: #f3f4f6; display: inline-block; border-radius: 8px; text-align: left;'>"
            "    <strong>Available API Endpoints:</strong>"
            "    <ul style='margin-top: 0.5rem;'>"
            "      <li>Ingestion Upload: <a href='/api/ingestion/upload/'>/api/ingestion/upload/</a></li>"
            "      <li>Records Ledger: <a href='/api/records/'>/api/records/</a></li>"
            "      <li>Aggregation Analytics: <a href='/api/analytics/'>/api/analytics/</a></li>"
            "    </ul>"
            "  </div>"
            "</div>"
        )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('ingestion.urls')),
    re_path(r'^.*$', serve_react, name='react-frontend'),
]

