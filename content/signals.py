"""Signal handlers to delete unused image files when content models change."""

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Attraction, RoomType


def _delete_unused_image(model_class, file_field, exclude_pk=None):
    """Delete an image file from storage if no other model row references it."""
    if not file_field or not file_field.name:
        return

    qs = model_class.objects.filter(image=file_field.name)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        return

    storage = file_field.storage
    if storage.exists(file_field.name):
        storage.delete(file_field.name)


@receiver(pre_save, sender=RoomType)
@receiver(pre_save, sender=Attraction)
def delete_replaced_image_on_save(sender, instance, **kwargs):
    """Remove the previous image file when a RoomType or Attraction image is replaced or cleared."""
    if not instance.pk:
        return

    try:
        previous = sender.objects.only('image').get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_image = previous.image
    new_name = instance.image.name if instance.image else ''
    if old_image and old_image.name and old_image.name != new_name:
        _delete_unused_image(sender, old_image, exclude_pk=instance.pk)


@receiver(post_delete, sender=RoomType)
@receiver(post_delete, sender=Attraction)
def delete_image_on_delete(sender, instance, **kwargs):
    """Remove the image file from storage when a RoomType or Attraction is deleted."""
    if instance.image:
        _delete_unused_image(sender, instance.image)

