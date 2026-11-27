import { Injectable } from '@angular/core';
import { ToastController } from '@ionic/angular/standalone';

export type FeedbackType = 'success' | 'warning' | 'danger' | 'info';

@Injectable({ providedIn: 'root' })
export class FeedbackService {
  constructor(private toastController: ToastController) {}

  async show(
    message: string,
    type: FeedbackType = 'info',
    duration = 3000
  ): Promise<void> {
    const toast = await this.toastController.create({
      message,
      duration,
      position: 'bottom',
      color: type === 'info' ? 'primary' : type,
      cssClass: ['rs-toast', `rs-toast--${type}`]
    });

    await toast.present();
  }

  success(message: string, duration?: number): Promise<void> {
    return this.show(message, 'success', duration);
  }

  warning(message: string, duration?: number): Promise<void> {
    return this.show(message, 'warning', duration);
  }

  error(message: string, duration?: number): Promise<void> {
    return this.show(message, 'danger', duration);
  }

  info(message: string, duration?: number): Promise<void> {
    return this.show(message, 'info', duration);
  }
}
