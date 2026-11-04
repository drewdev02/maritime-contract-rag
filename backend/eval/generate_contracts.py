"""Generates the synthetic Naviera Portecho contracts used by the retrieval evaluation.

Usage (from ``backend/``): ``uv run python eval/generate_contracts.py``
The PDFs are deterministic in content and committed to the repository.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT_DIR = Path(__file__).parent / "contracts"

# Each contract is a list of pages; each page is a list of ("p", text) | ("t", rows) blocks.
CONTRACTS: dict[str, list[list[tuple[str, object]]]] = {
    "maersk_tarifas_2026.pdf": [
        [
            ("p", "CONTRATO DE SERVICIOS MARITIMOS - MAERSK LINE / NAVIERA PORTECHO"),
            (
                "p",
                "Clausula 1. Objeto. El presente contrato regula el transporte de contenedores "
                "entre el Puerto de Valparaiso y el Puerto de Rotterdam durante el ano 2026.",
            ),
            (
                "p",
                "Clausula 2. Vigencia. El contrato rige desde el 1 de enero de 2026 hasta el "
                "31 de diciembre de 2026 y se renueva automaticamente por periodos de 12 meses.",
            ),
        ],
        [
            ("p", "Clausula 3. Tarifas de flete por contenedor."),
            (
                "t",
                [
                    ["Tipo de contenedor", "Ruta", "Tarifa USD"],
                    ["20 pies (1 TEU)", "Valparaiso - Rotterdam", "1250"],
                    ["40 pies (2 TEU)", "Valparaiso - Rotterdam", "2100"],
                    ["40 pies High Cube", "Valparaiso - Rotterdam", "2250"],
                ],
            ),
            (
                "p",
                "Clausula 4. Dias libres. El cliente dispone de 7 dias libres en terminal "
                "antes de que se devenguen cargos por demora (demurrage).",
            ),
        ],
        [
            ("p", "Clausula 5. Penalizaciones por demora."),
            (
                "t",
                [
                    ["Dia de demora", "Recargo por contenedor USD"],
                    ["Dias 8 a 14", "75"],
                    ["Dias 15 en adelante", "150"],
                ],
            ),
            (
                "p",
                "Clausula 6. Cancelacion. La cancelacion de una reserva con menos de 72 horas "
                "de antelacion al zarpe genera una penalizacion equivalente al 50% del flete.",
            ),
        ],
    ],
    "cmacgm_condiciones_2026.pdf": [
        [
            ("p", "ACUERDO COMERCIAL - CMA CGM / NAVIERA PORTECHO"),
            (
                "p",
                "Clausula 1. Alcance. Servicio de transporte maritimo entre el Puerto de "
                "Valparaiso y el Puerto de Rotterdam para carga seca y refrigerada.",
            ),
            (
                "p",
                "Clausula 2. Dias libres. El cliente dispone de 10 dias libres en terminal "
                "antes de que se devenguen cargos por demora (demurrage).",
            ),
        ],
        [
            ("p", "Clausula 3. Tarifas de flete."),
            (
                "t",
                [
                    ["Tipo de contenedor", "Ruta", "Tarifa USD"],
                    ["20 pies (1 TEU)", "Valparaiso - Rotterdam", "1190"],
                    ["40 pies (2 TEU)", "Valparaiso - Rotterdam", "2040"],
                    ["Reefer 40 pies", "Valparaiso - Rotterdam", "3400"],
                ],
            ),
            (
                "p",
                "Clausula 4. Pagos. Las facturas se pagan a 45 dias desde la fecha de emision. "
                "El retraso en el pago devenga un interes moratorio del 1,5% mensual.",
            ),
        ],
    ],
    "msc_terminal_servicios.pdf": [
        [
            ("p", "CONTRATO DE SERVICIOS PORTUARIOS - MSC / NAVIERA PORTECHO"),
            (
                "p",
                "Clausula 1. Servicios de terminal. MSC presta servicios de carga, descarga y "
                "almacenaje en el Puerto de San Antonio.",
            ),
        ],
        [
            ("p", "Clausula 2. Tarifas de manipulacion y almacenaje."),
            (
                "t",
                [
                    ["Servicio", "Unidad", "Tarifa USD"],
                    ["Manipulacion (THC)", "Por contenedor", "210"],
                    ["Almacenaje", "Por dia", "18"],
                    ["Inspeccion aduanera", "Por contenedor", "95"],
                ],
            ),
            (
                "p",
                "Clausula 3. Responsabilidad por danos. MSC responde por danos a la carga "
                "ocurridos bajo su custodia hasta un limite de 50000 USD por evento.",
            ),
        ],
    ],
    "hapag_seguros_fuerza_mayor.pdf": [
        [
            ("p", "CONTRATO DE TRANSPORTE - HAPAG-LLOYD / NAVIERA PORTECHO"),
            (
                "p",
                "Clausula 1. Fuerza mayor. Ninguna parte sera responsable por incumplimientos "
                "causados por huelgas portuarias, huracanes o cierres de canal declarados por "
                "autoridad competente.",
            ),
        ],
        [
            ("p", "Clausula 2. Seguro de carga."),
            (
                "t",
                [
                    ["Cobertura", "Prima sobre valor CIF", "Deducible USD"],
                    ["Basica", "0,15%", "1000"],
                    ["Ampliada", "0,35%", "500"],
                ],
            ),
            (
                "p",
                "Clausula 3. Terminacion anticipada. Cualquiera de las partes puede terminar el "
                "contrato con un preaviso escrito de 90 dias.",
            ),
        ],
    ],
}


def build_pdf(path: Path, pages: list[list[tuple[str, object]]]) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter, invariant=True)
    story: list[object] = []
    for index, blocks in enumerate(pages):
        for kind, content in blocks:
            if kind == "p":
                story.append(Paragraph(str(content), styles["BodyText"]))
                story.append(Spacer(1, 12))
            else:
                table = Table(content)  # type: ignore[arg-type]
                table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
                story.append(table)
                story.append(Spacer(1, 12))
        if index < len(pages) - 1:
            story.append(PageBreak())
    doc.build(story)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, pages in CONTRACTS.items():
        build_pdf(OUT_DIR / name, pages)
        print(f"generated {name} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
