# Planes de los colegios (Básico, Estándar, Avanzado) y sede principal de cada colegio.

from django.db import migrations, models

CAMPOS_DEL_COLEGIO = ('direccion', 'comuna', 'region', 'latitud', 'longitud', 'telefono')


def asignar_planes_y_sede_principal(apps, schema_editor):
    """
    Colegios con más de una sede: Avanzado (multisede). El resto: Básico.
    Cada colegio queda con una sede principal: la más antigua o, si no tiene sedes, una nueva copiada
    del colegio. En los colegios de una sola sede, lo que no tenía sede queda en la principal.
    """
    Colegio = apps.get_model('usuarios', 'Colegio')
    Sede = apps.get_model('usuarios', 'Sede')
    sin_sede = [apps.get_model('usuarios', nombre) for nombre in ('Estudiante', 'Furgon', 'Ruta')]

    for colegio in Colegio.objects.all():
        sedes = Sede.objects.filter(colegio=colegio).order_by('created_at', 'id')
        colegio.plan = 'avanzado' if sedes.count() > 1 else 'basico'
        colegio.save(update_fields=['plan'])

        datos = {campo: getattr(colegio, campo) for campo in CAMPOS_DEL_COLEGIO}
        principal = sedes.first()
        if principal is None:
            principal = Sede.objects.create(
                colegio=colegio, nombre='Sede Principal', activa=colegio.activo, **datos,
            )
        principal.es_principal = True
        principal.save(update_fields=['es_principal'])
        # La sede principal usa siempre los datos del colegio.
        Sede.objects.filter(pk=principal.pk).update(**datos)

        if colegio.plan != 'avanzado':
            for modelo in sin_sede:
                modelo.objects.filter(colegio=colegio, sede__isnull=True).update(sede=principal)



class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0054_qr_estatico_demo'),
    ]

    operations = [
        migrations.AddField(
            model_name='colegio',
            name='plan',
            field=models.CharField(choices=[('basico', 'Básico'), ('estandar', 'Estándar'), ('avanzado', 'Avanzado (multisede)')], default='basico', max_length=20),
        ),
        migrations.AddField(
            model_name='sede',
            name='es_principal',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(asignar_planes_y_sede_principal, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='sede',
            constraint=models.UniqueConstraint(condition=models.Q(('es_principal', True)), fields=('colegio',), name='una_sede_principal_por_colegio'),
        ),
    ]
