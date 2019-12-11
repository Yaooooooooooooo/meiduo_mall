from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meiduo_mall.settings.dev")

celery_apps = Celery('meiduo')


celery_apps.config_from_object('celery_tasks.config')

celery_apps.autodiscover_tasks(['celery_tasks.sms', 'celery_tasks.email'])