import type { jsPDF } from 'jspdf';
import { FilaReporte, IndicadoresReporte, ReporteRecorridos } from '../../core/services/reportes.service';

const MARGEN = 40;
const COLOR_ENCABEZADO: [number, number, number] = [15, 118, 110];

export const textoPuntualidad = (datos: IndicadoresReporte): string =>
  datos.porcentaje_puntualidad === null ? '—' : `${datos.porcentaje_puntualidad}%`;

export const textoAtraso = (datos: IndicadoresReporte): string =>
  datos.atraso_promedio_minutos === null ? '—' : `${datos.atraso_promedio_minutos} min`;

export const textoFecha = (iso: string): string => iso.split('-').reverse().join('/');

const nombreArchivo = (reporte: ReporteRecorridos): string => {
  const colegio = reporte.colegio_nombre
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase();
  return `reporte-${colegio}-${reporte.desde}-a-${reporte.hasta}.pdf`;
};

export async function descargarReportePdf(reporte: ReporteRecorridos): Promise<void> {
  // Se cargan al exportar para no agrandar la carga inicial del panel.
  const [{ jsPDF: Documento }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable')
  ]);
  const doc: jsPDF = new Documento({ orientation: 'landscape', unit: 'pt', format: 'a4' });
  const variosColegios = reporte.colegio_nombre === 'Todos los colegios';

  doc.setFontSize(18);
  doc.text('Reporte de recorridos - Rutas Seguras', MARGEN, 48);
  doc.setFontSize(11);
  doc.text(`Colegio: ${reporte.colegio_nombre}`, MARGEN, 70);
  doc.text(`Período: ${textoFecha(reporte.desde)} al ${textoFecha(reporte.hasta)}`, MARGEN, 86);
  doc.text(`Generado: ${new Date().toLocaleString('es-CL')}`, MARGEN, 102);

  const r = reporte.resumen;
  let posicionY = 118;
  const seccion = (titulo: string, cabecera: string[], cuerpo: (string | number)[][]) => {
    doc.setFontSize(13);
    if (posicionY > doc.internal.pageSize.getHeight() - 90) {
      doc.addPage();
      posicionY = 48;
    }
    doc.text(titulo, MARGEN, posicionY + 8);
    autoTable(doc, {
      startY: posicionY + 16,
      margin: { left: MARGEN, right: MARGEN, bottom: 40 },
      head: [cabecera],
      body: cuerpo,
      styles: { fontSize: 9, cellPadding: 4 },
      headStyles: { fillColor: COLOR_ENCABEZADO }
    });
    posicionY = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 22;
  };

  seccion(
    'Resumen',
    ['Recorridos', 'Puntualidad', 'Atraso promedio', 'Viajes', 'No subió', 'Inasistencias', 'Entregados', 'No se recibió', 'Emergencias'],
    [[r.recorridos, textoPuntualidad(r), textoAtraso(r), r.viajes, r.no_subio, r.inasistencias, r.entregados, r.no_recibidos, r.emergencias]]
  );

  const columnaColegio = variosColegios ? ['Colegio'] : [];
  const valorColegio = (fila: FilaReporte) => (variosColegios ? [fila.colegio_nombre] : []);
  const cabeceraOperacion = [...columnaColegio, 'Recorridos', 'Puntualidad', 'Atraso promedio', 'Viajes', 'No subió', 'Inasistencias', 'No se recibió', 'Emergencias'];
  const filaOperacion = (fila: FilaReporte) => [
    fila.nombre, ...valorColegio(fila), fila.recorridos, textoPuntualidad(fila), textoAtraso(fila),
    fila.viajes, fila.no_subio, fila.inasistencias, fila.no_recibidos, fila.emergencias
  ];

  seccion('Por ruta', ['Ruta', ...cabeceraOperacion], reporte.por_ruta.map(filaOperacion));
  seccion('Por conductor', ['Conductor', ...cabeceraOperacion], reporte.por_conductor.map(filaOperacion));
  seccion(
    'Por estudiante',
    ['Estudiante', ...columnaColegio, 'Recorridos', 'Viajó', 'De ellos, no recibidos', 'No subió', 'Faltó con aviso', 'Sin registro'],
    reporte.por_estudiante.map((fila) => [
      fila.nombre, ...valorColegio(fila), fila.recorridos, fila.viajes, fila.no_recibidos, fila.no_subio, fila.inasistencias, fila.sin_registro
    ])
  );

  const paginas = doc.getNumberOfPages();
  doc.setFontSize(9);
  for (let pagina = 1; pagina <= paginas; pagina++) {
    doc.setPage(pagina);
    doc.text(
      `Página ${pagina} de ${paginas}`,
      doc.internal.pageSize.getWidth() - MARGEN,
      doc.internal.pageSize.getHeight() - 20,
      { align: 'right' }
    );
  }

  doc.save(nombreArchivo(reporte));
}
