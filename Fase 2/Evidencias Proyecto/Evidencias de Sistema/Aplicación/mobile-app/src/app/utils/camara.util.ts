/**
 * Restricción para abrir la otra cámara del dispositivo, o null si solo tiene una.
 * En celulares alterna frontal/trasera; en PC, donde las cámaras no informan
 * su orientación, pasa a la siguiente de la lista.
 */
export async function restriccionOtraCamara(
  actual: MediaStreamTrack | undefined,
  base: MediaTrackConstraints = {}
): Promise<MediaTrackConstraints | null> {
  const camaras = (await navigator.mediaDevices.enumerateDevices())
    .filter(dispositivo => dispositivo.kind === 'videoinput');
  if (camaras.length < 2) return null;

  const ajustes = actual?.getSettings();
  if (ajustes?.facingMode === 'user' || ajustes?.facingMode === 'environment') {
    return { ...base, facingMode: { ideal: ajustes.facingMode === 'user' ? 'environment' : 'user' } };
  }
  const indice = camaras.findIndex(camara => camara.deviceId === ajustes?.deviceId);
  return { ...base, deviceId: { exact: camaras[(indice + 1) % camaras.length].deviceId } };
}

/**
 * La cámara frontal se muestra como un espejo, que es como la gente espera verse.
 * Solo cambia la vista previa: la foto que se guarda o se compara sale sin invertir.
 * En PC las cámaras no informan su orientación; se tratan como frontales salvo que su nombre diga lo contrario.
 */
export function esCamaraFrontal(flujo: MediaStream | undefined | null): boolean {
  const pista = flujo?.getVideoTracks()[0];
  if (!pista) return false;
  const orientacion = pista.getSettings?.().facingMode;
  if (orientacion === 'user') return true;
  if (orientacion === 'environment') return false;
  return !/back|rear|trasera|environment/i.test(pista.label || '');
}

export function aplicarEspejo(video: HTMLVideoElement | undefined | null, flujo: MediaStream | undefined | null): void {
  if (!video) return;
  video.style.transform = esCamaraFrontal(flujo) ? 'scaleX(-1)' : '';
}
