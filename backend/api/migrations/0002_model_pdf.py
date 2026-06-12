from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="model",
            name="pdf",
            field=models.CharField(blank=True, max_length=512),
        ),
    ]
