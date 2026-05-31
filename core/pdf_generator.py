"""Generation du PDF officiel d'attestation de conge - une seule page A4 institutionnelle."""
import os
from datetime import datetime
from io import BytesIO

from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# --- Constantes design ------------------------------------------------------
PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
NAVY = colors.HexColor('#0b2545')
NAVY_DARK = colors.HexColor('#06182f')
GOLD = colors.HexColor('#c9a227')
GREEN = colors.HexColor('#16a34a')
RED = colors.HexColor('#dc2626')
GREY_TEXT = colors.HexColor('#1f2937')
GREY_LIGHT = colors.HexColor('#6b7280')
GREY_BG = colors.HexColor('#f3f4f6')
GREY_BORDER = colors.HexColor('#d1d5db')

LOGO_PATH = os.path.join(settings.BASE_DIR, 'static', 'logocsig.jpg')


# --- Helpers ----------------------------------------------------------------
def _draw_state_header(c):
    """Bandeau du haut : Republique de Guinee + CSIG."""
    # Bandeau navy
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 32 * mm, PAGE_W, 32 * mm, fill=1, stroke=0)
    # Liseret or
    c.setFillColor(GOLD)
    c.rect(0, PAGE_H - 33 * mm, PAGE_W, 1 * mm, fill=1, stroke=0)

    # Logo a gauche
    if os.path.isfile(LOGO_PATH):
        try:
            c.drawImage(
                ImageReader(LOGO_PATH),
                MARGIN_X, PAGE_H - 28 * mm,
                width=22 * mm, height=22 * mm,
                preserveAspectRatio=True, mask='auto',
            )
        except Exception:
            pass

    # Republique au centre / droite
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(MARGIN_X + 28 * mm, PAGE_H - 11 * mm, "REPUBLIQUE DE GUINEE")
    c.setFont('Helvetica-Oblique', 8)
    c.drawString(MARGIN_X + 28 * mm, PAGE_H - 15 * mm, "Travail - Justice - Solidarite")

    c.setFont('Helvetica-Bold', 12)
    c.drawString(MARGIN_X + 28 * mm, PAGE_H - 21 * mm,
                 "CITE DES SCIENCES ET DE L'INNOVATION DE GUINEE")
    c.setFont('Helvetica', 8)
    c.setFillColor(colors.HexColor('#cbd5e1'))
    c.drawString(MARGIN_X + 28 * mm, PAGE_H - 25 * mm,
                 "Direction Generale - Centre de Suivi et d'Information de Gestion")

    # Reference a droite
    c.setFillColor(colors.white)
    c.setFont('Helvetica', 8)


def _draw_title_band(c, leave):
    """Bande titre du document."""
    y = PAGE_H - 45 * mm
    # Trait horizontal
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.6)
    c.line(MARGIN_X, y + 2 * mm, PAGE_W - MARGIN_X, y + 2 * mm)

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(PAGE_W / 2, y - 4 * mm, "ATTESTATION DE CONGE")

    c.setFillColor(GOLD)
    c.setLineWidth(1.2)
    c.setStrokeColor(GOLD)
    c.line(PAGE_W / 2 - 25 * mm, y - 7 * mm, PAGE_W / 2 + 25 * mm, y - 7 * mm)

    # Reference + date emission
    ref = f"N° CSIG/CONG/{leave.id:05d}/{datetime.now().year}"
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 9)
    c.drawString(MARGIN_X, y - 14 * mm, f"Reference : {ref}")
    c.drawRightString(PAGE_W - MARGIN_X, y - 14 * mm,
                      f"Conakry, le {datetime.now().strftime('%d/%m/%Y')}")


def _draw_section_title(c, x, y, label):
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(x, y, label.upper())
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    text_w = c.stringWidth(label.upper(), 'Helvetica-Bold', 10)
    c.line(x, y - 1.5 * mm, x + text_w, y - 1.5 * mm)


def _draw_kv_row(c, x, y, label, value, label_w=42 * mm):
    c.setFillColor(GREY_LIGHT)
    c.setFont('Helvetica', 9)
    c.drawString(x, y, label)
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(x + label_w, y, value or '-')


