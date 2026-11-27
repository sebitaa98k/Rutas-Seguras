import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AbstractControl, FormBuilder, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

const coinciden = (grupo: AbstractControl): ValidationErrors | null =>
  grupo.get('nueva')?.value === grupo.get('confirmacion')?.value ? null : { distintas: true };

/** Pantalla obligatoria para quien entra con la contraseña inicial. */
@Component({
  selector: 'app-cambiar-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './cambiar-password.component.html',
  styleUrl: '../login/login.component.scss'
})
export class CambiarPasswordComponent {
  form: FormGroup;
  isLoading = signal(false);
  errorMessage = signal<string | null>(null);

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router
  ) {
    this.form = this.fb.group({
      actual: ['', Validators.required],
      nueva: ['', [Validators.required, Validators.minLength(8)]],
      confirmacion: ['', Validators.required]
    }, { validators: coinciden });
  }

  async onSubmit(): Promise<void> {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.isLoading.set(true);
    this.errorMessage.set(null);
    try {
      await this.authService.cambiarPassword(this.form.value.actual, this.form.value.nueva);
      this.router.navigate(['/dashboard']);
    } catch (error: any) {
      this.errorMessage.set(error?.message || 'No se pudo cambiar la contraseña.');
    } finally {
      this.isLoading.set(false);
    }
  }

  salir(): void {
    this.authService.logout();
  }
}
