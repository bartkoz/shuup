# Generated by Django 2.2.18 on 2021-07-21 13:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shuup', '0092_baselinkerproductlink_baselinkertoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='baselinker_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
