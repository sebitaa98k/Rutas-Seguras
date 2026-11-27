import os
import base64
import binascii
import numpy as np
import cv2
from django.conf import settings
from .biometric_config import (
    BIOMETRIC_PIPELINE_VERSION,
    SFACE_AMBIGUITY_MARGIN,
    SFACE_COSINE_THRESHOLD,
    YUNET_NMS_THRESHOLD,
    YUNET_SCORE_THRESHOLD,
    YUNET_TOP_K,
)
from .terminos import biometria_autorizada
from .models import Ruta

# Rutas absolutas a los modelos ONNX dentro del backend
BASE_PATH = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_PATH, 'usuarios', 'models_onnx')

DETECTOR_MODEL = os.path.join(MODELS_DIR, 'face_detection_yunet_2026may.onnx')
RECOGNITION_MODEL = os.path.join(MODELS_DIR, 'face_recognition_sface_2021dec.onnx')
class FaceRecognitionEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FaceRecognitionEngine, cls).__new__(cls)
            cls._instance._init_models()
        return cls._instance

    def _init_models(self):
        if not os.path.exists(DETECTOR_MODEL) or not os.path.exists(RECOGNITION_MODEL):
            print(f"[FaceRecognitionEngine] ERROR: No se encontraron los modelos ONNX en {DETECTOR_MODEL} o {RECOGNITION_MODEL}")
            self.detector = None
            self.recognizer = None
            return

        try:
            self.detector = cv2.FaceDetectorYN.create(
                DETECTOR_MODEL,
                "",
                (320, 320),
                YUNET_SCORE_THRESHOLD,
                YUNET_NMS_THRESHOLD,
                YUNET_TOP_K
            )
            self.recognizer = cv2.FaceRecognizerSF.create(
                RECOGNITION_MODEL,
                ""
            )
            print("[FaceRecognitionEngine] Modelos YuNet + SFace cargados exitosamente.")
        except Exception as e:
            print(f"[FaceRecognitionEngine] Error al inicializar modelos: {e}")
            self.detector = None
            self.recognizer = None

    def extraer_embedding(self, frame):
        """Extrae un embedding solo cuando existe exactamente un rostro."""
        resultado = self.analizar_frame(frame)
        return resultado.get('embedding') if resultado['ok'] else None

    def analizar_frame(self, frame):
        """Ejecuta el pipeline unico YuNet -> alignCrop -> SFace."""
        deteccion = self.detectar_rostros(frame)
        if not deteccion['ok']:
            return {**deteccion, 'embedding': None}

        faces = deteccion['faces']
        face_count = deteccion['face_count']
        if face_count == 0:
            return {'ok': False, 'code': 'NO_FACE_DETECTED', 'face_count': 0, 'embedding': None}
        if face_count > 1:
            return {'ok': False, 'code': 'MULTIPLE_FACES_DETECTED', 'face_count': face_count, 'embedding': None}

        embedding = self.generar_embedding(frame, faces[0])
        return {
            'ok': True,
            'code': 'OK',
            'face_count': 1,
            'embedding': embedding,
            'embedding_dimension': len(embedding),
        }

    def detectar_rostros(self, frame):
        """Detecta rostros YuNet en un frame BGR sin modificarlo ni persistirlo."""
        if self.detector is None or self.recognizer is None:
            return {'ok': False, 'code': 'ENGINE_NOT_INITIALIZED', 'face_count': 0, 'faces': None}
        if frame is None or frame.size == 0:
            return {'ok': False, 'code': 'INVALID_IMAGE', 'face_count': 0, 'faces': None}

        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)
        return {
            'ok': True,
            'code': 'OK',
            'face_count': 0 if faces is None else len(faces),
            'faces': faces,
            'frame_width': width,
            'frame_height': height,
        }

    def generar_embedding(self, frame, face):
        """Alinea una deteccion YuNet y genera su embedding SFace."""
        aligned_face = self.recognizer.alignCrop(frame, face)
        feature = self.recognizer.feature(aligned_face)
        return feature.flatten().astype(np.float32).tolist()

    def analizar_imagen(self, image_bytes):
        """Decodifica bytes/base64 en memoria y ejecuta el pipeline facial."""
        try:
            if isinstance(image_bytes, str):
                if ',' in image_bytes:
                    image_bytes = image_bytes.split(',', 1)[1]
                image_bytes = base64.b64decode(image_bytes, validate=True)
        except (binascii.Error, ValueError):
            return {'ok': False, 'code': 'INVALID_IMAGE', 'face_count': 0, 'embedding': None}

        if not image_bytes:
            return {'ok': False, 'code': 'INVALID_IMAGE', 'face_count': 0, 'embedding': None}
        frame = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        return self.analizar_frame(frame)

    def extraer_embedding_de_bytes(self, image_bytes):
        """Convierte bytes de imagen (JPEG/PNG) o Base64 a matriz OpenCV y extrae embedding."""
        resultado = self.analizar_imagen(image_bytes)
        return resultado.get('embedding') if resultado['ok'] else None

    def procesar_foto_estudiante(self, image_bytes):
        """
        Procesa una imagen recibida para el registro biométrico de un estudiante.
        Validaciones estrictas:
        - 0 rostros -> rechazar.
        - >1 rostros -> rechazar.
        - 1 rostro -> extraer embedding SFace (128 floats).
        """
        resultado = self.analizar_imagen(image_bytes)
        if resultado['code'] == 'ENGINE_NOT_INITIALIZED':
            return False, "El motor biométrico YuNet/SFace no se encuentra inicializado."
        if resultado['code'] == 'INVALID_IMAGE':
            return False, "No se pudo decodificar el formato de la imagen subida."
        if resultado['code'] == 'NO_FACE_DETECTED':
            return False, "No se detectó ningún rostro en la imagen. Por favor sube una foto clara del estudiante."
        if resultado['code'] == 'MULTIPLE_FACES_DETECTED':
            return False, f"Se detectaron {resultado['face_count']} rostros en la imagen. Debe contener únicamente el rostro del estudiante."
        if not resultado['ok']:
            return False, "No fue posible procesar la fotografía biométrica."
        return True, resultado['embedding']

    def comparar_embeddings(self, emb1, emb2):
        """Calcula similitud de coseno SFace entre dos vectores de 128 floats."""
        if not emb1 or not emb2 or len(emb1) != 128 or len(emb2) != 128:
            return -1.0

        f1 = np.array(emb1, dtype=np.float32).reshape(1, -1)
        f2 = np.array(emb2, dtype=np.float32).reshape(1, -1)

        score = self.recognizer.match(f1, f2, cv2.FaceRecognizerSF_FR_COSINE)
        return float(score)


