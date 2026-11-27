/** Cursos de un estudiante. Es la misma lista que usa la app del apoderado al agregar un hijo. */
export const CURSOS: string[] = [
  'Prekínder', 'Kínder',
  '1° Básico', '2° Básico', '3° Básico', '4° Básico',
  '5° Básico', '6° Básico', '7° Básico', '8° Básico',
  '1° Medio', '2° Medio', '3° Medio', '4° Medio',
];

/** Si el estudiante tiene guardado un curso que no está en la lista, se agrega para no perderlo al editar. */
export function cursosCon(actual: string | null | undefined): string[] {
  return actual && !CURSOS.includes(actual) ? [...CURSOS, actual] : CURSOS;
}
