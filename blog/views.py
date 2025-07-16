from .serializers import RegisterSerializer
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (MyTokenObtainPairSerializer, UserProfileSerializer, VerifyEmailSerializer, DepositSerializer,
                          RecursiveCategorySerializer, OrderSerializer, OrderCreateSerializer, FaqSerializer,
                          ProductSerializer, FavoriteSerializer, BasketSerializer, CommentSerializer, PaymentSerializer)

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from rest_framework import generics
from .models import EmailVerification, Category, Product, Favorite, Basket, Comment, Order, Payment
from rest_framework import viewsets
from drf_yasg import openapi
from rest_framework import filters
import uuid
from django.db import transaction


class RegisterView(APIView):
    @swagger_auto_schema(
        operation_summary="Регистрация нового пользователя",
        request_body=RegisterSerializer,
        responses={
            201: RegisterSerializer,
            400: 'Ошибка валидации данных',
        },
        tags=['Аутентификация']
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response_serializer = RegisterSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    @swagger_auto_schema(
        request_body=VerifyEmailSerializer,
        responses={
            200: openapi.Response(description="Аккаунт успешно подтверждён"),
            400: openapi.Response(description="Неверный код или код истёк"),
        },
        operation_description="Подтверждение email с помощью кода",
        tags=["Аутентификация"]
    )
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']

        try:
            verification = EmailVerification.objects.get(code=code)
        except EmailVerification.DoesNotExist:
            return Response({"error": "Неверный код подтверждения"}, status=status.HTTP_400_BAD_REQUEST)

        if verification.is_expired():
            return Response({"error": "Код подтверждения истёк"}, status=status.HTTP_400_BAD_REQUEST)

        user = verification.user
        user.is_active = True
        user.save()
        verification.delete()

        return Response({"detail": "Аккаунт успешно подтверждён"})


@extend_schema(
    request=MyTokenObtainPairSerializer,
    responses={
        200: MyTokenObtainPairSerializer,
        401: None,  # Unauthorized
        400: None,  # Bad request
    },
    tags=["Аутентификация"],
    description="Получение access и refresh токенов по email и паролю"
)
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "refresh": {
                    "type": "string",
                    "example": "your_refresh_token_here"
                }
            },
            "required": ["refresh"]
        }
    },
    responses={
        205: OpenApiTypes.STR,
        400: OpenApiTypes.OBJECT,
    },
    tags=["Аутентификация"],
    description="Logout: делает refresh токен недействительным (blacklist). Требуется refresh токен.",
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Выход из системы (blacklist refresh токена)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refresh'],
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh токен')
            },
        ),
        responses={
            205: openapi.Response(description="Вы успешно вышли из системы"),
            400: openapi.Response(description="Ошибка: отсутствует или неверный токен"),
        },
        tags=["Аутентификация"],
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh token обязателен"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"detail": "Вы вышли из системы"}, status=status.HTTP_205_RESET_CONTENT)

        except TokenError:
            return Response({"error": "Неверный токен или уже использован"}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    @swagger_auto_schema(
        operation_summary="Получить профиль пользователя",
        responses={200: UserProfileSerializer},
        tags=["Профиль"]
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=UserProfileSerializer,
        operation_summary="Обновить профиль пользователя",
        responses={200: UserProfileSerializer},
        tags=["Профиль"]
    )
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=UserProfileSerializer,
        operation_summary="Частично обновить профиль пользователя",
        responses={200: UserProfileSerializer},
        tags=["Профиль"]
    )
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Удалить аккаунт пользователя",
        responses={204: "Пользователь удалён"},
        tags=["Профиль"]
    )
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class BalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DepositSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        user = request.user
        return Response({'balance': user.balance}, status=status.HTTP_200_OK)




class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(parent__isnull=True)
    serializer_class = RecursiveCategorySerializer

    @swagger_auto_schema(tags=['Категории'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Категории'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Категории'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Категории'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Категории'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Категории'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    @swagger_auto_schema(tags=['Продукты'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Продукты'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Продукты'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Продукты'])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Продукты'])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(tags=['Продукты'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Список избранных продуктов пользователя",
        tags=["Избранное"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Добавить продукт в избранное",
        tags=["Избранное"],
        request_body=FavoriteSerializer,
        responses={201: FavoriteSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Удалить избранное по ID",
        tags=["Избранное"],
        responses={204: "Удалено"},
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['delete'], url_path='remove/(?P<product_id>[^/.]+)')
    @swagger_auto_schema(
        operation_summary="Удалить из избранного по ID продукта",
        tags=["Избранное"],
        responses={204: "Удалено", 404: "Не найдено"},
    )
    def remove_by_product(self, request, product_id=None):
        try:
            fav = Favorite.objects.get(user=request.user, product__id=product_id)
            fav.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Favorite.DoesNotExist:
            return Response({"detail": "Продукт не найден в избранном."}, status=status.HTTP_404_NOT_FOUND)


class BasketViewSet(viewsets.ModelViewSet):
    serializer_class = BasketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Basket.objects.filter(user=self.request.user)
        return Basket.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @swagger_auto_schema(
        operation_summary="Получить список товаров в корзине",
        tags=["Корзина"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Добавить товар в корзину",
        tags=["Корзина"]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Удалить товар из корзины",
        tags=["Корзина"]
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Получить список комментариев (фильтр по product_id необязателен)",
        manual_parameters=[
            openapi.Parameter(
                name='product_id',
                in_=openapi.IN_QUERY,
                description='ID продукта для фильтрации комментариев',
                type=openapi.TYPE_INTEGER,
                required=False,
            )
        ],
        tags=["Комментарии"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Добавить новый комментарий к продукту",
        tags=["Комментарии"],
        request_body=CommentSerializer,
        responses={201: CommentSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Получить комментарий по ID",
        tags=["Комментарии"],
        responses={200: CommentSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        product_id = self.request.query_params.get('product_id')
        queryset = Comment.objects.all()
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).select_related('user')


    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            order = serializer.save()
            read_serializer = OrderSerializer(order, context={'request': request})
            return Response(read_serializer.data, status=status.HTTP_201_CREATED)



class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    queryset = Payment.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            payment = serializer.save(user=request.user)
            response_data = self.get_serializer(payment).data

            if response_data.get("requires_confirmation"):
                return Response({
                    "message": "Недостаточно средств. Платёж ожидает подтверждения карты.",
                    "payment": response_data
                }, status=status.HTTP_200_OK)

            return Response(response_data, status=status.HTTP_201_CREATED)



class PaymentConfirmationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('payment_id')
        confirmation_code = request.data.get('confirmation_code')

        if not payment_id or not confirmation_code:
            return Response({"detail": "payment_id и confirmation_code обязательны."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
        except Payment.DoesNotExist:
            return Response({"detail": "Платёж не найден."},
                            status=status.HTTP_404_NOT_FOUND)

        if payment.confirmation_code != confirmation_code:
            return Response({"detail": "Неверный код подтверждения."},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            payment.is_confirmed = True
            payment.status = 'paid'
            payment.save()

        return Response({"detail": "Платёж подтверждён."},
                        status=status.HTTP_200_OK)


class FaqViewSet(viewsets.ModelViewSet):
    serializer_class = FaqSerializer