def _obtener_embedding_actualizado(engine, objeto):
    """Obtiene un embedding compatible sin persistir fotografias nuevas."""
    embedding = objeto.embedding_facial
    version = objeto.embedding_facial_version

    # Los vectores existentes sin version fueron generados con estos mismos
    # modelos. Se etiquetan para no inutilizar registros previos.
    if embedding and len(embedding) == 128 and not version:
        objeto.embedding_facial_version = BIOMETRIC_PIPELINE_VERSION
        objeto.save(update_fields=['embedding_facial_version'])
        return embedding

    if embedding and len(embedding) == 128 and version == BIOMETRIC_PIPELINE_VERSION:
        return embedding

    foto = getattr(objeto, 'foto', None)
    if not foto:
        return None

    try:
        with foto.open('rb') as archivo:
            embedding = engine.extraer_embedding_de_bytes(archivo.read())
        if embedding:
            objeto.embedding_facial = embedding
            objeto.embedding_facial_version = BIOMETRIC_PIPELINE_VERSION
            objeto.save(update_fields=['embedding_facial', 'embedding_facial_version'])
            return embedding
    except (OSError, ValueError) as exc:
        print(f"[FaceRecognitionService] Error procesando foto de {objeto.__class__.__name__} {objeto.pk}: {exc}")
    return None


