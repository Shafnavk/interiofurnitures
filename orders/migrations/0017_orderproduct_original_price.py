# Generated by Django 5.1.5 on 2025-04-07 05:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0016_order_product_discount_alter_order_discount_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderproduct',
            name='original_price',
            field=models.FloatField(default=0),
        ),
    ]
