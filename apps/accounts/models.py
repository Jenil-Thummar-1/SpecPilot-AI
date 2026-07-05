from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.core.models import TimeStampedModel
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    """
    Custom user model for SpecPilot AI workspace.
    """
    pass

class Profile(TimeStampedModel):
    """
    Profile information and user settings workspace configurations.
    """
    THEME_CHOICES = [
        ('light', 'Light Mode'),
        ('dark', 'Dark Mode'),
        ('system', 'System Default'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    theme_preference = models.CharField(max_length=15, choices=THEME_CHOICES, default='dark')
    api_key_override = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Provide a custom Google Gemini API Key. If left blank, the system-wide key is used."
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"

# Automatically create user profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
