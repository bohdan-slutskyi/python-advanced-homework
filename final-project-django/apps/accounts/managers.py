from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def normalize_email_address(self, email):
        if not email:
            raise ValueError("An email address is required")
        return self.normalize_email(email).strip().casefold()

    def create_user(self, email, password=None, **extra_fields):
        email = self.normalize_email_address(email)
        if not extra_fields.get("display_name", "").strip():
            raise ValueError("A display name is required")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True")
        return self.create_user(email, password, **extra_fields)
