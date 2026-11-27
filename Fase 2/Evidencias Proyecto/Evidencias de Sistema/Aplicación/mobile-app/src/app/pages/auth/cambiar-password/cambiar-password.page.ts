import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import {
  IonContent,
  IonInput,
  IonInputPasswordToggle,
  IonItem,
  IonButton,
  IonSpinner
} from '@ionic/angular/standalone';
import { AuthService } from '../../../services/auth.service';
import { rutaInicioDe } from '../../../guards/auth.guard';

const LARGO_MINIMO = 8;

/** Pantalla obligatoria para quien entra con la contraseña inicial. */
@Component({
  selector: 'app-cambiar-password',
  templateUrl: './cambiar-password.page.html',
  styleUrls: ['../recuperar-password/recuperar-password.page.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, IonContent, IonInput, IonInputPasswordToggle, IonItem, IonButton, IonSpinner]
})
export class CambiarPasswordPage {
  actual = '';
  nueva = '';
  confirmacion = '';
  cargando = false;
  mensaje = '';
  readonly largoMinimo = LARGO_MINIMO;

  constructor(private authService: AuthService, private router: Router) {}

  guardar() {
    this.mensaje = '';
    if (!this.actual || !this.nueva) {
      this.mensaje = 'Completa todos los campos.';
      return;
    }
    if (this.nueva.length < LARGO_MINIMO) {
      this.mensaje = `La nueva contraseña debe tener al menos ${LARGO_MINIMO} caracteres.`;
      return;
    }
    if (this.nueva !== this.confirmacion) {
      this.mensaje = 'Las contraseñas no coinciden.';
      return;
    }
    this.cargando = true;
    this.authService.cambiarPasswordPropia(this.actual, this.nueva).subscribe({
      next: () => {
        this.cargando = false;
        const usuario = this.authService.getUsuario();
        this.router.navigateByUrl(rutaInicioDe(usuario?.rol), { replaceUrl: true });
      },
      error: (err) => {
        this.cargando = false;
        this.mensaje = err?.error?.message || 'No se pudo cambiar la contraseña.';
      }
    });
  }

  salir() {
    this.authService.logout();
    this.router.navigateByUrl('/home', { replaceUrl: true });
  }
}
