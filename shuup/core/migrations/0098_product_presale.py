# Generated by Django 2.2.18 on 2021-09-22 17:16

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('shuup', '0097_baselinkerproductlink_baselinkertoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_presale',
            field=models.BooleanField(default=False, verbose_name='Przedsprzedaż'),
        ),
    ]
