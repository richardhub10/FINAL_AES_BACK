"""
URL configuration for ua_clinic_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from django.http import JsonResponse
from django.urls import include, path

from rest_framework_simplejwt.views import TokenRefreshView

from clinic.auth import EmailOrUsernameTokenObtainPairView


def healthz(_request):  # noqa: ANN001
    # Simple health check endpoint (used by Render and for quick manual testing).
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('', healthz, name='root'),
    path('healthz/', healthz, name='healthz'),
    path('admin/', admin.site.urls),
    path('api/', include('clinic.urls')),
    path('api/auth/token/', EmailOrUsernameTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
