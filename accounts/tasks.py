from celery import shared_task

from . import reminders


@shared_task
def send_birthday_reminders():
    return reminders.send_birthday_reminders()
