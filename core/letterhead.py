"""Papier en-tête officiel CSIG — fond de page réutilisable pour les exports.

Les gabarits Word officiels (`New Papier en tete CSIG *.docx`) portent un fond de
page complet : image ``word/media/image1.jpg`` ancrée « derrière le texte »
(``behindDoc="1"``) dans ``header1.xml``. Elle contient le bandeau bleu du haut
(logos MESRS + CSIG) et le pied de page institutionnel (adresse Rogbané, tél.,
email, site, logos).

Les images ont été extraites dans ``assets/templates/`` :
``letterhead-portrait.jpg`` et ``letterhead-paysage.jpg``.

Ce module expose, pour chaque orientation :
- la taille de page et les marges (issues des ``<w:pgMar>`` des gabarits),
- le tracé du fond de page (image pleine page, dessinée avant le contenu),
- la configuration de section (valeurs twips d'origine, pour tout export qui
  régénère un document Word type docx),
- une orientation par défaut par type d'export.

Aucun export Word n'existe aujourd'hui dans l'application (tous les exports sont
des PDF ReportLab) : la fonction ``section_config`` est fournie telle quelle pour
un futur export docx, sans dépendance Node.js.
"""
import os

from django.conf import settings
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

# ---------------------------------------------------------------------------
# 1. Métriques brutes issues des gabarits Word (en twips, 1 pt = 20 twips)
# ---------------------------------------------------------------------------
# <w:pgSz w:w="11906" w:h="16838"/> + <w:pgMar .../>
PORTRAIT_TWIPS = {
    'page_w': 11906, 'page_h': 16838,
    'top': 2410, 'right': 1417, 'bottom': 1134, 'left': 1417,
    'header': 0, 'footer': 708,
}
# <w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>
# Piège du gabarit : left=0 fait coller le contenu au bord ; on force 1417.
LANDSCAPE_TWIPS = {
    'page_w': 16838, 'page_h': 11906,
    'top': 1843, 'right': 1417, 'bottom': 993, 'left': 1417,
    'header': 0, 'footer': 708,
}

TWIP_PER_PT = 20.0

# Extensions des images ancrées (EMU) dans les gabarits, pour référence.
PORTRAIT_IMAGE_EMU = {'cx': 7594600, 'cy': 10742033, 'offset_h': -899795}
LANDSCAPE_IMAGE_EMU = {'cx': 10706345, 'cy': 7569200, 'offset_h': 0}

# Hauteur du bandeau (haut) et du pied, mesurées sur les images (mm).
PORTRAIT_BAND_MM = 41.1
PORTRAIT_FOOTER_MM = 17.1
LANDSCAPE_BAND_MM = 29.8
LANDSCAPE_FOOTER_MM = 16.9

# ---------------------------------------------------------------------------
# 2. Design system CSIG (contenu)
# ---------------------------------------------------------------------------
NAVY = '#003366'
GOLD = '#c9a227'

# ---------------------------------------------------------------------------
# 3. Fichiers d'images
# ---------------------------------------------------------------------------
LETTERHEAD_DIR = os.path.join(settings.BASE_DIR, 'assets', 'templates')
_IMAGE_FILES = {
    'portrait': 'letterhead-portrait.jpg',
    'landscape': 'letterhead-paysage.jpg',
}

# Orientation par type d'export. Portrait = rapports / fiches / notes ;
# paysage = exports à tableaux larges (listes, journaux, vues Table).
EXPORT_ORIENTATIONS = {
    'leave_attestation': 'portrait',
    'reports': 'portrait',
    'employees': 'landscape',
    'project_activities': 'landscape',
}


def _twips(orientation):
    return LANDSCAPE_TWIPS if orientation == 'landscape' else PORTRAIT_TWIPS


def image_path(orientation='portrait'):
    """Chemin absolu de l'image de fond pour l'orientation donnée."""
    filename = _IMAGE_FILES.get(orientation, _IMAGE_FILES['portrait'])
    return os.path.join(LETTERHEAD_DIR, filename)


def page_size(orientation='portrait'):
    """Taille de page ReportLab (points) pour l'orientation."""
    return landscape(A4) if orientation == 'landscape' else A4


def margins(orientation='portrait'):
    """Marges de contenu (points) dérivées des <w:pgMar> du gabarit.

    La marge gauche du paysage est forcée à 1417 twips (= 25 mm) au lieu de 0.
    """
    t = _twips(orientation)
    return {
        'top': t['top'] / TWIP_PER_PT,
        'bottom': t['bottom'] / TWIP_PER_PT,
        'left': t['left'] / TWIP_PER_PT,
        'right': t['right'] / TWIP_PER_PT,
    }


def band_mm(orientation='portrait'):
    return LANDSCAPE_BAND_MM if orientation == 'landscape' else PORTRAIT_BAND_MM


def footer_mm(orientation='portrait'):
    return LANDSCAPE_FOOTER_MM if orientation == 'landscape' else PORTRAIT_FOOTER_MM


def content_top_mm(orientation='portrait'):
    """Ordonnée (mm depuis le haut) où le contenu peut commencer sans toucher le bandeau."""
    page_h_mm = (_twips(orientation)['page_h'] / TWIP_PER_PT) / 72.0 * 25.4
    return max(band_mm(orientation), margins(orientation)['top'] / 72.0 * 25.4)


def section_config(orientation='portrait'):
    """Configuration de section à réutiliser pour régénérer un document Word.

    Retourne les valeurs twips d'origine (``<w:pgSz>``, ``<w:pgMar>``).
    """
    t = _twips(orientation)
    return {
        'page_width_twips': t['page_w'],
        'page_height_twips': t['page_h'],
        'orientation': orientation,
        'margin_top_twips': t['top'],
        'margin_right_twips': t['right'],
        'margin_bottom_twips': t['bottom'],
        'margin_left_twips': t['left'],
        'header_twips': t['header'],
        'footer_twips': t['footer'],
    }


def orientation_for(export_type, default='portrait'):
    """Orientation par défaut configurée pour un type d'export."""
    return EXPORT_ORIENTATIONS.get(export_type, default)


# ---------------------------------------------------------------------------
# 4. Tracé du fond de page
# ---------------------------------------------------------------------------
def draw_letterhead(canvas, orientation='portrait'):
    """Dessine l'image d'en-tête pleine page, derrière le texte (à appeler avant le contenu)."""
    path = image_path(orientation)
    if not os.path.isfile(path):
        return
    w, h = page_size(orientation)
    canvas.drawImage(
        ImageReader(path),
        0, 0, width=w, height=h,
        preserveAspectRatio=False, mask='auto',
    )


def letterhead_onpage(orientation='portrait'):
    """Callback onPage à passer à SimpleDocTemplate.build.

    Le fond est redessiné sur chaque page (y compris les pages issues d'un
    saut de page), ce qui garantit le bandeau et le pied sur toutes les pages.
    """
    def _draw(canvas, doc):
        draw_letterhead(canvas, orientation)
    return _draw


def fit_col_widths(widths, available):
    """Réduit proportionnellement les largeurs de colonnes si elles dépassent ``available``."""
    total = float(sum(widths))
    if total <= available or total == 0:
        return list(widths)
    factor = available / total
    return [w * factor for w in widths]
