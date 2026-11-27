import { Routes } from '@angular/router';
import { LoginComponent } from './features/auth/login/login.component';
import { DashboardLayoutComponent } from './features/dashboard/dashboard-layout.component';
import { DashboardHomeComponent } from './features/dashboard/dashboard-home/dashboard-home.component';
import { authGuard, cambioPasswordGuard } from './core/guards/auth.guard';
import { CambiarPasswordComponent } from './features/auth/cambiar-password/cambiar-password.component';
import { RecuperarPasswordComponent } from './features/auth/recuperar-password/recuperar-password.component';

// Conductores
import { ConductorListaComponent } from './features/conductor/conductor-lista/conductor-lista.component';
import { ConductorFormComponent } from './features/conductor/conductor-form/conductor-form.component';

// Apoderados
import { ApoderadoListaComponent } from './features/apoderado/apoderado-lista/apoderado-lista.component';
import { ApoderadoFormComponent } from './features/apoderado/apoderado-form/apoderado-form.component';
import { RutsHabilitadosComponent } from './features/apoderado/ruts-habilitados/ruts-habilitados.component';

// Delegados
import { DelegadoListaComponent } from './features/delegado/delegado-lista/delegado-lista.component';
import { DelegadoFormComponent } from './features/delegado/delegado-form/delegado-form.component';

// Furgones
import { FurgonesListaComponent } from './features/furgones/furgones-lista/furgones-lista.component';
import { FurgonesFormComponent } from './features/furgones/furgones-form/furgones-form.component';

// Rutas
import { RutasListaComponent } from './features/rutas/rutas-lista/rutas-lista.component';
import { RutasFormComponent } from './features/rutas/rutas-form/rutas-form.component';

// Auditoría
import { AuditoriaListaComponent } from './features/auditoria/auditoria-lista.component';

// Reportes
import { ReportesComponent } from './features/reportes/reportes.component';

// Papelera
import { PapeleraComponent } from './features/papelera/papelera.component';

// Colegios
import { ColegiosListaComponent } from './features/colegios/colegios-lista/colegios-lista.component';
import { ColegiosFormComponent } from './features/colegios/colegios-form/colegios-form.component';
import { MiColegioComponent } from './features/colegios/mi-colegio/mi-colegio.component';

// Estudiantes
import { EstudiantesListaComponent } from './features/estudiantes/estudiantes-lista/estudiantes-lista.component';
import { EstudiantesFormComponent } from './features/estudiantes/estudiantes-form/estudiantes-form.component';

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: 'recuperar-password',
    component: RecuperarPasswordComponent
  },
  {
    path: 'cambiar-password',
    component: CambiarPasswordComponent,
    canActivate: [cambioPasswordGuard]
  },
  {
    path: '',
    component: DashboardLayoutComponent,
    canActivate: [authGuard],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      },
      {
        path: 'dashboard',
        component: DashboardHomeComponent
      },
      // Colegios (Solo Administrador de Plataforma)
      { path: 'colegios', component: ColegiosListaComponent },
      { path: 'colegios/nuevo', component: ColegiosFormComponent },
      { path: 'colegios/editar/:id', component: ColegiosFormComponent },
      // Resumen del colegio para su administrador (datos y, en Avanzado, sus sedes).
      { path: 'mi-colegio', component: MiColegioComponent },

      // Estudiantes
      { path: 'estudiantes', component: EstudiantesListaComponent },
      { path: 'estudiantes/nuevo', component: EstudiantesFormComponent },
      { path: 'estudiantes/editar/:id', component: EstudiantesFormComponent },

      // Conductores
      { path: 'conductores', component: ConductorListaComponent },
      { path: 'conductores/nuevo', component: ConductorFormComponent },
      { path: 'conductores/editar/:id', component: ConductorFormComponent },
      
      // Apoderados
      { path: 'apoderados', component: ApoderadoListaComponent },
      { path: 'apoderados/ruts-habilitados', component: RutsHabilitadosComponent },
      { path: 'apoderados/nuevo', component: ApoderadoFormComponent },
      { path: 'apoderados/editar/:id', component: ApoderadoFormComponent },

      // Delegados
      { path: 'delegados', component: DelegadoListaComponent },
      { path: 'delegados/nuevo', component: DelegadoFormComponent },
      { path: 'delegados/editar/:id', component: DelegadoFormComponent },

      // Furgones
      { path: 'furgones', component: FurgonesListaComponent },
      { path: 'furgones/nuevo', component: FurgonesFormComponent },
      { path: 'furgones/editar/:id', component: FurgonesFormComponent },

      // Rutas
      { path: 'rutas', component: RutasListaComponent },
      { path: 'rutas/nuevo', component: RutasFormComponent },
      { path: 'rutas/editar/:id', component: RutasFormComponent },

      // Auditoría
      { path: 'auditoria', component: AuditoriaListaComponent },

      // Reportes
      { path: 'reportes', component: ReportesComponent },

      // Papelera: lo desactivado se reactiva desde aquí
      { path: 'papelera', component: PapeleraComponent }
    ]
  },
  {
    path: '**',
    redirectTo: 'login'
  }
];