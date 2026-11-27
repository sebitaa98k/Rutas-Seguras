"""Configuracion versionada del pipeline biometrico del proyecto."""

BIOMETRIC_PIPELINE_VERSION = 'yunet_2026may+sface_2021dec:v1'
YUNET_SCORE_THRESHOLD = 0.75
YUNET_NMS_THRESHOLD = 0.3
YUNET_TOP_K = 5000
SFACE_COSINE_THRESHOLD = 0.363
SFACE_AMBIGUITY_MARGIN = 0.05
MAX_BIOMETRIC_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_BIOMETRIC_CONTENT_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
