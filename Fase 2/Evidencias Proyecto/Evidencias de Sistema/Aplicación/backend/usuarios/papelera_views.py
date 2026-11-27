"""Papelera del panel: lista lo desactivado y permite reactivarlo."""
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from .papelera import PapeleraError, contenido_papelera, eliminar_definitivo, mover_al_colegio, reactivar
from .permissions import IsAdministrador, es_admin_plataforma
from .view_common import get_colegio_id_for_request


def respuesta_desactivar(funcion, *args):
    """Respuesta común de los botones "Desactivar": 200 si se pudo, 409 con lo que falta si no."""
    try:
        return Response({'message': funcion(*args), 'desactivado': True})
    except PapeleraError as exc:
        return Response({'message': str(exc), 'desactivado': False}, status=409)


class PapeleraView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        return Response(contenido_papelera(
            get_colegio_id_for_request(request), admin_plataforma=es_admin_plataforma(request.user),
        ))


class PapeleraReactivarView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request, tipo, pk):
        try:
            mensaje = reactivar(
                tipo, pk, get_colegio_id_for_request(request),
                admin_plataforma=es_admin_plataforma(request.user),
            )
        except LookupError:
            raise Http404
        except PapeleraError as exc:
            return Response({'message': str(exc)}, status=409)
        return Response({'message': mensaje})


class PapeleraEliminarView(APIView):
    """Elimina definitivamente un registro de la papelera. El panel pide confirmarlo antes."""

    permission_classes = [IsAdministrador]

    def delete(self, request, tipo, pk):
        try:
            mensaje = eliminar_definitivo(
                tipo, pk, get_colegio_id_for_request(request),
                admin_plataforma=es_admin_plataforma(request.user),
            )
        except LookupError:
            raise Http404
        except PapeleraError as exc:
            return Response({'message': str(exc)}, status=409)
        return Response({'message': mensaje})


class PapeleraMoverView(APIView):
    """Mueve al colegio (su sede principal) algo que quedó en una sede cerrada al bajar de plan."""

    permission_classes = [IsAdministrador]

    def post(self, request, tipo, pk):
        try:
            mensaje = mover_al_colegio(
                tipo, pk, get_colegio_id_for_request(request),
                admin_plataforma=es_admin_plataforma(request.user),
            )
        except LookupError:
            raise Http404
        except PapeleraError as exc:
            return Response({'message': str(exc)}, status=409)
        return Response({'message': mensaje})
