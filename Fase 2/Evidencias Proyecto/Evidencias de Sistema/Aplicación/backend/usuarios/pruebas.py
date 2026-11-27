"""Ayudas para las pruebas automáticas."""
from .models import DelegadoSede, Sede


def asignar_sede(inspector, sede=None):
    """Todo inspector tiene su sede; en las pruebas se le crea una en su colegio si no se indica."""
    sede = sede or Sede.objects.create(colegio_id=inspector.colegio_id, nombre=f'Sede de {inspector.rut}')
    DelegadoSede.objects.create(delegado=inspector, sede=sede)
    return inspector
