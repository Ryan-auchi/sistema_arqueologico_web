from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pesquisa", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="api_id",
            field=models.CharField(blank=True, default="", max_length=36),
        ),
    ]