def procesar_identificacion_facial(conductor_perfil, imagen_raw, modo='abordar', threshold=SFACE_COSINE_THRESHOLD):
    """
    Busca coincidencias faciales REALES acotadas únicamente a los estudiantes
    de la ruta activa del conductor.
    """
    engine = FaceRecognitionEngine()
    embedding_capturado = engine.extraer_embedding_de_bytes(imagen_raw)

    if not embedding_capturado:
        return {
            'coincidencia': False,
            'motivo': 'no_rostro_detectado',
            'requiere_verificacion_alternativa': True,
            'mensaje': 'No se detectó ningún rostro claro en la captura. Por favor, vuelve a enfocar.'
        }

    # La busqueda queda acotada a la ruta realmente iniciada por el conductor.
    ruta_activa = (
        Ruta.objects.select_related('colegio', 'furgon__colegio').prefetch_related('estudiantes__apoderado__usuario')
        .filter(conductor_perfil=conductor_perfil, estado='en_ruta')
        .order_by('id')
        .first()
    )
    if not ruta_activa:
        return {
            'coincidencia': False,
            'motivo': 'sin_ruta_activa',
            'mensaje': 'El conductor no tiene una ruta iniciada para realizar la verificación.'
        }

    if (
        conductor_perfil.colegio_id
        and ruta_activa.colegio_id != conductor_perfil.colegio_id
    ):
        return {
            'coincidencia': False,
            'motivo': 'ruta_fuera_de_colegio',
            'mensaje': 'La ruta activa no corresponde al colegio del conductor.'
        }

    # El modelo asigna el furgón a la ruta, no directamente al conductor. La
    # consistencia disponible es que ambos pertenezcan al mismo colegio.
    if (
        ruta_activa.furgon_id
        and ruta_activa.colegio_id
        and ruta_activa.furgon.colegio_id
        and ruta_activa.furgon.colegio_id != ruta_activa.colegio_id
    ):
        return {
            'coincidencia': False,
            'motivo': 'furgon_fuera_de_ruta',
            'mensaje': 'El furgón asignado no corresponde al colegio de la ruta activa.'
        }

    estudiantes_ruta = ruta_activa.estudiantes.select_related('apoderado__usuario', 'colegio').all()
    if ruta_activa.colegio_id:
        estudiantes_ruta = estudiantes_ruta.filter(colegio_id=ruta_activa.colegio_id)
    if not estudiantes_ruta.exists():
        return {
            'coincidencia': False,
            'motivo': 'sin_estudiantes_asignados',
            'mensaje': 'La ruta activa no tiene estudiantes asignados.'
        }

    candidatos = []

    # Solo los estudiantes usan biometría, tanto al subir como al ser entregados.
    for est in estudiantes_ruta:
        # Sin la autorización del apoderado no se compara su rostro: se valida con QR.
        if not biometria_autorizada(est):
            continue

        emb = _obtener_embedding_actualizado(engine, est)

        if emb:
            candidatos.append({
                'tipo': 'ESTUDIANTE',
                'objeto': est,
                'embedding': emb,
                'nombre': f"{est.nombre} {est.apellido}",
                'rut': est.rut,
                'estudiante_id': est.id,
                'estudiante_nombre': f"{est.nombre} {est.apellido}",
                'colegio': str(est.colegio) if est.colegio else '',
                'colegio_id': est.colegio_id,
                'curso': est.curso
            })

    if not candidatos:
        return {
            'coincidencia': False,
            'motivo': 'sin_biometria_registrada',
            'requiere_verificacion_alternativa': True,
            'mensaje': 'Los estudiantes de esta ruta no tienen su rostro registrado. Valida con QR.',
        }

    # 2. Comparar embedding capturado contra candidatos de la ruta activa
    coincidencias = sorted(
        (
            (engine.comparar_embeddings(embedding_capturado, candidato['embedding']), candidato)
            for candidato in candidatos
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    mejor_score, mejor_coincidencia = coincidencias[0]

    segundo_distinto = next(
        (
            item for item in coincidencias[1:]
            if (
                item[1]['tipo'],
                item[1]['objeto'].pk,
            ) != (
                mejor_coincidencia['tipo'],
                mejor_coincidencia['objeto'].pk,
            )
        ),
        None,
    )
    if segundo_distinto:
        segundo_score = segundo_distinto[0]
        if (
            mejor_score >= threshold
            and segundo_score >= threshold
            and (mejor_score - segundo_score) < SFACE_AMBIGUITY_MARGIN
        ):
            return {
                'coincidencia': False,
                'motivo': 'coincidencia_ambigua',
                'score_maximo': round(mejor_score, 4),
                'segundo_score': round(segundo_score, 4),
                'requiere_verificacion_alternativa': True,
                'mensaje': 'Hay más de una coincidencia facial similar. Verifica mediante QR o control manual.'
            }

    if mejor_coincidencia and mejor_score >= threshold:
        similitud_porcentaje = round(min(100.0, max(0.0, mejor_score * 100)), 1)
        return {
            'coincidencia': True,
            'score': round(mejor_score, 4),
            'similitud_porcentaje': similitud_porcentaje,
            'tipo_identificado': mejor_coincidencia['tipo'],
            'nombre_identificado': mejor_coincidencia['nombre'],
            'rut_identificado': mejor_coincidencia.get('rut', ''),
            'perfil_id': mejor_coincidencia.get('perfil_id'),
            'estudiante_id': mejor_coincidencia['estudiante_id'],
            'estudiante_nombre': mejor_coincidencia['estudiante_nombre'],
            'colegio': mejor_coincidencia.get('colegio', ''),
            'colegio_id': mejor_coincidencia.get('colegio_id'),
            'curso': mejor_coincidencia.get('curso', ''),
            'relacion': mejor_coincidencia.get('relacion', 'Estudiante'),
            'pipeline_biometrico': BIOMETRIC_PIPELINE_VERSION,
            'mensaje': f"¡Rostro de {mejor_coincidencia['nombre']} identificado exitosamente!"
        }
    else:
        return {
            'coincidencia': False,
            'motivo': 'bajo_umbral',
            'score_maximo': round(mejor_score, 4) if mejor_score > 0 else 0,
            'requiere_verificacion_alternativa': True,
            'mensaje': 'Rostro no identificado entre los estudiantes de esta ruta.'
        }