def _draw_info_box(c, leave):
    """Bloc 'Informations du demandeur' + 'Details du conge' cote a cote."""
    top = PAGE_H - 65 * mm
    box_h = 48 * mm
    col_w = (PAGE_W - 2 * MARGIN_X - 6 * mm) / 2

    # --- Colonne 1 : Demandeur ---
    x1 = MARGIN_X
    c.setFillColor(GREY_BG)
    c.setStrokeColor(GREY_BORDER)
    c.setLineWidth(0.5)
    c.roundRect(x1, top - box_h, col_w, box_h, 3, fill=1, stroke=1)

    _draw_section_title(c, x1 + 4 * mm, top - 6 * mm, "Demandeur")
    yy = top - 13 * mm
    direction_name = leave.direction.name if leave.direction else '-'
    _draw_kv_row(c, x1 + 4 * mm, yy, "Nom complet", leave.employee.name, 28 * mm)
    yy -= 7 * mm
    _draw_kv_row(c, x1 + 4 * mm, yy, "Direction", direction_name, 28 * mm)
    yy -= 7 * mm
    if getattr(leave.employee, 'role', None):
        _draw_kv_row(c, x1 + 4 * mm, yy, "Fonction", leave.employee.role, 28 * mm)
        yy -= 7 * mm
    if getattr(leave.employee, 'email', None):
        _draw_kv_row(c, x1 + 4 * mm, yy, "Email", leave.employee.email, 28 * mm)

    # --- Colonne 2 : Details du conge ---
    x2 = x1 + col_w + 6 * mm
    c.setFillColor(GREY_BG)
    c.roundRect(x2, top - box_h, col_w, box_h, 3, fill=1, stroke=1)

    _draw_section_title(c, x2 + 4 * mm, top - 6 * mm, "Details du conge")
    yy = top - 13 * mm
    _draw_kv_row(c, x2 + 4 * mm, yy, "Type", leave.get_leave_type_display(), 22 * mm)
    yy -= 7 * mm
    period = f"Du {leave.start_date.strftime('%d/%m/%Y')} au {leave.end_date.strftime('%d/%m/%Y')}"
    _draw_kv_row(c, x2 + 4 * mm, yy, "Periode", period, 22 * mm)
    yy -= 7 * mm
    _draw_kv_row(c, x2 + 4 * mm, yy, "Duree", f"{leave.days_count} jour(s)", 22 * mm)
    yy -= 7 * mm
    if leave.replacement:
        _draw_kv_row(c, x2 + 4 * mm, yy, "Suppleant", leave.replacement, 22 * mm)


def _draw_motif(c, leave):
    """Encadre 'Motif'."""
    top = PAGE_H - 117 * mm
    h = 16 * mm
    c.setStrokeColor(GREY_BORDER)
    c.setFillColor(colors.white)
    c.setLineWidth(0.5)
    c.roundRect(MARGIN_X, top - h, PAGE_W - 2 * MARGIN_X, h, 3, fill=1, stroke=1)

    _draw_section_title(c, MARGIN_X + 4 * mm, top - 6 * mm, "Motif")
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 9)
    motif = (leave.reason or '-')[:240]
    c.drawString(MARGIN_X + 4 * mm, top - 12 * mm, motif)


