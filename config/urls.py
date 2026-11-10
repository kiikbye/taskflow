from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from accounts import views as account_views
from queueing import api, views

router = DefaultRouter()
router.register("batches", api.BatchViewSet)

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("batches/new/", views.new_batch, name="new_batch"),
    path("batches/<int:pk>/rename/", views.rename_batch, name="rename_batch"),
    path("batches/<int:pk>/publish/", views.publish, name="publish"),
    path("signup/", account_views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", account_views.profile, name="profile"),
    path("profile/logout-all/", account_views.logout_everywhere, name="logout_everywhere"),
    path("admin/", admin.site.urls),
    path("api/token/", obtain_auth_token, name="api_token"),
    path("api/jwt/", TokenObtainPairView.as_view(), name="api_jwt"),
    path("api/jwt/refresh/", TokenRefreshView.as_view(), name="api_jwt_refresh"),
    path("api/jwt/logout/", TokenBlacklistView.as_view(), name="api_jwt_logout"),
    path("api/me/", api.me, name="api_me"),
    path("api/", include(router.urls)),
]

admin.site.site_header = "TaskFlow әкімші панелі"
admin.site.site_title = "TaskFlow"
