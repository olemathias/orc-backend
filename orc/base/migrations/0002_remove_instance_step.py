# Generated by Django 4.1.7 on 2023-03-11 00:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='instance',
            name='step',
        ),
    ]
