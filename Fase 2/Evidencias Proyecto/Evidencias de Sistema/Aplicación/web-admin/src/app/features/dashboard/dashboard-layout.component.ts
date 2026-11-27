import { Component, signal, inject, OnInit, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { ColegioService } from '../../core/services/colegio.service';

interface NavItem {
  label: string;
  route: string;
  icon: string;
}

@Component({
  selector: 'app-dashboard-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive, FormsModule],
  templateUrl: './dashboard-layout.component.html',
  styleUrl: './dashboard-layout.component.scss'
})
export class DashboardLayoutComponent implements OnInit {
  protected authService = inject(AuthService);
  protected colegioService = inject(ColegioService);

  sidebarOpen = signal(false);
  sidebarCollapsed = signal(false);
  /** El nombre del pie del menú corre como letrero solo si no cabe y el mouse está encima. */
  nombreDesplazando = signal(false);

  user = computed(() => this.authService.currentUser());
  esAdminPlataforma = computed(() => {
    const u = this.user();
    return u?.role === 'ADMIN_PLATAFORMA' || u?.role === 'ADMIN';
  });

  navItems = computed<NavItem[]>(() => {
    const baseNav: NavItem[] = [
      { label: 'Dashboard', route: '/dashboard', icon: 'dashboard' }
    ];

    if (this.esAdminPlataforma()) {
      baseNav.push({ label: 'Colegios', route: '/colegios', icon: 'building' });
      baseNav.push(
        { label: 'Estudiantes', route: '/estudiantes', icon: 'graduation-cap' },
        { label: 'Apoderados', route: '/apoderados', icon: 'users' },
        { label: 'Conductores', route: '/conductores', icon: 'steering-wheel' },
        { label: 'Delegados', route: '/delegados', icon: 'shield' },
        { label: 'Furgones', route: '/furgones', icon: 'bus' },
        { label: 'Rutas', route: '/rutas', icon: 'map-pin' },
        { label: 'Auditoría', route: '/auditoria', icon: 'clipboard' },
        { label: 'Reportes', route: '/reportes', icon: 'chart' },
        { label: 'Papelera', route: '/papelera', icon: 'trash' }
      );
    } else {
      const colegioId = this.user()?.colegioId;
      if (colegioId) {
        baseNav.push({ label: 'Mi colegio', route: '/mi-colegio', icon: 'building' });
      }
      baseNav.push(
        { label: 'Apoderados', route: '/apoderados', icon: 'users' },
        { label: 'Estudiantes', route: '/estudiantes', icon: 'graduation-cap' },
        { label: 'Conductores', route: '/conductores', icon: 'steering-wheel' },
        { label: 'Furgones', route: '/furgones', icon: 'bus' },
        { label: 'Rutas', route: '/rutas', icon: 'map-pin' },
        { label: 'Delegados', route: '/delegados', icon: 'shield' },
        { label: 'Auditoría', route: '/auditoria', icon: 'clipboard' },
        { label: 'Reportes', route: '/reportes', icon: 'chart' },
        { label: 'Papelera', route: '/papelera', icon: 'trash' }
      );
    }

    return baseNav;
  });

  ngOnInit(): void {
    try {
      this.sidebarCollapsed.set(localStorage.getItem(this.sidebarStorageKey()) === 'true');
    } catch {
      this.sidebarCollapsed.set(false);
    }

    if (this.esAdminPlataforma()) {
      void this.colegioService.getColegios().catch(error => {
        console.error('No fue posible cargar el selector global de colegios:', error);
      });
    }
  }

  /** Recibe el id elegido, o null para "Todos los colegios". */
  onColegioChange(valor: number | string | null): void {
    const id = valor === null || valor === '' ? null : Number(valor);
    this.colegioService.setSelectedColegioId(id !== null && Number.isInteger(id) && id > 0 ? id : null);
    // Disparar recarga ligera o evento si es necesario
    window.dispatchEvent(new Event('colegio-changed'));
  }

  alEntrarNombre(evento: MouseEvent): void {
    const texto = (evento.currentTarget as HTMLElement).querySelector('.user-name__texto') as HTMLElement | null;
    this.nombreDesplazando.set(!!texto && texto.scrollWidth > texto.clientWidth);
  }

  toggleSidebar(): void {
    this.sidebarOpen.update(val => !val);
  }

  toggleSidebarCollapsed(): void {
    this.sidebarCollapsed.update(value => !value);
    try {
      localStorage.setItem(this.sidebarStorageKey(), String(this.sidebarCollapsed()));
    } catch {
      // El layout sigue funcionando aunque el navegador bloquee localStorage.
    }
  }

  closeSidebar(): void {
    this.sidebarOpen.set(false);
  }

  logout(): void {
    this.authService.logout();
  }

  private sidebarStorageKey(): string {
    return `rutas-seguras:sidebar-collapsed:${this.user()?.role || 'admin'}`;
  }
}
