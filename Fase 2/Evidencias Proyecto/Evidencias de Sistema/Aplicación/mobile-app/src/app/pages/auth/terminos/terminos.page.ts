import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { IonContent } from '@ionic/angular/standalone';

import {
  AceptacionTerminosPanel,
  TerminosPanelComponent
} from '../../../components/terminos-panel/terminos-panel.component';
import { rutaInicioDe } from '../../../guards/auth.guard';
import { AuthService } from '../../../services/auth.service';
import { FeedbackService } from '../../../services/feedback.service';

@Component({
  selector: 'app-terminos',
  template: `
    <ion-content [scrollY]="false">
      <app-terminos-panel
        textoCancelar="Cerrar sesión"
        [enviando]="enviando"
        (aceptar)="aceptar($event)"
        (cancelar)="salir()">
      </app-terminos-panel>
    </ion-content>
  `,
  standalone: true,
  imports: [IonContent, TerminosPanelComponent]
})
export class TerminosPage {
  enviando = false;

  constructor(
    private authService: AuthService,
    private router: Router,
    private feedback: FeedbackService
  ) {}

  aceptar(aceptacion: AceptacionTerminosPanel): void {
    this.enviando = true;
    this.authService.aceptarTerminos(aceptacion.version).subscribe({
      next: () => {
        this.enviando = false;
        const usuario = this.authService.getUsuario();
        this.router.navigateByUrl(rutaInicioDe(usuario?.rol), { replaceUrl: true });
      },
      error: (err) => {
        this.enviando = false;
        void this.feedback.show(err?.error?.message || 'No se pudo registrar tu aceptación.', 'danger');
      }
    });
  }

  salir(): void {
    this.authService.logout();
    this.router.navigateByUrl('/home', { replaceUrl: true });
  }
}
