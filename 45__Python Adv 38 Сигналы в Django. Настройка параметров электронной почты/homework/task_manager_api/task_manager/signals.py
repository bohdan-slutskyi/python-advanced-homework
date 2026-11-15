"""Уведомление владельца о фактическом изменении статуса основной задачи."""

from functools import partial

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Task


@receiver(pre_save, sender=Task, dispatch_uid="task_track_previous_status")
def track_previous_task_status(sender, instance, raw=False, using=None, update_fields=None, **kwargs):
    # Запоминать предыдущее значение нужно ДО сохранения новой версии в БД.
    instance._previous_status_for_email = None
    if raw or instance._state.adding or (update_fields is not None and "status" not in update_fields):
        return

    previous_status = (
        sender._base_manager.using(using).filter(pk=instance.pk)
        .values_list("status", flat=True).first()
    )
    if previous_status is not None and previous_status != instance.status:
        instance._previous_status_for_email = previous_status


@receiver(post_save, sender=Task, dispatch_uid="task_email_on_status_change")
def notify_task_owner(sender, instance, created, raw=False, using=None, **kwargs):
    previous_status = getattr(instance, "_previous_status_for_email", None)
    if hasattr(instance, "_previous_status_for_email"):
        del instance._previous_status_for_email

    if created or raw or previous_status is None or instance.owner_id is None:
        return

    # Без адреса владельца письмо не отправляется; другие пользователи не уведомляются.
    recipient = instance.owner.email.strip() if instance.owner.email else ""
    if not recipient:
        return

    old_label = dict(Task._meta.get_field("status").choices).get(
        previous_status, previous_status
    )
    new_label = instance.get_status_display()
    task_id = instance.pk
    subject = f"Статус задачи #{task_id} изменён: {new_label}"
    message = (
        f"Задача: {instance.title} (#{task_id})\n"
        f"Предыдущий статус: {old_label}\n"
        f"Новый статус: {new_label}\n"
        + ("Задача закрыта.\n" if instance.status == "done" else "")
    )

    # Если транзакция откатится, уведомление не должно уйти.
    transaction.on_commit(
        partial(
            send_mail,
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
        ),
        using=using,
    )
