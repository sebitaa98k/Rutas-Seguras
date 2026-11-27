import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import {
  IonContent,
  IonButton,
  IonMenuToggle,
  IonIcon,
  IonItem,
  IonInput,
  IonInputPasswordToggle,
  IonSpinner,
  MenuController
} from '@ionic/angular/standalone';

import { addIcons } from 'ionicons';
import {
  personOutline,
  mailOutline,
  cardOutline,
  callOutline,
  ribbonOutline,
  shieldCheckmarkOutline,
  menuOutline,
  arrowBackOutline,
  logOutOutline,
  busOutline,
  idCardOutline,
  checkmarkCircleOutline,
  keyOutline,
  closeOutline
} from 'ionicons/icons';

import { AuthService, Usuario } from '../../../services/auth.service';
import { PushNotificationService } from '../../../services/push-notification.service';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';

/** Mismo mínimo que exige el servidor al cambiar la contraseña. */
const LARGO_MINIMO_PASSWORD = 8;

addIcons({
  personOutline,
  mailOutline,
  cardOutline,
  callOutline,
  ribbonOutline,
  shieldCheckmarkOutline,
  menuOutline,
  arrowBackOutline,
  logOutOutline,
  busOutline,
  idCardOutline,
  checkmarkCircleOutline,
  keyOutline,
  closeOutline
});

@Component({
  selector: 'app-perfil-conductor',
  templateUrl: './perfil.page.html',
  styleUrls: ['./perfil.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    IonContent,
    IonButton,
    IonMenuToggle,
    IonIcon,
    IonItem,
    IonInput,
    IonInputPasswordToggle,
    IonSpinner
  ]
})
export class PerfilPage implements OnInit {

  usuario: Usuario | null = null;

  constructor(
    private authService: AuthService,
    private pushNotificationService: PushNotificationService,
    private router: Router,
    private feedback: FeedbackService,
    private menuController: MenuController
  ) {}

  ngOnInit() {
    this.cargarUsuario();
  }

  ionViewWillEnter() {
    this.cargarUsuario();
  }

  cargarUsuario() {
    this.usuario = this.authService.getUsuario();
  }

  get nombreCompleto(): string {
    if (!this.usuario) return 'Conductor';
    const full = `${this.usuario.first_name || ''} ${this.usuario.last_name || ''}`.trim();
    return full || this.usuario.email || 'Conductor';
  }

  get iniciales(): string {
    if (!this.usuario) return 'C';
    const fn = (this.usuario.first_name || '').charAt(0);
    const ln = (this.usuario.last_name || '').charAt(0);
    return (fn + ln).toUpperCase() || 'C';
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
    await this.menuController.close('main-menu');
    await this.mostrarToast('Has cerrado sesión correctamente.', 'success');
    this.router.navigate(['/login'], { replaceUrl: true, queryParams: rol ? { rol } : {} });
  }

  private async mostrarToast(mensaje: string, color: 'success' | 'danger' | 'warning') {
    await this.feedback.show(mensaje, color as FeedbackType);
  }
}
