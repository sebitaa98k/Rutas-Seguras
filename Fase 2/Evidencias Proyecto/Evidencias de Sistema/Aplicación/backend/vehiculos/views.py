from usuarios.papelera import desactivar_furgon
from usuarios.papelera_views import respuesta_desactivar
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import Furgon
from usuarios.permissions import IsAdministrador
from vehiculos.serializers import FurgonSerializer
from usuarios.view_common import get_colegio_id_for_request

class FurgonListCreateView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        colegio_id = get_colegio_id_for_request(request)
        furgones = Furgon.objects.all()
        if colegio_id:
            furgones = furgones.filter(colegio_id=colegio_id)
        furgones = furgones.order_by('-id')
        serializer = FurgonSerializer(furgones, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data.copy()
        target_colegio_id = get_colegio_id_for_request(request) or data.get('colegio') or data.get('colegio_id')
        if target_colegio_id:
            data['colegio'] = target_colegio_id

        serializer = FurgonSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FurgonDetailView(APIView):
    permission_classes = [IsAdministrador]

    def get_object(self, request, pk):
        colegio_id = get_colegio_id_for_request(request)
        try:
            qs = Furgon.objects.filter(pk=pk)
            if colegio_id:
                qs = qs.filter(colegio_id=colegio_id)
            return qs.get()
        except Furgon.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        furgon = self.get_object(request, pk)
        serializer = FurgonSerializer(furgon)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        furgon = self.get_object(request, pk)
        data = request.data.copy()
        target_colegio_id = get_colegio_id_for_request(request) or data.get('colegio') or data.get('colegio_id')
        if target_colegio_id:
            data['colegio'] = target_colegio_id

        serializer = FurgonSerializer(furgon, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        return respuesta_desactivar(desactivar_furgon, self.get_object(request, pk))
