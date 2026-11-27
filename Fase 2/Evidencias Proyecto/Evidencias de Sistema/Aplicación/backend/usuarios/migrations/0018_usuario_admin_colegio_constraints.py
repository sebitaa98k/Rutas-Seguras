from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0017_mark_empty_passwords_unusable'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.CheckConstraint(
                condition=~models.Q(rol='admin_plataforma') | models.Q(colegio__isnull=True),
                name='admin_plataforma_sin_colegio',
            ),
        ),
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.CheckConstraint(
                condition=~models.Q(rol='admin_colegio') | models.Q(colegio__isnull=False),
                name='admin_colegio_con_colegio',
            ),
        ),
    ]