def _draw_workflow(c, leave):
    """Tableau circuit de validation."""
    top = PAGE_H - 138 * mm
    inner_x = MARGIN_X
    inner_w = PAGE_W - 2 * MARGIN_X

    _draw_section_title(c, inner_x, top, "Circuit de validation")

    # Header tableau
    header_y = top - 4 * mm
    row_h = 7 * mm
    col_widths = [38 * mm, 50 * mm, 32 * mm, 0]  # 4eme = restant
    col_widths[3] = inner_w - sum(col_widths[:3])
    col_x = [inner_x]
    for w in col_widths[:-1]:
        col_x.append(col_x[-1] + w)

    c.setFillColor(NAVY)
    c.rect(inner_x, header_y - row_h, inner_w, row_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 9)
    headers = ["Etape", "Validateur", "Date", "Decision"]
    for i, h in enumerate(headers):
        c.drawString(col_x[i] + 3 * mm, header_y - row_h + 2.2 * mm, h)

    # Rows
    rows = []
    if leave.manager_user:
        rows.append((
            "Avis hierarchique",
            leave.manager_user.get_full_name() or leave.manager_user.username,
            leave.manager_decision_at.strftime('%d/%m/%Y %H:%M') if leave.manager_decision_at else '-',
            leave.get_manager_decision_display() if leave.manager_decision else '-',
            leave.manager_decision == 'favorable',
        ))
    if leave.hr_user:
        rows.append((
            "Verification RH",
            leave.hr_user.get_full_name() or leave.hr_user.username,
            leave.hr_decision_at.strftime('%d/%m/%Y %H:%M') if leave.hr_decision_at else '-',
            leave.get_hr_decision_display() if leave.hr_decision else '-',
            leave.hr_decision == 'conforme',
        ))
    if leave.final_user:
        rows.append((
            "Decision finale",
            leave.final_user.get_full_name() or leave.final_user.username,
            leave.final_decision_at.strftime('%d/%m/%Y %H:%M') if leave.final_decision_at else '-',
            leave.get_final_decision_display() if leave.final_decision else '-',
            leave.final_decision == 'approuve',
        ))

    y = header_y - row_h
    c.setStrokeColor(GREY_BORDER)
    c.setLineWidth(0.4)
    for idx, row in enumerate(rows):
        y -= row_h
        if idx % 2 == 0:
            c.setFillColor(colors.HexColor('#f8fafc'))
            c.rect(inner_x, y, inner_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(GREY_BORDER)
        c.rect(inner_x, y, inner_w, row_h, fill=0, stroke=1)
        c.setFillColor(GREY_TEXT)
        c.setFont('Helvetica', 9)
        c.drawString(col_x[0] + 3 * mm, y + 2.2 * mm, row[0])
        c.drawString(col_x[1] + 3 * mm, y + 2.2 * mm, str(row[1])[:38])
        c.drawString(col_x[2] + 3 * mm, y + 2.2 * mm, row[2])
        # Decision avec couleur
        c.setFillColor(GREEN if row[4] else RED)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(col_x[3] + 3 * mm, y + 2.2 * mm, row[3])

    return y  # bottom Y du tableau


def _draw_decision_stamp(c, leave, table_bottom_y):
    """Bandeau de decision finale + bloc signature."""
    approved = leave.status == 'approuvee'
    color = GREEN if approved else RED
    label = "APPROUVE" if approved else "REJETE"

    # Bandeau de decision
    band_top = table_bottom_y - 8 * mm
    band_h = 14 * mm
    c.setFillColor(color)
    c.roundRect(MARGIN_X, band_top - band_h, PAGE_W - 2 * MARGIN_X, band_h, 4, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(PAGE_W / 2, band_top - band_h / 2 - 1.5 * mm,
                        f"DECISION FINALE  -  {label}")

    # Bloc signature (a droite)
    sig_top = band_top - band_h - 6 * mm
    sig_w = 70 * mm
    sig_h = 28 * mm
    sig_x = PAGE_W - MARGIN_X - sig_w
    c.setStrokeColor(GREY_BORDER)
    c.setFillColor(colors.white)
    c.setLineWidth(0.5)
    c.roundRect(sig_x, sig_top - sig_h, sig_w, sig_h, 3, fill=1, stroke=1)

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(sig_x + 3 * mm, sig_top - 5 * mm, "VALIDE PAR")
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 9)
    if leave.final_user:
        name = leave.final_user.get_full_name() or leave.final_user.username
        c.drawString(sig_x + 3 * mm, sig_top - 10 * mm, name)
        c.setFillColor(GREY_LIGHT)
        c.setFont('Helvetica-Oblique', 8)
        c.drawString(sig_x + 3 * mm, sig_top - 14 * mm, "Direction Generale - CSIG")
        if leave.final_decision_at:
            c.drawString(sig_x + 3 * mm, sig_top - 18 * mm,
                         f"Le {leave.final_decision_at.strftime('%d/%m/%Y a %H:%M')}")

    # Zone reservee au cachet (a apposer manuellement apres impression)
    c.setStrokeColor(GREY_BORDER)
    c.setLineWidth(0.4)
    c.setDash(2, 2)
    cx = sig_x + sig_w - 14 * mm
    cy = sig_top - sig_h + 9 * mm
    c.circle(cx, cy, 8 * mm, stroke=1, fill=0)
    c.setDash()
    c.setFillColor(GREY_LIGHT)
    c.setFont('Helvetica-Oblique', 6)
    c.drawCentredString(cx, cy - 0.5 * mm, "Cachet")


def _draw_footer(c, leave):
    """Pied de page institutionnel."""
    # Liseret or en bas
    c.setFillColor(GOLD)
    c.rect(0, 12 * mm, PAGE_W, 0.6 * mm, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, 12 * mm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(MARGIN_X, 7 * mm, "Cite des Sciences et de l'Innovation de Guinee (CSIG)")
    c.setFont('Helvetica', 7.5)
    c.setFillColor(colors.HexColor('#cbd5e1'))
    c.drawString(MARGIN_X, 3.5 * mm,
                 "Document officiel genere par le systeme de gestion des conges - CSIG Dashboard")

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Oblique', 7.5)
    c.drawRightString(PAGE_W - MARGIN_X, 5 * mm,
                      f"Page 1/1  -  Ref. CSIG/CONG/{leave.id:05d}/{datetime.now().year}")


def _draw_watermark(c, leave):
    """Watermark diagonal en arriere plan."""
    c.saveState()
    c.translate(PAGE_W / 2, PAGE_H / 2)
    c.rotate(30)
    c.setFillColor(colors.HexColor('#e5e7eb'))
    c.setFont('Helvetica-Bold', 70)
    label = "OFFICIEL" if leave.status == 'approuvee' else "REJETE"
    c.drawCentredString(0, 0, label)
    c.restoreState()


# --- API publique -----------------------------------------------------------
def generate_leave_approval_pdf(leave, output_path=None):
    """Genere le PDF officiel d'attestation de conge sur une seule page A4."""
    if output_path is None:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
    else:
        c = canvas.Canvas(output_path, pagesize=A4)

    c.setTitle(f"Attestation de conge - {leave.employee.name} - {leave.id}")
    c.setAuthor("CSIG - Direction Generale")
    c.setSubject("Attestation officielle de conge")

    # Watermark en fond
    _draw_watermark(c, leave)

    # Composition
    _draw_state_header(c)
    _draw_title_band(c, leave)
    _draw_info_box(c, leave)
    _draw_motif(c, leave)
    table_bottom_y = _draw_workflow(c, leave)
    _draw_decision_stamp(c, leave, table_bottom_y)
    _draw_footer(c, leave)

    c.showPage()
    c.save()

    if output_path is None:
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
    return output_path
