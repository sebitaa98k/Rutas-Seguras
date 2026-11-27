import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AbstractControl, FormBuilder, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

const coinciden = (grupo: AbstractControl): ValidationErrors | null =>
  grupo.get('nueva')?.value === grupo.get('confirmacion')?.value ? null : { distintas: true };

/** Recuperar la contraseña con un código de 6 dígitos enviado al correo. */
@Component({
  selector: 'app-recuperar-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './recuperar-password.component.html',
  styleUrl: '../login/login.component.scss'
})
export class RecuperarPasswordComponent {
  paso = signal<'correo' | 'codigo' | 'listo'>('correo');
  isLoading = signal(false);
  errorMessage = signal<string | null>(null);
  infoMessage = signal<string | null>(null);

  correoForm: FormGroup;
  codigoForm: FormGroup;

  constructor(private fb: FormBuilder, private authService: AuthService) {
    this.correoForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]]
    });
    this.codigoForm = this.fb.group({
      codigo: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
      nueva: ['', [Validators.required, Validators.minLength(8)]],
      confirmacion: ['', Validators.required]
    }, { validators: coinciden });
  }

  async solicitarCodigo(): Promise<void> {
    if (this.correoForm.invalid) {
      this.correoForm.markAllAsTouched();
      return;
    }
    this.isLoading.set(true);
    this.errorMessage.set(null);
    try {
      const mensaje = await this.authService.solicitarRecuperacion(this.correoForm.value.email);
      this.infoMessage.set(mensaje);
      this.paso.set('codigo');
    } catch (error: any) {
      this.errorMessage.set(error?.message || 'No se pudo solicitar el código.');
    } finally {
      this.isLoading.set(false);
    }
  }

  async confirmar(): Promise<void> {
    if (this.codigoForm.invalid) {
      this.codigoForm.markAllAsTouched();
      return;
    }
    this.isLoading.set(true);
    this.errorMessage.set(null);
    try {
      await this.authService.confirmarRecuperacion(
        this.correoForm.value.email,
        this.codigoForm.value.codigo,
        this.codigoForm.value.nueva
      );
      this.paso.set('listo');
    } catch (error: any) {
      this.errorMessage.set(error?.message || 'No se pudo cambiar la contraseña.');
    } finally {
      this.isLoading.set(false);
    }
  }

  volverAPedirCodigo(): void {
    this.codigoForm.reset();
    this.errorMessage.set(null);
    this.infoMessage.set(null);
    this.paso.set('correo');
  }
}
