import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import {
  IonContent,
  IonButton,
  IonMenuToggle
} from '@ionic/angular/standalone';

@Component({
  selector: 'app-inicio-apoderado',
  templateUrl: './inicio.page.html',
  styleUrls: ['./inicio.page.scss'],
  standalone: true,
  imports: [
    RouterLink,
    IonContent,
    IonButton,
    IonMenuToggle
  ]
})
export class InicioPage {}
