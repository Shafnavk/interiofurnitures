# Generated by Django 5.1.5 on 2025-02-12 05:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0012_remove_product_discount_percentage'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='max_quantity',
            field=models.PositiveIntegerField(default=5),
        ),
    ]
