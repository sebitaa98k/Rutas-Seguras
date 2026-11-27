import { Component, ElementRef, EventEmitter, Input, OnInit, Output, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonButton, IonCheckbox, IonSpinner } from '@ionic/angular/standalone';

import { AuthService } from '../../services/auth.service';

interface BloqueTexto {
  esTitulo: boolean;
  texto: string;
}

/** El apoderado aceptó esta versión. La biometría ya no va aquí: se autoriza por cada hijo. */
export interface AceptacionTerminosPanel {
  version: string;
}

/** Margen para considerar leído el final aunque falten unos píxeles por redondeo. */
const MARGEN_FINAL_PX = 16;

@Component({
  selector: 'app-terminos-panel',
  templateUrl: './terminos-panel.component.html',
  styleUrls: ['./terminos-panel.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, IonButton, IonCheckbox, IonSpinner]
})
export class TerminosPanelComponent implements OnInit {
  @Input() textoAceptar = 'Aceptar y continuar';
  @Input() textoCancelar = 'Cancelar';
  @Input() enviando = false;
  @Output() aceptar = new EventEmitter<AceptacionTerminosPanel>();
  @Output() cancelar = new EventEmitter<void>();

  @ViewChild('zonaTexto') private zonaTexto?: ElementRef<HTMLElement>;

  titulo = '';
  version = '';
  bloques: BloqueTexto[] = [];
  cargando = true;
  error = '';
  llegoAlFinal = false;
  aceptaTerminos = false;

  constructor(private authService: AuthService) {}

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando = true;
    this.error = '';
    this.authService.obtenerTerminos().subscribe({
      next: (terminos) => {
        this.titulo = terminos.titulo;
        this.version = terminos.version;
        this.bloques = terminos.contenido
          .split(/\n\s*\n/)
          .map((bloque) => bloque.trim())
          .filter(Boolean)
          .map((bloque) => bloque.startsWith('## ')
            ? { esTitulo: true, texto: bloque.slice(3) }
            : { esTitulo: false, texto: bloque });
        this.cargando = false;
        // Si el texto cabe completo en la pantalla no hay nada que desplazar.
        setTimeout(() => this.revisarLectura());
      },
      error: () => {
        this.cargando = false;
        this.error = 'No se pudieron cargar los términos. Revisa tu conexión e inténtalo nuevamente.';
      }
    });
  }

  revisarLectura(): void {
    const zona = this.zonaTexto?.nativeElement;
    if (zona && zona.scrollTop + zona.clientHeight >= zona.scrollHeight - MARGEN_FINAL_PX) {
      this.llegoAlFinal = true;
    }
  }

  get puedeAceptar(): boolean {
    return this.llegoAlFinal && this.aceptaTerminos && !this.enviando;
  }

  confirmar(): void {
    if (this.puedeAceptar) {
      this.aceptar.emit({ version: this.version });
    }
  }
}
