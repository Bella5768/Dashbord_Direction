"""Génération de PDF pour les attestations de congé."""
import os
from datetime import datetime
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def generate_leave_approval_pdf(leave, output_path=None):
    """Génère un PDF d'attestation de congé approuvé.

    Args:
        leave: Instance de LeaveRequest
        output_path: Chemin du fichier de sortie (optionnel). Si None, retourne les bytes.

    Returns:
        Si output_path est fourni: chemin du fichier généré
        Sinon: bytes du PDF
    """
    from io import BytesIO

    # Utiliser BytesIO si pas de chemin de sortie
    if output_path is None:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=30)
    else:
        doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=30)

    styles = getSampleStyleSheet()
    story = []

    # Styles personnalisés
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=10,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.grey
    )

    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=10,
        spaceBefore=15,
        textColor=colors.darkblue
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=8
    )

    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.darkblue,
        fontName='Helvetica-Bold'
    )

    # En-tête CSIG
    story.append(Paragraph("CITÉ DES SCIENCES ET DE L'INNOVATION DE GUINÉE", title_style))
    story.append(Paragraph("CSIG - Centre de Suivi et d'Information de Gestion", subtitle_style))
    story.append(Paragraph("Direction Générale", subtitle_style))
    story.append(Spacer(1, 30))

    # Titre du document
    story.append(Paragraph("ATTESTATION DE CONGÉ", ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=20,
        spaceBefore=10,
        alignment=TA_CENTER,
        textColor=colors.darkgreen
    )))
    story.append(Spacer(1, 20))

    # Numéro de référence et date
    ref_num = f"CONG-{leave.id:06d}"
    story.append(Paragraph(f"<b>Référence :</b> {ref_num}", normal_style))
    story.append(Paragraph(f"<b>Date d'émission :</b> {datetime.now().strftime('%d/%m/%Y')}", normal_style))
    story.append(Spacer(1, 20))

    # Informations de l'employé
    story.append(Paragraph("INFORMATIONS DU DEMANDEUR", heading_style))
    
    employee_data = [
        [Paragraph("<b>Nom complet :</b>", label_style), Paragraph(leave.employee.name, normal_style)],
        [Paragraph("<b>Direction / Service :</b>", label_style), Paragraph(leave.direction.name if leave.direction else '-', normal_style)],
    ]
    
    employee_table = Table(employee_data, colWidths=[2.5*inch, 3.5*inch])
    employee_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(employee_table)
    story.append(Spacer(1, 15))

    # Détails du congé
    story.append(Paragraph("DÉTAILS DU CONGÉ", heading_style))
    
    type_label = leave.get_leave_type_display()
    period = f"Du {leave.start_date.strftime('%d/%m/%Y')} au {leave.end_date.strftime('%d/%m/%Y')}"
    duration = f"{leave.days_count} jour(s)"
    
    leave_data = [
        [Paragraph("<b>Type de congé :</b>", label_style), Paragraph(type_label, normal_style)],
        [Paragraph("<b>Période :</b>", label_style), Paragraph(period, normal_style)],
        [Paragraph("<b>Durée :</b>", label_style), Paragraph(duration, normal_style)],
        [Paragraph("<b>Motif :</b>", label_style), Paragraph(leave.reason, normal_style)],
    ]
    
    if leave.replacement:
        leave_data.append([Paragraph("<b>Suppléant :</b>", label_style), Paragraph(leave.replacement, normal_style)])
    
    leave_table = Table(leave_data, colWidths=[2.5*inch, 3.5*inch])
    leave_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(leave_table)
    story.append(Spacer(1, 20))

    # Validation
    story.append(Paragraph("CIRCUIT DE VALIDATION", heading_style))
    
    validation_data = [
        ["Étape", "Validateur", "Date", "Décision"],
    ]
    
    # Avis hiérarchique
    if leave.manager_user:
        manager_name = leave.manager_user.get_full_name() or leave.manager_user.username
        manager_date = leave.manager_decision_at.strftime('%d/%m/%Y %H:%M') if leave.manager_decision_at else '-'
        manager_decision = leave.get_manager_decision_display() if leave.manager_decision else '-'
        validation_data.append(["Avis hiérarchique", manager_name, manager_date, manager_decision])
    
    # Vérification RH
    if leave.hr_user:
        hr_name = leave.hr_user.get_full_name() or leave.hr_user.username
        hr_date = leave.hr_decision_at.strftime('%d/%m/%Y %H:%M') if leave.hr_decision_at else '-'
        hr_decision = leave.get_hr_decision_display() if leave.hr_decision else '-'
        validation_data.append(["Vérification RH", hr_name, hr_date, hr_decision])
    
    # Décision finale
    if leave.final_user:
        final_name = leave.final_user.get_full_name() or leave.final_user.username
        final_date = leave.final_decision_at.strftime('%d/%m/%Y %H:%M') if leave.final_decision_at else '-'
        final_decision = leave.get_final_decision_display() if leave.final_decision else '-'
        validation_data.append(["Décision finale", final_name, final_date, final_decision])
    
    validation_cell_style = ParagraphStyle('ValidationCell', parent=styles['Normal'], fontSize=8, leading=10)
    validation_header_style = ParagraphStyle('ValidationHeader', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.whitesmoke)
    
    formatted_validation_data = []
    for i, row in enumerate(validation_data):
        if i == 0:
            formatted_validation_data.append([
                Paragraph('<b>' + row[0] + '</b>', validation_header_style),
                Paragraph('<b>' + row[1] + '</b>', validation_header_style),
                Paragraph('<b>' + row[2] + '</b>', validation_header_style),
                Paragraph('<b>' + row[3] + '</b>', validation_header_style),
            ])
        else:
            formatted_validation_data.append([
                Paragraph(row[0], validation_cell_style),
                Paragraph(row[1], validation_cell_style),
                Paragraph(row[2], validation_cell_style),
                Paragraph(row[3], validation_cell_style),
            ])
    
    validation_table = Table(formatted_validation_data, colWidths=[2.0*inch, 2.0*inch, 1.5*inch, 1.5*inch], repeatRows=1)
    validation_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),
    ]))
    story.append(validation_table)
    story.append(Spacer(1, 30))

    # Statut final
    status_text = "APPROUVÉ" if leave.status == 'approuvee' else "REJETÉ"
    status_color = colors.darkgreen if leave.status == 'approuvee' else colors.red
    
    story.append(Paragraph(f"STATUT FINAL : {status_text}", ParagraphStyle(
        'Status',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=status_color,
        fontName='Helvetica-Bold'
    )))
    story.append(Spacer(1, 20))

    # Footer
    story.append(Paragraph("Ce document est généré automatiquement par le système CSIG.", subtitle_style))
    story.append(Paragraph("Pour toute question, veuillez contacter la Direction des Ressources Humaines.", subtitle_style))
    story.append(Spacer(1, 30))
    
    story.append(Paragraph("Cité des Sciences et de l'Innovation de Guinée", subtitle_style))
    story.append(Paragraph("© 2026 CSIG - Tous droits réservés", subtitle_style))

    # Génération du PDF
    doc.build(story)

    if output_path is None:
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
    else:
        return output_path
