from django.db import models


class Model(models.Model):
    source_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    faction = models.CharField(max_length=255)
    pdf = models.CharField(max_length=512, blank=True)
    station = models.CharField(max_length=255, blank=True)
    text = models.TextField(blank=True)
    title = models.CharField(max_length=255, blank=True)
    crew_card = models.CharField(max_length=255, blank=True)
    totem_id = models.CharField(max_length=255, blank=True)
    characteristics = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    tokens = models.JSONField(default=list, blank=True)
    alternates = models.JSONField(default=list, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    files = models.JSONField(default=dict, blank=True)
    stats = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name", "source_id"]

    def __str__(self) -> str:
        return self.name


class CrewCard(models.Model):
    source_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    faction = models.CharField(max_length=255)
    pdf = models.CharField(max_length=512, blank=True)
    text = models.TextField(blank=True)
    keywords = models.JSONField(default=list, blank=True)
    tokens = models.JSONField(default=list, blank=True)
    files = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name", "source_id"]

    def __str__(self) -> str:
        return self.name


class Upgrade(models.Model):
    source_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    faction = models.CharField(max_length=255)
    pdf = models.CharField(max_length=512, blank=True)
    text = models.TextField(blank=True)
    keywords = models.JSONField(default=list, blank=True)
    tokens = models.JSONField(default=list, blank=True)
    files = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name", "source_id"]

    def __str__(self) -> str:
        return self.name
