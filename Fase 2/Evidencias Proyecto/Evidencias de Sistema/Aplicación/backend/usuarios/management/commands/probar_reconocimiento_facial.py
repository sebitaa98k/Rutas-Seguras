from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from usuarios.face_recognition_service import FaceRecognitionEngine, SFACE_COSINE_THRESHOLD


class Command(BaseCommand):
    help = 'Compara dos imagenes en memoria mediante YuNet + alignCrop + SFace.'

    def add_arguments(self, parser):
        parser.add_argument('foto_a', help='Ruta local de la primera fotografia.')
        parser.add_argument('foto_b', help='Ruta local de la segunda fotografia.')

    def handle(self, *args, **options):
        rutas = [Path(options['foto_a']).expanduser(), Path(options['foto_b']).expanduser()]
        for ruta in rutas:
            if not ruta.is_file():
                raise CommandError(f'No existe el archivo: {ruta}')

        engine = FaceRecognitionEngine()
        resultados = []
        for etiqueta, ruta in zip(('a', 'b'), rutas):
            resultado = engine.analizar_imagen(ruta.read_bytes())
            self.stdout.write(f'foto_{etiqueta}={ruta}')
            self.stdout.write(f'faces_{etiqueta}={resultado["face_count"]}')
            if not resultado['ok']:
                self.stdout.write(self.style.ERROR(f'error_{etiqueta}={resultado["code"]}'))
                self.stdout.write(self.style.ERROR('result=ERROR'))
                return
            self.stdout.write(f'embedding_dimension_{etiqueta}={resultado["embedding_dimension"]}')
            resultados.append(resultado)

        similitud = engine.comparar_embeddings(
            resultados[0]['embedding'], resultados[1]['embedding']
        )
        coincide = similitud >= SFACE_COSINE_THRESHOLD
        self.stdout.write(f'cosine_similarity={similitud:.6f}')
        self.stdout.write(f'threshold={SFACE_COSINE_THRESHOLD:.3f}')
        self.stdout.write(
            self.style.SUCCESS('result=MATCH')
            if coincide else self.style.WARNING('result=NO MATCH')
        )
