import { Component, OnInit } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import {
  IonContent,
  IonInput,
  IonInputPasswordToggle,
  IonButton,
  IonSpinner,
  IonIcon
} from '@ionic/angular/standalone';

import { addIcons } from 'ionicons';
import {
  arrowBackOutline,
  shieldCheckmarkOutline,
  personOutline,
  callOutline,
  mailOutline,
  cardOutline,
  logOutOutline,
  checkmarkCircleOutline,
  lockClosedOutline,
  keyOutline
} from 'ionicons/icons';

import { AuthService, Usuario } from '../../../services/auth.service';
import { PushNotificationService } from '../../../services/push-notification.service';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';

/** Mismo mínimo que exige el servidor al cambiar la contraseña. */
const LARGO_MINIMO_PASSWORD = 8;

addIcons({
  arrowBackOutline,
  shieldCheckmarkOutline,
  personOutline,
  callOutline,
  mailOutline,
  cardOutline,
  logOutOutline,
  checkmarkCircleOutline,
  lockClosedOutline,
  keyOutline
});

@Component({
  selector: 'app-perfil-delegado',
  templateUrl: './perfil.page.html',
  styleUrls: ['./perfil.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    IonContent,
    IonInput,
    IonInputPasswordToggle,
    IonButton,
    IonSpinner,
    IonIcon
  ]
})
export class PerfilDelegadoPage implements OnInit {

  usuario: Usuario | null = null;

  nombre: string = '';
  apellido: string = '';
  telefono: string = '';

  editando: boolean = false;
  guardando: boolean = false;

  constructor(
    private authService: AuthService,
    private pushNotificationService: PushNotificationService,
    private router: Router,
    private location: Location,
    private feedback: FeedbackService
  ) {}

  ngOnInit() {
    this.cargarPerfil();
  }

  cargarPerfil() {
    this.usuario = this.authService.getUsuario();
    if (this.usuario) {
      this.nombre = this.usuario.first_name || '';
      this.apellido = this.usuario.last_name || '';
      this.telefono = this.usuario.telefono || '';
    }
  }

  toggleEditar() {
    this.editando = !this.editando;
    if (!this.editando) {
      this.cargarPerfil();
    }
  }

  guardarPerfil() {
    if (!this.nombre.trim()) {
      this.mostrarToast('El nombre no puede estar vacío.', 'warning');
      return;
    }

    this.guardando = true;
    this.authService.actualizarPerfilDelegado({
      first_name: this.nombre,
      last_name: this.apellido,
      telefono: this.telefono
    }).subscribe({
      next: async (res) => {
        this.guardando = false;
        this.editando = false;
        this.usuario = this.authService.getUsuario();
        await this.mostrarToast('Perfil actualizado correctamente.', 'success');
      },
      error: async (err) => {
        this.guardando = false;
        await this.mostrarToast('Error al actualizar el perfil.', 'danger');
      }
    });
  }

  editandoPassword = false;
  passwordActual = '';
  nuevaPassword = '';
  confirmarNuevaPassword = '';
  cargandoPassword = false;

  iniciarCambioPassword() {
    this.editandoPassword = true;
    this.passwordActual = '';
    this.nuevaPassword = '';
    this.confirmarNuevaPassword = '';
  }

  cancelarCambioPassword() {
    this.editandoPassword = false;
    this.passwordActual = '';
    this.nuevaPassword = '';
    this.confirmarNuevaPassword = '';
  }

  guardarPassword() {
    if (!this.passwordActual || !this.nuevaPassword || !this.confirmarNuevaPassword) {
      this.mostrarToast('Por favor completa todos los campos de contraseña.', 'warning');
      return;
    }
    if (this.nuevaPassword === this.passwordActual) {
      this.mostrarToast('La nueva contraseña no puede ser igual a la contraseña anterior.', 'danger');
      return;
    }
    if (this.nuevaPassword !== this.confirmarNuevaPassword) {
      this.mostrarToast('La nueva contraseña y su confirmación no coinciden.', 'warning');
      return;
    }
    if (this.nuevaPassword.length < LARGO_MINIMO_PASSWORD) {
      this.mostrarToast(`La nueva contraseña debe tener al menos ${LARGO_MINIMO_PASSWORD} caracteres.`, 'warning');
      return;
    }

    this.cargandoPassword = true;
    this.authService.cambiarPasswordPropia(this.passwordActual, this.nuevaPassword).subscribe({
      next: async () => {
        this.cargandoPassword = false;
        this.cancelarCambioPassword();
        await this.mostrarToast('Contraseña actualizada exitosamente.', 'success');
      },
      error: async (err) => {
        this.cargandoPassword = false;
        await this.mostrarToast(err?.error?.message || 'Error al actualizar la contraseña.', 'danger');
      }
    });
  }

  async cerrarSesion() {
    await this.pushNotificationService.cerrarSesionPush();
    // Vuelve al inicio de sesión de su propio rol.
    const rol = this.authService.getUsuario()?.rol;
    this.authService.logout();
    this.router.navigate(['/login'], { replaceUrl: true, queryParams: rol ? { rol } : {} });
  }

  volver() {
    this.location.back();
  }

  private async mostrarToast(mensaje: string, color: 'success' | 'danger' | 'warning') {
    await this.feedback.show(mensaje, color as FeedbackType, 3000);
  }
}
