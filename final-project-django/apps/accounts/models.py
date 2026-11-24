from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("email address"), unique=True, max_length=254)
    display_name = models.CharField(_("display name"), max_length=150)
    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    date_joined = models.DateTimeField(_("date joined"), auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.email = User.objects.normalize_email_address(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
