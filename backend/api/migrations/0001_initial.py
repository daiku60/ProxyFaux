from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Model",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_id", models.CharField(max_length=255, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("faction", models.CharField(max_length=255)),
                ("station", models.CharField(blank=True, max_length=255)),
                ("text", models.TextField(blank=True)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("crew_card", models.CharField(blank=True, max_length=255)),
                ("totem_id", models.CharField(blank=True, max_length=255)),
                ("characteristics", models.JSONField(blank=True, default=list)),
                ("keywords", models.JSONField(blank=True, default=list)),
                ("tokens", models.JSONField(blank=True, default=list)),
                ("alternates", models.JSONField(blank=True, default=list)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("files", models.JSONField(blank=True, default=dict)),
                ("stats", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["name", "source_id"],
            },
        ),
    ]
