# Generated by Django 5.1.5 on 2025-03-22 07:56

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_alter_order_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='carrier',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='estimated_delivery_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='tracking_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.CreateModel(
            name='TrackingUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('Order Placed', 'Order Placed'), ('Processing', 'Processing'), ('Shipped', 'Shipped'), ('In Transit', 'In Transit'), ('Out for Delivery', 'Out for Delivery'), ('Delivered', 'Delivered')], max_length=50)),
                ('location', models.CharField(blank=True, max_length=100, null=True)),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('description', models.TextField(blank=True, null=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tracking_updates', to='orders.order')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
    ]
