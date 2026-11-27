import { Component, Input } from '@angular/core';

/**
 * Información que se muestra junto al interruptor de reconocimiento facial de cada hijo
 * (Ley 21.719, arts. 12 y 16 ter): qué dato se usa, para qué, cuánto tiempo y cómo se revoca.
 */
@Component({
  selector: 'app-consentimiento-biometrico',
  standalone: true,
  template: `
    <div class="consentimiento" role="note">
      <p class="titulo">Antes de autorizar el reconocimiento facial{{ nombre ? ' de ' + nombre : '' }}:</p>
      <ul>
        <li><strong>Qué dato se usa:</strong> una foto de su rostro y un código numérico de sus rasgos faciales
          (dato biométrico), guardados cifrados.</li>
        <li><strong>Para qué:</strong> solo para identificarlo al subir y bajar del furgón. No se publica ni se
          muestra a otros apoderados.</li>
        <li><strong>Cuánto tiempo:</strong> mientras esta autorización esté vigente y use el servicio.</li>
        <li><strong>Cómo retirarla:</strong> cuando quieras, desde el detalle del hijo. Se borran al tiro su foto y
          sus datos faciales, y pasa a subir y bajar con tu código QR.</li>
      </ul>
      <p class="nota">Es opcional: sin autorizarlo, usa el servicio igual con tu código QR o con el inspector.</p>
    </div>
  `,
  styles: [`
    .consentimiento {
      margin: 8px 0 0;
      padding: 12px 14px;
      border-radius: 12px;
      background: var(--rs-color-surface-muted, #f1f5f4);
      color: var(--rs-color-text, #1f2d2b);
      font-size: 13px;
      line-height: 1.45;
      overflow-wrap: anywhere;
      box-sizing: border-box;
      max-width: 100%;
    }
    :host { display: block; }
    .titulo { margin: 0 0 6px; font-weight: 700; }
    ul { margin: 0; padding-left: 18px; }
    li { margin-bottom: 4px; }
    .nota { margin: 8px 0 0; color: var(--rs-color-text-muted, #5c6f6c); }
  `]
})
export class ConsentimientoBiometricoComponent {
  /** Nombre del hijo, para que quede claro a quién aplica. */
  @Input() nombre = '';
}
