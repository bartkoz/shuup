# Generated by Django 2.2.18 on 2021-07-16 09:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shuup', '0091_background_tasks'),
    ]

    operations = [
        migrations.CreateModel(
            name='BaseLinkerToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=100)),
                ('shop', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bl_token', to='shuup.Shop')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='BaseLinkerProductLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bl_id', models.IntegerField()),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bl_product_link', to='shuup.Product')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
