"""Página de error de Django (DEBUG=True) sin datos del .env.

Django solo oculta los valores cuyo nombre contiene API, TOKEN, KEY, SECRET, PASS o SIGNATURE.
Este filtro oculta además todo lo que viene de backend/.env, se llame como se llame: la clave de
cifrado de las fotos, el correo de Gmail, etc. Así una captura de un error no expone secretos.
"""
import re

from django.conf import settings
from django.views.debug import SafeExceptionReporterFilter
from dotenv import dotenv_values

# Valores tan cortos o comunes que ocultarlos solo estorbaría (por ejemplo, "True" o "*").
LARGO_MINIMO_SECRETO = 6


def _valores_del_env():
    ruta = settings.BASE_DIR / '.env'
    if not ruta.exists():
        return {}, set()
    valores = {nombre: valor for nombre, valor in dotenv_values(ruta).items() if valor}
    secretos = {valor for valor in valores.values() if len(valor) >= LARGO_MINIMO_SECRETO}
    # La contraseña de Gmail se usa sin espacios.
    secretos |= {valor.replace(' ', '') for valor in secretos}
    return valores, secretos


class FiltroErroresSinSecretos(SafeExceptionReporterFilter):
    hidden_settings = re.compile(
        'API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|CLAVE|CIFRADO|CORREO|EMAIL|MAILERS',
        flags=re.IGNORECASE,
    )

    def __init__(self):
        super().__init__()
        self.nombres_env, self.secretos_env = _valores_del_env()

    def _contiene_secreto(self, valor):
        texto = str(valor)
        return any(secreto in texto for secreto in self.secretos_env)

    def get_traceback_frame_variables(self, request, tb_frame):
        # Variables locales de cada función del error: con DEBUG=True Django no las oculta.
        variables = super().get_traceback_frame_variables(request, tb_frame)
        return [
            (nombre, self.cleansed_substitute if self._contiene_secreto(repr(valor)) else valor)
            for nombre, valor in variables
        ]

    def cleanse_setting(self, key, value):
        # Variables del .env (aparecen así en las variables del servidor) y cualquier valor que las contenga.
        if isinstance(key, str) and key in self.nombres_env:
            return self.cleansed_substitute
        if isinstance(value, str) and self._contiene_secreto(value):
            return self.cleansed_substitute
        return super().cleanse_setting(key, value)
