import { Component, EventEmitter, Input, Output } from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { checkmarkCircleOutline, peopleOutline } from 'ionicons/icons';

addIcons({ checkmarkCircleOutline, peopleOutline });

export interface NinoAConfirmar {
  id: number;
  nombre: string;
  rut: string;
  curso?: string;
}

/**
 * Ventana "¿Seguro que son estos niños?": el conductor revisa a quién marcó del QR
 * de un apoderado o persona autorizada antes de registrar la subida o la entrega.
 */
@Component({
  selector: 'app-confirmar-ninos',
  standalone: true,
  imports: [IonIcon],
  templateUrl: './confirmar-ninos.component.html',
  styleUrls: ['./confirmar-ninos.component.scss']
})
export class ConfirmarNinosComponent {
  @Input() seleccionados: NinoAConfirmar[] = [];
  @Input() noSeleccionados: NinoAConfirmar[] = [];
  /** Dueño del QR escaneado. */
  @Input() persona = '';
  /** true: suben al furgón (ida). false: se entregan (vuelta). */
  @Input() esSubida = false;

  @Output() revisar = new EventEmitter<void>();
  @Output() confirmar = new EventEmitter<void>();

  iniciales(nombre: string): string {
    return (nombre || '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map(p => p.charAt(0).toUpperCase())
      .join('') || '?';
  }
}
