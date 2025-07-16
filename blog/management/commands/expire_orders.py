from django.core.management.base import BaseCommand
from django.utils import timezone
from blog.models import Order, Payment


class Command(BaseCommand):
    help = 'Cancelled expired orders and payments'

    def handle(self, *args, **options):
        now = timezone.now()
        expired_orders = Order.objects.filter(status='pending', expires_at__lt=now)
        cancelled_count = 0

        for order in expired_orders:
            for item in order.items.all():
                product = item.product
                product.product_count -= item.quantity
                product.save()

            order.status = 'cancelled'
            order.save()

            Payment.objects.filter(order=order, status='pending').update(status='cancelled')

            cancelled_count += 1

        self.stdout.write(self.style.SUCCESS(f"Cancelled : {cancelled_count}"))