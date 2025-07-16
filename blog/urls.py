from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from . import views
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter


schema_view = get_schema_view(
    openapi.Info(
        title="User Registration API",
        default_version='v1',
        description="API для регистрации пользователя",
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)



router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='categories'),
router.register(r'products', views.ProductViewSet, basename='product'),
router.register(r'favorites', views.FavoriteViewSet, basename='favorite'),
router.register(r'basket', views.BasketViewSet, basename='basket'),
router.register(r'comments', views.CommentViewSet, basename='comment'),
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'payments', views.PaymentViewSet, basename='payment')


urlpatterns = [
    path('api/register/', views.RegisterView.as_view(), name='register'),
    path('verify/email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('api/token/', views.TokenObtainPairView.as_view(), name='api_token'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/logout/', views.LogoutView.as_view(), name='logout'),
    path('payments/confirm/', views.PaymentConfirmationAPIView.as_view(), name='payment-confirmation'),
    path('api/balance/', views.BalanceView.as_view(), name='balance-top-up'),

    path('api/', include(router.urls)),



    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
