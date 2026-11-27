import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import {
  IonContent,
  IonInput,
  IonInputPasswordToggle,
  IonItem,
  IonButton,
  IonSpinner,
  IonSelect,
  IonSelectOption,
  IonModal
} from '@ionic/angular/standalone';

import { AuthService, ColegioRegistro } from '../../../services/auth.service';
import {
  AceptacionTerminosPanel,
  TerminosPanelComponent
} from '../../../components/terminos-panel/terminos-panel.component';
import { FeedbackService, FeedbackType } from '../../../services/feedback.service';

@Component({
  selector: 'app-registro',
  templateUrl: './registro.page.html',
  styleUrls: ['./registro.page.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    IonContent,
    IonInput,
    IonInputPasswordToggle,
    IonItem,
    IonButton,
    IonSpinner,
    IonSelect,
    IonSelectOption,
    IonModal,
    TerminosPanelComponent
  ]
})
export class RegistroPage implements OnInit {

  nombre: string = '';
  apellido: string = '';
  rut: string = '';
  email: string = '';
  telefono: string = '';
  password: string = '';
  confirmarPassword: string = '';

  colegios: ColegioRegistro[] = [];
  colegioId?: number;
  contactoColegio: { nombre: string; telefono: string; email: string } | null = null;

  terminosAbiertos = false;
  versionTerminos = '';
  cargando: boolean = false;
  errorMensaje: string = '';

  constructor(
    private authService: AuthService,
    private router: Router,
    private feedback: FeedbackService
  ) {}

  ngOnInit(): void {
    this.authService.obtenerColegiosRegistro().subscribe({
      next: (colegios) => {
        this.colegios = colegios || [];
      },
      error: () => {
        this.errorMensaje = 'No se pudo cargar la lista de colegios. Revisa tu conexión.';
      }
    });
  }

  get nombreColegio(): string {
    return this.colegios.find((colegio) => colegio.id === this.colegioId)?.nombre || '';
  }

  onColegioChange(event: CustomEvent<{ value: string | null | undefined }>): void {
    const valor = Number(event.detail.value);
    this.colegioId = Number.isInteger(valor) && valor > 0 ? valor : undefined;
    this.contactoColegio = null;
  }

  aceptarTerminos(aceptacion: AceptacionTerminosPanel): void {
    this.versionTerminos = aceptacion.version;
    this.terminosAbiertos = false;
  }

  async onSubmit() {
    this.errorMensaje = '';
    this.contactoColegio = null;

    if (!this.colegioId) {
      this.errorMensaje = 'Selecciona el colegio de tu hijo o hija.';
      await this.mostrarToast(this.errorMensaje, 'warning');
      return;
    }

    if (!this.nombre.trim() || !this.apellido.trim() || !this.rut.trim() || !this.telefono.trim() || !this.email.trim() || !this.password) {
      this.errorMensaje = 'Por favor completa todos los campos obligatorios.';
      await this.mostrarToast(this.errorMensaje, 'warning');
      return;
    }

    if (this.password !== this.confirmarPassword) {
      this.errorMensaje = 'Las contraseñas no coinciden.';
      await this.mostrarToast(this.errorMensaje, 'danger');
      return;
    }

    if (!this.versionTerminos) {
      this.errorMensaje = 'Debes leer y aceptar los términos y condiciones para crear tu cuenta.';
      await this.mostrarToast(this.errorMensaje, 'warning');
      return;
    }

    this.cargando = true;

    const datos = {
      nombre: this.nombre,
      apellido: this.apellido,
      rut: this.rut,
      email: this.email,
      telefono: this.telefono,
      password: this.password,
      colegio_id: this.colegioId,
      acepta_terminos: true,
      version_terminos: this.versionTerminos
    };

    this.authService.registrarApoderado(datos).subscribe({
      next: async (res) => {
        this.cargando = false;
        await this.mostrarToast(res.message || 'Registro completado exitosamente.', 'success');
        this.router.navigate(['/apoderado/inicio']);
      },
      error: async (err) => {
        this.cargando = false;
        let mensaje = 'Ocurrió un error al registrar la cuenta.';
        if (err.error) {
          if (err.error.message) {
            mensaje = err.error.message;
          }
          if (err.error.errors) {
            const keys = Object.keys(err.error.errors);
            if (keys.length > 0) {
              const primerError = err.error.errors[keys[0]];
              mensaje = Array.isArray(primerError) ? primerError[0] : primerError;
            }
          }
        }
        this.errorMensaje = mensaje;
        this.contactoColegio = err.error?.contacto_colegio || null;
        // Si los términos cambiaron mientras llenaba el formulario, debe leerlos otra vez.
        if (err.error?.errors?.terminos) {
          this.versionTerminos = '';
        }
        await this.mostrarToast(mensaje, 'danger');
      }
    });
  }

  private async mostrarToast(mensaje: string, color: 'success' | 'danger' | 'warning') {
    await this.feedback.show(mensaje, color as FeedbackType);
  }

}
