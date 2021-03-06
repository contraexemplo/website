# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-06-07 23:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0155_auto_20190523_1558_squashed_0156_auto_20190523_1558'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='new_contributors_welcome',
            field=models.BooleanField(choices=[(True, 'My project is open to new contributors'), (False, 'My project already has many strong applicants')], default=True, verbose_name='Is your project open to new contributors?'),
        ),
    ]
