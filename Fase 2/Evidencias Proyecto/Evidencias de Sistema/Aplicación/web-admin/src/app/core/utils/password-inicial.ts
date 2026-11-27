/** Muestra una sola vez la contraseña inicial generada para entregársela a la persona. */
export function avisarPasswordInicial(respuesta: { password_inicial?: string } | null | undefined): void {
  const password = respuesta?.password_inicial;
  if (!password) {
    return;
  }
  alert(
    `Cuenta creada.\n\nContraseña inicial: ${password}\n\n` +
    'Entrégasela a la persona. Al ingresar por primera vez deberá cambiarla.'
  );
}
