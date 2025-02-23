# Generated by Django 2.2.18 on 2021-07-19 06:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shuup', '0096_auto_20210909_1041'),
    ]

    operations = [
        migrations.CreateModel(
            name='BaseLinkerToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=100)),
                ('storage', models.CharField(max_length=20)),
                ('order_status_id', models.CharField(max_length=50, default='changeme')),
                ('shop', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bl_token', to='shuup.Supplier')),
            ],
            options={
                'abstract': False,
            },
        ),
        ]
