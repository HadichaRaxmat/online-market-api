from random import random

from django.db import transaction
from rest_framework import serializers
from .models import CustomUser
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from .models import EmailVerification, Category, Product, Favorite, Basket, Comment, Order, OrderItem, Payment, Faq
from .utils import send_verification_email


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = ('email', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует")
        return value

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password']
        )
        EmailVerification.objects.create(user=user)
        send_verification_email(user)
        return user


class VerifyEmailSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(request=self.context.get("request"), email=email, password=password)
        if not user:
            raise serializers.ValidationError("Неверный email или пароль")

        data = super().validate({
            self.username_field: email,
            "password": password
        })
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'balance']
        read_only_fields = ['balance']

    def validate_email(self, value):
        user = self.instance
        if CustomUser.objects.exclude(pk=user.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует")
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        email = validated_data.get('email', instance.email)

        instance.email = email

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    card_number = serializers.CharField(write_only=True, max_length=16)
    card_expiry = serializers.CharField(write_only=True, max_length=5)
    card_cvv = serializers.CharField(write_only=True, max_length=4, required=False)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть положительной.")
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        amount = self.validated_data['amount']

        payment = Payment.objects.create(
            user=user,
            amount=amount,
            payment_type='balance_replenishment',
            status='paid',
            is_confirmed=True,
            card_number=self.validated_data.get('card_number'),
            card_expiry=self.validated_data.get('card_expiry'),
            card_cvv=self.validated_data.get('card_cvv', ''),
        )

        user.deposit(amount)
        return payment



class RecursiveCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    parent = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Category.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'parent', 'children']

    def get_children(self, obj):
        if obj.children.exists():
            return RecursiveCategorySerializer(obj.children.all(), many=True).data
        return []


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    rating = serializers.IntegerField(required=False, min_value=1, max_value=5, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Comment
        fields = ['id', 'user', 'product_id', 'comment', 'rating', 'image', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Category.objects.all()
    )
    product_count = serializers.IntegerField(required=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'image', 'price', 'category', 'description', 'sold_count', 'product_count',
                  'created_at', 'updated_at', 'comments', ]
        read_only_fields = ['id', 'sold_count', 'created_at', 'updated_at']

    def validate_category(self, value):
        if value.children.exists():
            raise serializers.ValidationError("Выберите подкатегорию, а не родительскую категорию.")
        return value


class FavoriteSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Favorite
        fields = ['id', 'product', 'product_id', 'added_at']
        read_only_fields = ['id', 'product', 'added_at']


class BasketSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = Basket
        fields = ['id', 'product', 'product_id', 'quantity', 'added_at']
        read_only_fields = ['id', 'added_at']

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']
        quantity = validated_data.get('quantity', 1)

        basket_item, created = Basket.objects.update_or_create(
            user=user,
            product=product,
            defaults={'quantity': quantity}
        )
        return basket_item


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'total_price', 'status', 'created_at', 'expires_at', 'items']
        read_only_fields = ['id', 'user', 'total_price', 'status', 'created_at', 'expires_at', 'items']


class OrderCreateSerializer(serializers.Serializer):
    basket_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )

    def validate_basket_ids(self, value):
        user = self.context['request'].user
        baskets = Basket.objects.filter(id__in=value, user=user)
        if baskets.count() != len(value):
            raise serializers.ValidationError("Некоторые элементы корзины не найдены или не принадлежат пользователю.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        basket_ids = validated_data['basket_ids']
        baskets = Basket.objects.filter(id__in=basket_ids, user=user)

        with transaction.atomic():
            total_price = sum(b.product.price * b.quantity for b in baskets)

            order = Order.objects.create(user=user, total_price=total_price, status='pending')

            order_items = []
            for basket_item in baskets:
                product = basket_item.product
                if product.product_count < basket_item.quantity:
                    raise serializers.ValidationError(f"Товара {product.name} недостаточно на складе.")

                order_items.append(OrderItem(
                    order=order,
                    product=product,
                    quantity=basket_item.quantity,
                    price=product.price
                ))


                product.product_count -= basket_item.quantity
                product.sold_count += basket_item.quantity
                product.save()

            OrderItem.objects.bulk_create(order_items)
            baskets.delete()
            return order



class PaymentSerializer(serializers.ModelSerializer):
    confirmation_code = serializers.CharField(read_only=True)
    requires_confirmation = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ['id', 'confirmation_code', 'card_number', 'card_expiry', 'card_cvv', 'requires_confirmation', 'expires_at']
        extra_kwargs = {
            'card_number': {'write_only': True, 'required': False},
            'card_expiry': {'write_only': True, 'required': False},
            'card_cvv': {'write_only': True, 'required': False},
        }

    def get_requires_confirmation(self, obj):
        return not obj.is_confirmed

    def create(self, validated_data):
        user = self.context['request'].user

        with transaction.atomic():

            try:
                order = Order.objects.filter(user=user, status='pending').latest('created_at')
            except Order.DoesNotExist:
                raise serializers.ValidationError("Нет активного заказа для оплаты.")

            amount = order.total_price

            # 1. Попытка списать с баланса
            if user.balance >= amount:
                user.charge(amount)
                return Payment.objects.create(
                    user=user,
                    order=order,
                    amount=amount,
                    status='paid',
                    is_confirmed=True,
                    payment_type='order_payment',
                    card_number='',
                    card_expiry='',
                    card_cvv=''
                )

            # 2. Проверка наличия карты, если не хватает средств
            card_number = validated_data.get('card_number')
            card_expiry = validated_data.get('card_expiry')
            card_cvv = validated_data.get('card_cvv')

            if not all([card_number, card_expiry, card_cvv]):
                raise serializers.ValidationError({
                    "detail": "Недостаточно средств и не указаны данные карты.",
                    "required_fields": ["card_number", "card_expiry", "card_cvv"]
                })

            # 3. Создаём платёж в статусе 'pending'
            payment = Payment.objects.create(
                user=user,
                order=order,
                amount=amount,
                card_number=card_number,
                card_expiry=card_expiry,
                card_cvv=card_cvv,
                status='pending',
                payment_type='order_payment'
            )

            payment.generate_confirmation_code()
            payment.save()
            return payment


class PaymentConfirmationSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    confirmation_code = serializers.CharField(max_length=6)

    def validate(self, data):
        try:
            payment = Payment.objects.get(id=data['payment_id'])
        except Payment.DoesNotExist:
            raise serializers.ValidationError("Платеж не найден.")

        if payment.is_confirmed:
            raise serializers.ValidationError("Платёж уже подтверждён.")

        if payment.confirmation_code != data['confirmation_code']:
            raise serializers.ValidationError("Неверный код подтверждения.")

        data['payment'] = payment
        return data

    def save(self, **kwargs):
        with transaction.atomic():
            payment = self.validated_data['payment']
            payment.is_confirmed = True
            payment.status = 'paid'
            payment.save()
            return payment


class FaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faq
        fields = ['id', 'ask', 'answer']


