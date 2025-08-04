from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone
from django.db import models
from django.conf import settings
from datetime import timedelta
import random
from tkinter.constants import CASCADE
from django.db.models import CASCADE
from blog.basequeryset import CustomSQLManager

def get_expiration(minutes):
    return timezone.now() + timedelta(minutes=minutes)

def get_order_expiration():
    return get_expiration(minutes=1)

def get_payment_expiration():
    return get_expiration(minutes=2)



class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        if 'is_active' not in extra_fields:
            extra_fields['is_active'] = False
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class CustomUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    balance = models.DecimalField(default=0.00, max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def _change_balance(self, amount):
        self.balance += amount
        self.save(update_fields=['balance'])

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной.")
        self._change_balance(amount)

    def charge(self, amount):
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной.")
        if self.balance < amount:
            raise ValueError("Недостаточно средств на балансе.")
        self._change_balance(-amount)


class EmailVerification(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    @staticmethod
    def generate_code():
        return str(random.randint(100000, 999999))


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название продукта")
    image = models.ImageField(
        upload_to='product_images/',
        default='product_images/about-img.jpg',
        verbose_name="Фото"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")

    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='products',
                                 verbose_name='Категория')
    description = models.TextField(verbose_name="Описание / Отзыв")
    sold_count = models.PositiveIntegerField(default=0, verbose_name="Сколько продано")
    product_count = models.PositiveIntegerField(verbose_name="в наличии", null=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return self.name


class Favorite(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        verbose_name = "Избранное"
        verbose_name_plural = "Избранные"

    def __str__(self):
        return f"{self.user.email} → {self.product.name}"


class Basket(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="baskets")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="baskets_by")
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        verbose_name = "Корзинка"
        verbose_name_plural = "Корзинки"

    def __str__(self):
        return f"{self.user.email} — {self.product.name} x{self.quantity}"


class Comment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='comments')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    comment = models.TextField()
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    image = models.ImageField(upload_to='comment_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} — {self.product.name} — {self.rating or 'No rating'}"


class Order(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('pending', 'Ожидание'), ('paid', 'Оплачен')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_order_expiration)

    objects = CustomSQLManager()


    def __str__(self):
        return f"Order {self.id} — {self.user.email} — {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидается'),
        ('paid', 'Оплачено'),
        ('failed', 'Не удалось'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('order_payment', 'Оплата заказа'),
        ('balance_replenishment', 'Пополнение баланса'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    card_number = models.CharField(max_length=16, null=True, blank=True)
    card_expiry = models.CharField(max_length=5, null=True, blank=True)
    card_cvv = models.CharField(max_length=4, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    confirmation_code = models.CharField(max_length=6, blank=True)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_payment_expiration)
    payment_type = models.CharField(
        max_length=25,
        choices=PAYMENT_TYPE_CHOICES,
        default='order_payment'
    )

    def __str__(self):
        return f"{self.user.email} — {self.amount} — {self.status}"

    def generate_confirmation_code(self):
        self.confirmation_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])


class Faq(models.Model):
    ask = models.TextField()
    answer = models.TextField()

    def __str__(self):
        return self.ask
