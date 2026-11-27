import time
import tkinter as tk

import cv2
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageTk

from usuarios.face_recognition_service import (
    FaceRecognitionEngine,
    SFACE_COSINE_THRESHOLD,
    YUNET_NMS_THRESHOLD,
    YUNET_SCORE_THRESHOLD,
    YUNET_TOP_K,
)


class Command(BaseCommand):
    help = 'Herramienta visual local para diagnosticar YuNet y comparar embeddings SFace.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--camera', type=int, default=0, help='Indice de camara (por defecto: 0).')

    def handle(self, *args, **options):
        engine = FaceRecognitionEngine()
        if engine.detector is None or engine.recognizer is None:
            raise CommandError('No fue posible inicializar YuNet/SFace.')

        capture = cv2.VideoCapture(options['camera'], cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(options['camera'])
        if not capture.isOpened():
            raise CommandError(f'No fue posible abrir la camara {options["camera"]}.')

        root = tk.Tk()
        root.title('Rutas Seguras - Diagnostico YuNet + SFace')
        root.configure(bg='#111827')
        video = tk.Label(root, bg='black')
        video.pack(padx=12, pady=(12, 4))
        info = tk.Label(root, fg='white', bg='#111827', font=('Segoe UI', 11), justify='left')
        info.pack(padx=12, pady=8, anchor='w')

        state = {
            'frame': None,
            'face': None,
            'face_count': 0,
            'sample_1': None,
            'sample_2': None,
            'fps': 0.0,
            'last_time': time.perf_counter(),
            'last_report': 0.0,
            'last_status': None,
            'closed': False,
            'result': 'Aun no se han comparado muestras.',
        }

        def capture_sample(slot):
            if state['face_count'] != 1 or state['frame'] is None:
                state['result'] = 'CAPTURA RECHAZADA: debe existir exactamente un rostro.'
                return
            embedding = engine.generar_embedding(state['frame'], state['face'])
            state[f'sample_{slot}'] = embedding
            state['result'] = f'Muestra {slot} capturada en memoria (dimension={len(embedding)}).'
            self.stdout.write(state['result'])

        def compare_samples():
            first, second = state['sample_1'], state['sample_2']
            if first is None or second is None:
                state['result'] = 'FALTAN MUESTRAS: captura 1 y 2 antes de comparar.'
                return
            similarity = engine.comparar_embeddings(first, second)
            result = 'MATCH' if similarity >= SFACE_COSINE_THRESHOLD else 'NO MATCH'
            state['result'] = (
                f'dimension=128 | cosine_similarity={similarity:.6f} | '
                f'threshold={SFACE_COSINE_THRESHOLD:.3f} | {result}'
            )
            self.stdout.write(state['result'])

        def reset_samples():
            state['sample_1'] = None
            state['sample_2'] = None
            state['result'] = 'Muestras eliminadas de memoria.'
            self.stdout.write(state['result'])

        def close():
            if state['closed']:
                return
            state['closed'] = True
            capture.release()
            root.destroy()

        def update_frame():
            if state['closed']:
                return
            ok, frame = capture.read()
            if not ok:
                state['result'] = 'ERROR: no se pudo leer un frame de la camara.'
                root.after(100, update_frame)
                return

            # OpenCV y YuNet reciben BGR. Solo la copia de preview se convierte a RGB.
            frame = cv2.flip(frame, 1)
            detection = engine.detectar_rostros(frame)
            faces = detection.get('faces')
            count = detection['face_count'] if detection['ok'] else 0
            state['frame'] = frame
            state['face_count'] = count
            state['face'] = faces[0].copy() if count == 1 else None

            if count == 0:
                status, color = 'SIN ROSTRO', (0, 0, 255)
            elif count == 1:
                status, color = 'ROSTRO DETECTADO', (0, 200, 0)
            else:
                status, color = 'MULTIPLES ROSTROS', (0, 165, 255)

            preview = frame.copy()
            if faces is not None:
                for face in faces:
                    x, y, width, height = (int(value) for value in face[:4])
                    cv2.rectangle(preview, (x, y), (x + width, y + height), color, 2)
                    score = float(face[-1])
                    cv2.putText(preview, f'{score:.3f}', (x, max(20, y - 7)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            now = time.perf_counter()
            instant_fps = 1.0 / max(now - state['last_time'], 0.000001)
            state['last_time'] = now
            state['fps'] = instant_fps if state['fps'] == 0 else state['fps'] * 0.9 + instant_fps * 0.1
            height, width = frame.shape[:2]
            if status != state['last_status'] or now - state['last_report'] >= 2.0:
                self.stdout.write(
                    f'status={status} faces={count} frame={width}x{height} fps={state["fps"]:.1f}'
                )
                state['last_status'] = status
                state['last_report'] = now
            sample_1 = 'SI' if state['sample_1'] is not None else 'NO'
            sample_2 = 'SI' if state['sample_2'] is not None else 'NO'
            info.configure(text=(
                f'{status} | rostros={count} | FPS={state["fps"]:.1f}\n'
                f'Frame={width}x{height} | formato YuNet=BGR | preview reflejado horizontalmente\n'
                f'YuNet: score={YUNET_SCORE_THRESHOLD} | NMS={YUNET_NMS_THRESHOLD} | top_k={YUNET_TOP_K}\n'
                f'Muestra 1={sample_1} | Muestra 2={sample_2}\n'
                f'{state["result"]}\n'
                'Controles: 1=muestra 1 | 2=muestra 2/reemplazar | C=comparar | R=reiniciar | Q=cerrar'
            ))

            rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            image = ImageTk.PhotoImage(Image.fromarray(rgb))
            video.configure(image=image)
            video.image = image
            root.after(1, update_frame)

        root.bind('1', lambda _event: capture_sample(1))
        root.bind('2', lambda _event: capture_sample(2))
        root.bind('<KeyPress-c>', lambda _event: compare_samples())
        root.bind('<KeyPress-C>', lambda _event: compare_samples())
        root.bind('<KeyPress-r>', lambda _event: reset_samples())
        root.bind('<KeyPress-R>', lambda _event: reset_samples())
        root.bind('<KeyPress-q>', lambda _event: close())
        root.bind('<KeyPress-Q>', lambda _event: close())
        root.protocol('WM_DELETE_WINDOW', close)

        self.stdout.write('Camara iniciada. Ningun frame ni embedding sera persistido.')
        try:
            update_frame()
            root.mainloop()
        finally:
            capture.release()
            if not state['closed']:
                try:
                    root.destroy()
                except tk.TclError:
                    pass
