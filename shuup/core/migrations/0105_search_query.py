# Generated by Django 2.2.18 on 2022-02-06 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shuup', '0104_baselinkertoken_old_new_system'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchQuery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
