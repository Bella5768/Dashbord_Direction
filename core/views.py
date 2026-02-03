from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime, timedelta
from django.db import models
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from .models import Direction, Project, Document, Partner, Event, Request, Employee, Budget, UserProfile, UserActivity, ProjectMember, Milestone, ProjectNeed, ProjectComment, ProjectDocument, ProjectFolder


def login_view(request):
    """Vue de connexion"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Bienvenue, {user.get_full_name() or user.username}!')
                next_url = request.GET.get('next', 'core:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Votre compte est désactivé.')
        else:
            messages.error(request, 'Identifiants incorrects.')
    
    return render(request, 'registration/login.html')


def logout_view(request):
    """Vue de déconnexion"""
    logout(request)
    messages.success(request, 'Vous avez été déconnecté avec succès.')
    return redirect('core:login')


def password_reset_info(request):
    """Page d'information pour mot de passe oublié"""
    return render(request, 'registration/password_reset.html')


@login_required
def dashboard(request):
    """Vue principale du tableau de bord"""
    today = timezone.now().date()
    
    # KPIs
    total_projects = Project.objects.count()
    projects_in_progress = Project.objects.filter(status='en_cours').count()
    projects_completed = Project.objects.filter(status='termine').count()
    projects_planned = Project.objects.filter(status='planifie').count()
    
    # Budget
    total_budget = Budget.objects.aggregate(total=Sum('allocated'))['total'] or 0
    total_consumed = Budget.objects.aggregate(total=Sum('consumed'))['total'] or 0
    budget_percentage = round((float(total_consumed) / float(total_budget) * 100), 1) if total_budget > 0 else 0
    
    # Documents et demandes
    pending_documents = Document.objects.exclude(status='signe').count()
    pending_requests = Request.objects.filter(status='en_attente').count()
    
    # Partenaires
    active_partners = Partner.objects.filter(status='actif').count()
    
    # Projets en cours
    active_projects = Project.objects.filter(status='en_cours').select_related('direction')[:4]
    
    # Documents en attente
    pending_docs = Document.objects.exclude(status='signe').select_related('direction')[:4]
    
    # Demandes en attente
    pending_reqs = Request.objects.filter(status='en_attente').select_related('direction')[:4]
    
    # Événements à venir
    upcoming_events = Event.objects.filter(date__gte=today).prefetch_related('participants')[:4]
    
    # Données pour les graphiques
    directions = Direction.objects.all()
    budget_data = []
    for direction in directions:
        try:
            budget = direction.budget
            budget_data.append({
                'direction': direction.code,
                'allocated': float(budget.allocated) / 1000000,
                'consumed': float(budget.consumed) / 1000000,
            })
        except Budget.DoesNotExist:
            pass
    
    context = {
        'total_projects': total_projects,
        'projects_in_progress': projects_in_progress,
        'projects_completed': projects_completed,
        'projects_planned': projects_planned,
        'total_budget': total_budget,
        'total_consumed': total_consumed,
        'budget_percentage': budget_percentage,
        'pending_documents': pending_documents,
        'pending_requests': pending_requests,
        'active_partners': active_partners,
        'active_projects': active_projects,
        'pending_docs': pending_docs,
        'pending_reqs': pending_reqs,
        'upcoming_events': upcoming_events,
        'budget_data': budget_data,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def projects(request):
    """Vue de la liste des projets"""
    status_filter = request.GET.get('status', 'all')
    direction_filter = request.GET.get('direction', 'all')
    search = request.GET.get('search', '')
    
    projects_qs = Project.objects.select_related('direction').prefetch_related('milestones')
    
    # Permission filtering
    if request.user.profile.is_directeur_general() or request.user.is_staff:
        # DG et admin voient tous les projets
        pass
    elif request.user.profile.is_directeur():
        # Directeur ne voit que les projets de sa direction
        projects_qs = projects_qs.filter(direction=request.user.profile.direction)
    else:
        # Chef de projet et autres voient les projets où ils sont manager OU membres
        from django.db.models import Q
        
        # Récupérer le nom de l'utilisateur
        user_name = request.user.get_full_name() or request.user.username
        employee_id = getattr(request.user.profile, 'employee_id', None)
        user_direction = request.user.profile.direction
        
        # Projets où l'utilisateur est manager (champ texte) OU membre (table ProjectMember)
        member_q = (
            Q(members__employee_id=employee_id)
            if employee_id
            else Q(members__employee__name__iexact=user_name) | Q(members__employee__name__icontains=request.user.username)
        )
        
        # Ajouter les projets de sa direction où il est membre
        if user_direction:
            projects_qs = projects_qs.filter(
                Q(manager__icontains=user_name) | member_q | Q(direction=user_direction, members__employee_id=employee_id)
            ).distinct()
        else:
            projects_qs = projects_qs.filter(Q(manager__icontains=user_name) | member_q).distinct()
    
    if status_filter != 'all':
        projects_qs = projects_qs.filter(status=status_filter)
    if direction_filter != 'all':
        projects_qs = projects_qs.filter(direction__code=direction_filter)
    if search:
        projects_qs = projects_qs.filter(name__icontains=search)
    
    directions = Direction.objects.all()
    
    # Stats filtered by permissions
    if request.user.profile.is_directeur_general() or request.user.is_staff:
        # DG et admin voient tous les projets
        base_qs = Project.objects.all()
    elif request.user.profile.is_directeur():
        # Directeur ne voit que les projets de sa direction
        base_qs = Project.objects.filter(direction=request.user.profile.direction)
    else:
        # Chef de projet et autres voient les projets où ils sont manager OU membres
        from django.db.models import Q
        
        # Récupérer le nom de l'utilisateur
        user_name = request.user.get_full_name() or request.user.username
        employee_id = getattr(request.user.profile, 'employee_id', None)
        user_direction = request.user.profile.direction
        
        # Projets où l'utilisateur est manager (champ texte) OU membre (table ProjectMember)
        member_q = (
            Q(members__employee_id=employee_id)
            if employee_id
            else Q(members__employee__name__iexact=user_name) | Q(members__employee__name__icontains=request.user.username)
        )
        
        # Ajouter les projets de sa direction où il est membre
        if user_direction:
            base_qs = Project.objects.filter(
                Q(manager__icontains=user_name) | member_q | Q(direction=user_direction, members__employee_id=employee_id)
            ).distinct()
        else:
            base_qs = Project.objects.filter(Q(manager__icontains=user_name) | member_q).distinct()
    stats = {
        'total': base_qs.count(),
        'en_cours': base_qs.filter(status='en_cours').count(),
        'termine': base_qs.filter(status='termine').count(),
        'planifie': base_qs.filter(status='planifie').count(),
    }
    
    context = {
        'projects': projects_qs,
        'directions': directions,
        'stats': stats,
        'current_status': status_filter,
        'current_direction': direction_filter,
        'search': search,
    }
    return render(request, 'core/projects.html', context)


@login_required
def resources(request):
    """Vue des ressources (budget et RH)"""
    tab = request.GET.get('tab', 'budget')
    
    # Budget data
    can_view_budgets = request.user.profile.can_view_budgets()
    can_manage_budgets = request.user.profile.can_manage_budgets()
    can_view_all_budget_directions = request.user.profile.can_view_all_budget_directions()

    budgets = Budget.objects.select_related('direction')
    if not can_view_budgets:
        budgets = budgets.none()
    elif not can_view_all_budget_directions:
        budgets = budgets.filter(direction=request.user.profile.direction)

    budgets = budgets.all()
    total_allocated = budgets.aggregate(total=Sum('allocated'))['total'] or 0
    total_consumed = budgets.aggregate(total=Sum('consumed'))['total'] or 0
    
    # Employees data
    employees = Employee.objects.select_related('direction').all()
    avg_workload = employees.aggregate(avg=Avg('workload'))['avg'] or 0
    overloaded = employees.filter(workload__gte=85).count()
    
    directions = Direction.objects.all()
    
    context = {
        'tab': tab,
        'budgets': budgets,
        'total_allocated': total_allocated,
        'total_consumed': total_consumed,
        'total_available': total_allocated - total_consumed,
        'consumption_rate': round((float(total_consumed) / float(total_allocated) * 100), 1) if total_allocated > 0 else 0,
        'can_view_budgets': can_view_budgets,
        'can_manage_budgets': can_manage_budgets,
        'can_view_all_budget_directions': can_view_all_budget_directions,
        'employees': employees,
        'avg_workload': round(avg_workload),
        'overloaded': overloaded,
        'directions': directions,
    }
    return render(request, 'core/resources.html', context)


@login_required
def documents(request):
    """Vue des documents"""
    status_filter = request.GET.get('status', 'all')
    type_filter = request.GET.get('type', 'all')
    search = request.GET.get('search', '')
    
    docs_qs = Document.objects.select_related('direction')
    
    if status_filter != 'all':
        docs_qs = docs_qs.filter(status=status_filter)
    if type_filter != 'all':
        docs_qs = docs_qs.filter(doc_type=type_filter)
    if search:
        docs_qs = docs_qs.filter(title__icontains=search)
    
    stats = {
        'total': Document.objects.count(),
        'a_signer': Document.objects.filter(status='a_signer').count(),
        'a_valider': Document.objects.filter(status='a_valider').count(),
        'signe': Document.objects.filter(status='signe').count(),
    }
    
    context = {
        'documents': docs_qs,
        'stats': stats,
        'current_status': status_filter,
        'current_type': type_filter,
        'search': search,
    }
    return render(request, 'core/documents.html', context)


@login_required
def requests_view(request):
    """Vue des demandes"""
    status_filter = request.GET.get('status', 'all')
    direction_filter = request.GET.get('direction', 'all')
    search = request.GET.get('search', '')
    
    reqs_qs = Request.objects.select_related('direction')
    
    if status_filter != 'all':
        reqs_qs = reqs_qs.filter(status=status_filter)
    if direction_filter != 'all':
        reqs_qs = reqs_qs.filter(direction__code=direction_filter)
    if search:
        reqs_qs = reqs_qs.filter(title__icontains=search)
    
    directions = Direction.objects.all()
    
    stats = {
        'total': Request.objects.count(),
        'en_attente': Request.objects.filter(status='en_attente').count(),
        'approuve': Request.objects.filter(status='approuve').count(),
        'rejete': Request.objects.filter(status='rejete').count(),
    }
    
    context = {
        'requests': reqs_qs,
        'directions': directions,
        'stats': stats,
        'current_status': status_filter,
        'current_direction': direction_filter,
        'search': search,
    }
    return render(request, 'core/requests.html', context)


@login_required
def calendar(request):
    """Vue du calendrier"""
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    # Événements du mois
    events_qs = Event.objects.filter(
        date__year=year,
        date__month=month
    ).prefetch_related('participants')
    
    # Stats pour le mois
    stats = {
        'reunions': events_qs.filter(event_type='reunion').count(),
        'evenements': events_qs.filter(event_type='evenement').count(),
        'deadlines': events_qs.filter(event_type='deadline').count(),
        'total': events_qs.count(),
    }
    
    # Événements à venir
    upcoming = Event.objects.filter(date__gte=today).prefetch_related('participants')[:5]
    
    # Construire le calendrier
    import calendar as cal
    cal_obj = cal.Calendar(firstweekday=0)
    month_days = cal_obj.monthdayscalendar(year, month)
    
    # Associer les événements aux jours
    events_by_day = {}
    for event in events_qs:
        day = event.date.day
        if day not in events_by_day:
            events_by_day[day] = []
        events_by_day[day].append(event)
    
    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    context = {
        'year': year,
        'month': month,
        'month_name': months[month - 1],
        'month_days': month_days,
        'events_by_day': events_by_day,
        'upcoming_events': upcoming,
        'today': today,
        'prev_month': month - 1 if month > 1 else 12,
        'prev_year': year if month > 1 else year - 1,
        'next_month': month + 1 if month < 12 else 1,
        'next_year': year if month < 12 else year + 1,
        'stats': stats,
    }
    return render(request, 'core/calendar.html', context)


@login_required
def event_create(request):
    """Créer un événement"""
    from .forms import EventForm
    
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Événement créé avec succès.")
            return redirect('core:calendar')
    else:
        # Pré-remplir la date si fournie dans l'URL
        initial = {}
        date_str = request.GET.get('date')
        if date_str:
            initial['date'] = date_str
        form = EventForm(initial=initial)
    
    return render(request, 'core/event_form.html', {'form': form, 'title': 'Nouvel événement'})


@login_required
def event_edit(request, event_id):
    """Modifier un événement"""
    from .forms import EventForm
    
    event = get_object_or_404(Event, pk=event_id)
    
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Événement modifié avec succès.")
            return redirect('core:calendar')
    else:
        form = EventForm(instance=event)
    
    return render(request, 'core/event_form.html', {'form': form, 'event': event, 'title': f'Modifier {event.title}'})


@login_required
def event_delete(request, event_id):
    """Supprimer un événement"""
    event = get_object_or_404(Event, pk=event_id)
    
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Événement supprimé avec succès.")
        return redirect('core:calendar')
    
    return render(request, 'core/event_confirm_delete.html', {'event': event})


@login_required
def reports(request):
    """Vue des rapports"""
    # Projets par direction
    directions = Direction.objects.all()
    projects_by_direction = []
    for direction in directions:
        projects_by_direction.append({
            'direction': direction.code,
            'en_cours': Project.objects.filter(direction=direction, status='en_cours').count(),
            'termine': Project.objects.filter(direction=direction, status='termine').count(),
        })
    
    # Projets par statut
    projects_by_status = [
        {'name': 'En cours', 'value': Project.objects.filter(status='en_cours').count()},
        {'name': 'Terminés', 'value': Project.objects.filter(status='termine').count()},
        {'name': 'Planifiés', 'value': Project.objects.filter(status='planifie').count()},
    ]
    
    # KPIs
    total_projects = Project.objects.count()
    projects_completed = Project.objects.filter(status='termine').count()
    total_budget = Budget.objects.aggregate(total=Sum('allocated'))['total'] or 0
    total_consumed = Budget.objects.aggregate(total=Sum('consumed'))['total'] or 0
    budget_rate = round((float(total_consumed) / float(total_budget) * 100)) if total_budget > 0 else 0
    active_partners = Partner.objects.filter(status='actif').count()
    pending_docs = Document.objects.exclude(status='signe').count()
    
    # Tous les projets pour le tableau
    all_projects = Project.objects.select_related('direction').all()
    
    context = {
        'projects_by_direction': projects_by_direction,
        'projects_by_status': projects_by_status,
        'total_projects': total_projects,
        'projects_completed': projects_completed,
        'budget_rate': budget_rate,
        'active_partners': active_partners,
        'pending_docs': pending_docs,
        'all_projects': all_projects,
    }
    return render(request, 'core/reports.html', context)


@login_required
def export_reports_pdf(request):
    """Exporter les rapports en PDF"""
    # Récupérer les mêmes données que la vue reports
    directions = Direction.objects.all()
    projects_by_direction = []
    for direction in directions:
        projects_by_direction.append({
            'direction': direction.code,
            'en_cours': Project.objects.filter(direction=direction, status='en_cours').count(),
            'termine': Project.objects.filter(direction=direction, status='termine').count(),
        })
    
    projects_by_status = [
        {'name': 'En cours', 'value': Project.objects.filter(status='en_cours').count()},
        {'name': 'Terminés', 'value': Project.objects.filter(status='termine').count()},
        {'name': 'Planifiés', 'value': Project.objects.filter(status='planifie').count()},
    ]
    
    total_projects = Project.objects.count()
    projects_completed = Project.objects.filter(status='termine').count()
    total_budget = Budget.objects.aggregate(total=Sum('allocated'))['total'] or 0
    total_consumed = Budget.objects.aggregate(total=Sum('consumed'))['total'] or 0
    budget_rate = round((float(total_consumed) / float(total_budget) * 100)) if total_budget > 0 else 0
    active_partners = Partner.objects.filter(status='actif').count()
    pending_docs = Document.objects.exclude(status='signe').count()
    all_projects = Project.objects.select_related('direction').all()
    
    # Créer le PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapports_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    story = []
    
    # Style personnalisé pour le titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    # Style pour les sous-titres
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.darkblue
    )
    
    # En-tête
    story.append(Paragraph("RAPPORT D'ACTIVITÉS", title_style))
    story.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Section KPIs
    story.append(Paragraph("INDICATEURS CLÉS", heading_style))
    
    kpi_data = [
        ['Indicateur', 'Valeur'],
        ['Projets totaux', str(total_projects)],
        ['Projets terminés', str(projects_completed)],
        ['Budget consommé', f'{budget_rate}%'],
        ['Partenaires actifs', str(active_partners)],
        ['Documents en attente', str(pending_docs)],
    ]
    
    kpi_table = Table(kpi_data, colWidths=[3*inch, 1.5*inch])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 20))
    
    # Section Projets par direction
    story.append(Paragraph("PROJETS PAR DIRECTION", heading_style))
    
    direction_data = [['Direction', 'En cours', 'Terminés']]
    for item in projects_by_direction:
        direction_data.append([item['direction'], str(item['en_cours']), str(item['termine'])])
    
    direction_table = Table(direction_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
    direction_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(direction_table)
    story.append(Spacer(1, 20))
    
    # Section Projets par statut
    story.append(Paragraph("RÉPARTITION DES PROJETS PAR STATUT", heading_style))
    
    status_data = [['Statut', 'Nombre']]
    for item in projects_by_status:
        status_data.append([item['name'], str(item['value'])])
    
    status_table = Table(status_data, colWidths=[2.5*inch, 1.5*inch])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(status_table)
    story.append(Spacer(1, 20))
    
    # Section détaillée des projets
    story.append(PageBreak())
    story.append(Paragraph("DÉTAIL DES PROJETS", heading_style))
    
    projects_data = [['Projet', 'Direction', 'Statut', 'Progression', 'Budget', 'Consommé', 'Taux']]
    for project in all_projects:
        projects_data.append([
            project.name,
            project.direction.code,
            project.get_status_display(),
            f"{project.progress}%",
            f"{project.budget:,.0f} GNF",
            f"{project.budget_consumed:,.0f} GNF",
            f"{project.budget_percentage}%"
        ])
    
    projects_table = Table(projects_data, colWidths=[2*inch, 1*inch, 1*inch, 0.8*inch, 1*inch, 1*inch, 0.8*inch])
    projects_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Aligner les noms de projets à gauche
    ]))
    story.append(projects_table)
    
    # Construire le PDF
    doc.build(story)
    
    return response


@login_required
def partners(request):
    """Vue des partenaires"""
    type_filter = request.GET.get('type', 'all')
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    
    partners_qs = Partner.objects.all()
    
    if type_filter != 'all':
        partners_qs = partners_qs.filter(partner_type=type_filter)
    if status_filter != 'all':
        partners_qs = partners_qs.filter(status=status_filter)
    if search:
        partners_qs = partners_qs.filter(name__icontains=search)
    
    today = timezone.now().date()
    upcoming_events = Event.objects.filter(
        event_type='evenement',
        date__gte=today
    ).prefetch_related('participants')[:3]
    
    stats = {
        'total': Partner.objects.count(),
        'actif': Partner.objects.filter(status='actif').count(),
        'en_discussion': Partner.objects.filter(status='en_discussion').count(),
    }
    
    type_counts = {
        'entreprise': Partner.objects.filter(partner_type='entreprise').count(),
        'universite': Partner.objects.filter(partner_type='universite').count(),
        'institution': Partner.objects.filter(partner_type='institution').count(),
        'ong': Partner.objects.filter(partner_type='ong').count(),
    }
    
    context = {
        'partners': partners_qs,
        'stats': stats,
        'type_counts': type_counts,
        'upcoming_events': upcoming_events,
        'current_type': type_filter,
        'current_status': status_filter,
        'search': search,
    }
    return render(request, 'core/partners.html', context)


# ==================== USER MANAGEMENT ====================

@login_required
def users_list(request):
    """Liste des utilisateurs"""
    from django.contrib.auth.models import User
    from .models import UserActivity
    
    # Check permission
    if not request.user.profile.can_manage_users():
        messages.error(request, "Vous n'avez pas les permissions pour gérer les utilisateurs.")
        return redirect('core:dashboard')
    
    search = request.GET.get('search', '')
    role_filter = request.GET.get('role', 'all')
    status_filter = request.GET.get('status', 'all')
    
    users = User.objects.select_related('profile').all()
    
    if search:
        users = users.filter(
            models.Q(username__icontains=search) |
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(email__icontains=search)
        )
    
    if role_filter != 'all':
        users = users.filter(profile__role=role_filter)
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Stats
    stats = {
        'total': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'inactive': User.objects.filter(is_active=False).count(),
    }
    
    # Recent activities
    recent_activities = UserActivity.objects.select_related('user').all()[:10]
    
    context = {
        'users': users,
        'stats': stats,
        'recent_activities': recent_activities,
        'search': search,
        'current_role': role_filter,
        'current_status': status_filter,
        'role_choices': UserProfile.ROLE_CHOICES,
    }
    return render(request, 'core/users/list.html', context)


@login_required
def user_create(request):
    """Créer un nouvel utilisateur"""
    from .forms import UserCreateForm
    
    if not request.user.profile.can_manage_users():
        messages.error(request, "Vous n'avez pas les permissions pour créer des utilisateurs.")
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                action='create',
                description=f"Création de l'utilisateur {user.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            messages.success(request, f"L'utilisateur {user.username} a été créé avec succès.")
            return redirect('core:users_list')
    else:
        form = UserCreateForm()
    
    context = {
        'form': form,
        'title': 'Nouvel utilisateur',
    }
    return render(request, 'core/users/form.html', context)


@login_required
def user_edit(request, user_id):
    """Modifier un utilisateur"""
    from django.contrib.auth.models import User
    from .forms import UserUpdateForm
    
    if not request.user.profile.can_manage_users():
        messages.error(request, "Vous n'avez pas les permissions pour modifier des utilisateurs.")
        return redirect('core:dashboard')
    
    user_obj = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                action='update',
                description=f"Modification de l'utilisateur {user_obj.username}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            messages.success(request, f"L'utilisateur {user_obj.username} a été modifié avec succès.")
            return redirect('core:users_list')
    else:
        form = UserUpdateForm(instance=user_obj)
    
    context = {
        'form': form,
        'user_obj': user_obj,
        'title': f'Modifier {user_obj.username}',
    }
    return render(request, 'core/users/form.html', context)


@login_required
def user_delete(request, user_id):
    """Supprimer un utilisateur"""
    from django.contrib.auth.models import User
    
    if not request.user.profile.can_manage_users():
        messages.error(request, "Vous n'avez pas les permissions pour supprimer des utilisateurs.")
        return redirect('core:dashboard')
    
    user_obj = get_object_or_404(User, pk=user_id)
    
    if user_obj == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('core:users_list')
    
    if request.method == 'POST':
        username = user_obj.username
        user_obj.delete()
        
        # Log activity
        UserActivity.objects.create(
            user=request.user,
            action='delete',
            description=f"Suppression de l'utilisateur {username}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        messages.success(request, f"L'utilisateur {username} a été supprimé.")
        return redirect('core:users_list')
    
    context = {
        'user_obj': user_obj,
    }
    return render(request, 'core/users/delete.html', context)


@login_required
def user_toggle_status(request, user_id):
    """Activer/Désactiver un utilisateur"""
    from django.contrib.auth.models import User
    
    if not request.user.profile.can_manage_users():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:dashboard')
    
    user_obj = get_object_or_404(User, pk=user_id)
    
    if user_obj == request.user:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect('core:users_list')
    
    user_obj.is_active = not user_obj.is_active
    user_obj.save()
    
    status = "activé" if user_obj.is_active else "désactivé"
    messages.success(request, f"L'utilisateur {user_obj.username} a été {status}.")
    
    return redirect('core:users_list')


@login_required
def user_change_password(request, user_id):
    """Changer le mot de passe d'un utilisateur"""
    from django.contrib.auth.models import User
    from .forms import PasswordChangeForm
    
    if not request.user.profile.can_manage_users():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:dashboard')
    
    user_obj = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            user_obj.set_password(form.cleaned_data['new_password1'])
            user_obj.save()
            
            messages.success(request, f"Le mot de passe de {user_obj.username} a été modifié.")
            return redirect('core:users_list')
    else:
        form = PasswordChangeForm()
    
    context = {
        'form': form,
        'user_obj': user_obj,
    }
    return render(request, 'core/users/change_password.html', context)


@login_required
def user_activities(request):
    """Journal des activités"""
    from .models import UserActivity
    
    if not request.user.profile.can_manage_users():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:dashboard')
    
    activities = UserActivity.objects.select_related('user').all()[:100]
    
    context = {
        'activities': activities,
    }
    return render(request, 'core/users/activities.html', context)


def get_client_ip(request):
    """Récupérer l'adresse IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ==================== PROJECT CRUD ====================


@login_required
def project_detail(request, project_id):
    """Détail d'un projet"""
    project = get_object_or_404(
        Project.objects.select_related('direction').prefetch_related('milestones', 'needs', 'comments'),
        pk=project_id,
    )

    employee_id = getattr(request.user.profile, 'employee_id', None)
    is_lead = bool(employee_id and project.members.filter(employee_id=employee_id, role='manager').exists())
    can_manage_members = bool((request.user.profile.is_directeur_general() or request.user.is_staff) or is_lead)

    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut voir que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            from django.db.models import Q
            
            # Récupérer le nom de l'utilisateur
            user_name = request.user.get_full_name() or request.user.username
            employee_id = getattr(request.user.profile, 'employee_id', None)
            
            # Vérifier si l'utilisateur est manager OU membre du projet
            is_manager = project.manager and user_name in project.manager
            if employee_id:
                is_member = project.members.filter(employee_id=employee_id).exists()
            else:
                is_member = (
                    project.members.filter(employee__name__iexact=user_name).exists() or
                    project.members.filter(employee__name__icontains=request.user.username).exists()
                )
            
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')

    context = {
        'project': project,
        'milestones': project.milestones.all(),
        'needs': project.needs.all(),
        'comments': project.comments.all(),
        'can_manage_members': can_manage_members,
    }
    return render(request, 'core/project_detail.html', context)


@login_required
def project_need_create(request, project_id):
    """Créer un besoin sur un projet"""
    from .forms_project import ProjectNeedForm

    project = get_object_or_404(Project, pk=project_id)

    # Permission check (mêmes règles que jalons / dossiers)
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            user_name = request.user.get_full_name() or request.user.username
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')

    if request.method != 'POST':
        return redirect('core:project_detail', project_id=project.id)

    form = ProjectNeedForm(request.POST)
    if form.is_valid():
        need = form.save(commit=False)
        need.project = project
        need.created_by = request.user.get_full_name() or request.user.username
        need.save()
        messages.success(request, "Besoin ajouté avec succès.")
    else:
        messages.error(request, "Impossible d'ajouter le besoin. Vérifiez le formulaire.")

    return redirect('core:project_detail', project_id=project.id)


@login_required
def project_comment_create(request, project_id):
    """Créer un commentaire sur un projet"""
    from .forms_project import ProjectCommentForm

    project = get_object_or_404(Project, pk=project_id)

    # Permission check (mêmes règles que jalons / besoins)
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            user_name = request.user.get_full_name() or request.user.username
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')

    if request.method != 'POST':
        return redirect('core:project_detail', project_id=project.id)

    form = ProjectCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.project = project
        comment.created_by = request.user.get_full_name() or request.user.username
        comment.save()
        messages.success(request, "Commentaire ajouté.")
    else:
        messages.error(request, "Impossible d'ajouter le commentaire. Vérifiez le formulaire.")

    return redirect('core:project_detail', project_id=project.id)

@login_required
def project_create(request):
    """Créer un nouveau projet"""
    from .forms_project import ProjectForm
    
    if not request.user.profile.can_create_projects():
        messages.error(request, "Vous n'avez pas les permissions pour créer un projet.")
        return redirect('core:projects')
    
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            messages.success(request, "Projet créé avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = ProjectForm()
    
    return render(request, 'core/project_form.html', {'form': form, 'title': 'Nouveau projet'})


@login_required
def project_edit(request, project_id):
    """Modifier un projet"""
    from .forms_project import ProjectForm
    
    project = get_object_or_404(Project, pk=project_id)
    
    # Vérifier les permissions
    if not request.user.profile.can_edit_project(project):
        messages.error(request, "Vous n'avez pas les permissions pour modifier ce projet.")
        return redirect('core:projects')
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Projet modifié avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project)
    
    return render(request, 'core/project_form.html', {'form': form, 'project': project, 'title': f'Modifier {project.name}'})


@login_required
def project_delete(request, project_id):
    """Supprimer un projet"""
    # Seul le Directeur Général peut supprimer un projet
    if not request.user.profile.is_directeur_general():
        messages.error(request, "Seul le Directeur Général peut supprimer un projet.")
        return redirect('core:projects')
    
    project = get_object_or_404(Project, pk=project_id)
    
    if request.method == 'POST':
        project.delete()
        messages.success(request, "Projet supprimé.")
        return redirect('core:projects')
    
    return render(request, 'core/confirm_delete.html', {'object': project, 'type': 'projet', 'back_url': 'core:projects'})


# ==================== MILESTONE CRUD ====================

@login_required
def milestone_create(request, project_id):
    """Créer un jalon pour un projet"""
    from .forms_project import MilestoneForm
    
    project = get_object_or_404(Project, pk=project_id)
    
    # Permission check - utiliser la nouvelle méthode
    if not request.user.profile.can_add_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour ajouter des jalons à ce projet.")
        return redirect('core:projects')
    
    if request.method == 'POST':
        form = MilestoneForm(project=project, data=request.POST)
        if form.is_valid():
            milestone = form.save(commit=False)
            milestone.project = project
            milestone.save()
            messages.success(request, "Jalon créé avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = MilestoneForm(project=project)
    
    return render(request, 'core/milestone_form.html', {'form': form, 'project': project, 'title': 'Nouveau jalon'})


@login_required
def milestone_edit(request, milestone_id):
    """Modifier un jalon"""
    from .forms_project import MilestoneForm
    
    milestone = get_object_or_404(Milestone.objects.select_related('project'), pk=milestone_id)
    project = milestone.project
    
    # Permission check
    if not request.user.profile.can_add_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour modifier ce jalon.")
        return redirect('core:projects')
    
    if request.method == 'POST':
        form = MilestoneForm(project=project, data=request.POST, instance=milestone)
        if form.is_valid():
            form.save()
            messages.success(request, "Jalon modifié avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = MilestoneForm(project=project, instance=milestone)
    
    return render(request, 'core/milestone_form.html', {'form': form, 'project': project, 'milestone': milestone, 'title': f'Modifier {milestone.name}'})


@login_required
def milestone_delete(request, milestone_id):
    """Supprimer un jalon"""
    milestone = get_object_or_404(Milestone.objects.select_related('project'), pk=milestone_id)
    project = milestone.project
    
    # Permission check
    if not request.user.profile.can_add_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour supprimer ce jalon.")
        return redirect('core:projects')
    
    if request.method == 'POST':
        milestone.delete()
        messages.success(request, "Jalon supprimé.")
        return redirect('core:project_detail', project_id=project.id)
    
    return render(request, 'core/confirm_delete.html', {'object': milestone, 'type': 'jalon', 'back_url': 'core:project_detail', 'back_args': {'project_id': project.id}})


# ==================== PROJECT FOLDER & DOCUMENT CRUD ====================

@login_required
def project_folder_create(request, project_id):
    """Créer un dossier pour un projet"""
    from .forms_project import ProjectFolderForm
    
    project = get_object_or_404(Project, pk=project_id)
    parent_id = request.GET.get('parent')
    parent_folder = None
    if parent_id:
        parent_folder = get_object_or_404(ProjectFolder, pk=parent_id, project=project)
    
    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut gérer que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            from django.db.models import Q
            
            # Récupérer le nom de l'utilisateur
            user_name = request.user.get_full_name() or request.user.username
            
            # Vérifier si l'utilisateur est manager OU membre du projet
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
    
    if request.method == 'POST':
        form = ProjectFolderForm(project, request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.project = project
            folder.save()
            messages.success(request, "Dossier créé avec succès.")
            if folder.parent_id:
                return redirect('core:project_folder_detail', folder_id=folder.id)
            return redirect('core:project_detail', project_id=project.id)
    else:
        if parent_folder:
            form = ProjectFolderForm(project, initial={'parent': parent_folder})
        else:
            form = ProjectFolderForm(project)
    
    return render(request, 'core/project_folder_form.html', {'form': form, 'project': project, 'title': 'Nouveau dossier'})


@login_required
def project_folder_detail(request, folder_id):
    """Détail d'un dossier de projet (sous-dossiers + documents)"""
    folder = get_object_or_404(ProjectFolder.objects.select_related('project', 'parent'), pk=folder_id)
    project = folder.project

    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut voir que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            user_name = request.user.get_full_name() or request.user.username
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')

    subfolders = folder.subfolders.all().order_by('name')
    documents = folder.documents.all().order_by('-uploaded_at')

    context = {
        'project': project,
        'folder': folder,
        'subfolders': subfolders,
        'documents': documents,
    }
    return render(request, 'core/project_folder_detail.html', context)


@login_required
def project_folder_edit(request, folder_id):
    """Modifier un dossier de projet"""
    from .forms_project import ProjectFolderForm
    
    folder = get_object_or_404(ProjectFolder.objects.select_related('project'), pk=folder_id)
    project = folder.project
    
    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut gérer que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            from django.db.models import Q
            
            # Récupérer le nom de l'utilisateur
            user_name = request.user.get_full_name() or request.user.username
            
            # Vérifier si l'utilisateur est manager OU membre du projet
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
    
    if request.method == 'POST':
        form = ProjectFolderForm(project, request.POST, instance=folder)
        if form.is_valid():
            form.save()
            messages.success(request, "Dossier modifié avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = ProjectFolderForm(project, instance=folder)
    
    return render(request, 'core/project_folder_form.html', {'form': form, 'project': project, 'folder': folder, 'title': f'Modifier {folder.name}'})


@login_required
def project_folder_delete(request, folder_id):
    """Supprimer un dossier de projet"""
    folder = get_object_or_404(ProjectFolder.objects.select_related('project'), pk=folder_id)
    project = folder.project
    
    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut gérer que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            from django.db.models import Q
            
            # Récupérer le nom de l'utilisateur
            user_name = request.user.get_full_name() or request.user.username
            
            # Vérifier si l'utilisateur est manager OU membre du projet
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
    
    if request.method == 'POST':
        folder.delete()
        messages.success(request, "Dossier supprimé.")
        return redirect('core:project_detail', project_id=project.id)
    
    return render(request, 'core/confirm_delete.html', {'object': folder, 'type': 'dossier', 'back_url': 'core:project_detail', 'back_args': {'project_id': project.id}})


@login_required
def project_document_create(request, project_id):
    """Créer un document pour un projet"""
    from .forms_project import ProjectDocumentForm
    
    project = get_object_or_404(Project, pk=project_id)
    folder_id = request.GET.get('folder')
    initial_folder = None
    if folder_id:
        initial_folder = get_object_or_404(ProjectFolder, pk=folder_id, project=project)
    
    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut gérer que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            from django.db.models import Q
            
            # Récupérer le nom de l'utilisateur
            user_name = request.user.get_full_name() or request.user.username
            
            # Vérifier si l'utilisateur est manager OU membre du projet
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
    
    if request.method == 'POST':
        form = ProjectDocumentForm(project, request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.project = project
            doc.uploaded_by = request.user.get_full_name() or request.user.username
            doc.save()
            messages.success(request, "Document ajouté avec succès.")
            if doc.folder_id:
                return redirect('core:project_folder_detail', folder_id=doc.folder_id)
            return redirect('core:project_detail', project_id=project.id)
    else:
        if initial_folder:
            form = ProjectDocumentForm(project, initial={'folder': initial_folder})
        else:
            form = ProjectDocumentForm(project)
    
    return render(request, 'core/project_document_form.html', {'form': form, 'project': project, 'title': 'Nouveau document'})


@login_required
def project_document_edit(request, doc_id):
    """Modifier un document de projet"""
    from .forms_project import ProjectDocumentForm
    
    doc = get_object_or_404(ProjectDocument.objects.select_related('project'), pk=doc_id)
    project = doc.project
    
    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut gérer que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            from django.db.models import Q
            
            # Récupérer le nom de l'utilisateur
            user_name = request.user.get_full_name() or request.user.username
            
            # Vérifier si l'utilisateur est manager OU membre du projet
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
    
    if request.method == 'POST':
        form = ProjectDocumentForm(project, request.POST, request.FILES, instance=doc)
        if form.is_valid():
            form.save()
            messages.success(request, "Document modifié avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = ProjectDocumentForm(project, instance=doc)
    
    return render(request, 'core/project_document_form.html', {'form': form, 'project': project, 'doc': doc, 'title': f'Modifier {doc.title}'})


@login_required
def project_document_delete(request, doc_id):
    """Supprimer un document de projet"""
    doc = get_object_or_404(ProjectDocument.objects.select_related('project'), pk=doc_id)
    project = doc.project
    
    # Permission check
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        if request.user.profile.is_directeur():
            # Directeur ne peut gérer que les projets de sa direction
            if project.direction != request.user.profile.direction:
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
        else:
            # Chef de projet et autres voient les projets où ils sont manager OU membres
            from django.db.models import Q
            
            # Récupérer le nom de l'utilisateur
            user_name = request.user.get_full_name() or request.user.username
            
            # Vérifier si l'utilisateur est manager OU membre du projet
            is_manager = project.manager and user_name in project.manager
            is_member = project.members.filter(employee__name=user_name).exists()
            
            if not (is_manager or is_member):
                messages.error(request, "Vous n'avez pas accès à ce projet.")
                return redirect('core:projects')
    
    if request.method == 'POST':
        doc.delete()
        messages.success(request, "Document supprimé.")
        return redirect('core:project_detail', project_id=project.id)
    
    return render(request, 'core/confirm_delete.html', {'object': doc, 'type': 'document', 'back_url': 'core:project_detail', 'back_args': {'project_id': project.id}})


# ==================== PROJECT MEMBER CRUD ====================

@login_required
def project_member_add(request, project_id):
    """Ajouter un membre à un projet"""
    from .forms_project import ProjectMemberForm
    
    project = get_object_or_404(Project, pk=project_id)

    # Permission check - utiliser la nouvelle méthode
    if not request.user.profile.can_add_project_members(project):
        messages.error(request, "Vous n'avez pas les permissions pour ajouter des membres à ce projet.")
        return redirect('core:project_detail', project_id=project.id)
    
    directions = Direction.objects.all()
    context = {
        'project': project,
        'title': 'Ajouter un membre',
        'directions': directions,
    }
    
    if request.method == 'POST':
        create_new_employee = request.POST.get('create_new_employee') == 'on'
        
        if create_new_employee:
            # Créer un nouvel employé
            new_name = request.POST.get('new_employee_name', '').strip()
            new_direction_id = request.POST.get('new_employee_direction', '')
            new_role_employee = request.POST.get('new_employee_role', '').strip()
            new_phone = request.POST.get('new_employee_phone', '').strip()
            new_email = request.POST.get('new_employee_email', '').strip()
            project_role = request.POST.get('role', 'membre')
            
            # Validation
            errors = []
            if not new_name:
                errors.append("Le nom de l'employé est requis.")
            if not new_direction_id:
                errors.append("La direction est requise.")
            if not new_role_employee:
                errors.append("Le poste/fonction est requis.")
            
            if errors:
                for error in errors:
                    messages.error(request, error)
                context['create_new_employee'] = True
                context['new_employee_name'] = new_name
                context['new_employee_direction'] = new_direction_id
                context['new_employee_role'] = new_role_employee
                context['new_employee_phone'] = new_phone
                context['new_employee_email'] = new_email
                form = ProjectMemberForm(project)
                context['form'] = form
                return render(request, 'core/project_member_form.html', context)
            
            # Créer l'employé
            direction = get_object_or_404(Direction, pk=new_direction_id)
            new_employee = Employee.objects.create(
                name=new_name,
                direction=direction,
                role=new_role_employee,
                phone=new_phone,
                email=new_email
            )
            
            # Créer le membre de projet
            ProjectMember.objects.create(
                project=project,
                employee=new_employee,
                role=project_role
            )
            
            messages.success(request, f"Employé '{new_name}' créé et ajouté au projet avec succès.")
            return redirect('core:project_detail', project_id=project.id)
        else:
            # Employé existant
            form = ProjectMemberForm(project, request.POST)
            if form.is_valid():
                member = form.save(commit=False)
                member.project = project
                member.save()
                messages.success(request, "Membre ajouté avec succès.")
                return redirect('core:project_detail', project_id=project.id)
            context['form'] = form
            return render(request, 'core/project_member_form.html', context)
    else:
        form = ProjectMemberForm(project)
    
    context['form'] = form
    return render(request, 'core/project_member_form.html', context)


@login_required
def project_member_edit(request, member_id):
    """Modifier le rôle d'un membre de projet"""
    from .forms_project import ProjectMemberForm
    
    member = get_object_or_404(ProjectMember.objects.select_related('project', 'employee'), pk=member_id)
    project = member.project

    # Permission check - utiliser la nouvelle méthode
    if not request.user.profile.can_add_project_members(project):
        messages.error(request, "Vous n'avez pas les permissions pour modifier les membres de ce projet.")
        return redirect('core:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        form = ProjectMemberForm(project, request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, "Rôle du membre modifié avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = ProjectMemberForm(project, instance=member)
    
    return render(request, 'core/project_member_form.html', {'form': form, 'project': project, 'member': member, 'title': f'Modifier {member.employee.name}'})


@login_required
def project_member_delete(request, member_id):
    """Supprimer un membre d'un projet"""
    member = get_object_or_404(ProjectMember.objects.select_related('project', 'employee'), pk=member_id)
    project = member.project

    # Permission check - utiliser la nouvelle méthode
    if not request.user.profile.can_add_project_members(project):
        messages.error(request, "Vous n'avez pas les permissions pour supprimer des membres de ce projet.")
        return redirect('core:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        member.delete()
        messages.success(request, "Membre supprimé du projet.")
        return redirect('core:project_detail', project_id=project.id)
    
    return render(request, 'core/confirm_delete.html', {'object': member, 'type': 'membre', 'back_url': 'core:project_detail', 'back_args': {'project_id': project.id}})


# ==================== DOCUMENT CRUD ====================

@login_required
def document_create(request):
    """Créer un nouveau document"""
    from .forms_project import DocumentForm
    
    if not request.user.profile.can_approve_documents():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:documents')
    
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Document créé avec succès.")
            return redirect('core:documents')
    else:
        form = DocumentForm()
    
    return render(request, 'core/document_form.html', {'form': form, 'title': 'Nouveau document'})


@login_required
def document_edit(request, doc_id):
    """Modifier un document"""
    from .forms_project import DocumentForm
    
    if not request.user.profile.can_approve_documents():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:documents')
    
    doc = get_object_or_404(Document, pk=doc_id)
    
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            form.save()
            messages.success(request, "Document modifié avec succès.")
            return redirect('core:documents')
    else:
        form = DocumentForm(instance=doc)
    
    return render(request, 'core/document_form.html', {'form': form, 'document': doc, 'title': f'Modifier {doc.title}'})


@login_required
def document_delete(request, doc_id):
    """Supprimer un document"""
    if not request.user.profile.can_approve_documents():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:documents')
    
    doc = get_object_or_404(Document, pk=doc_id)
    
    if request.method == 'POST':
        doc.delete()
        messages.success(request, "Document supprimé.")
        return redirect('core:documents')
    
    return render(request, 'core/confirm_delete.html', {'object': doc, 'type': 'document', 'back_url': 'core:documents'})


@login_required
def document_sign(request, doc_id):
    """Signer un document"""
    if not request.user.profile.can_approve_documents():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:documents')
    
    doc = get_object_or_404(Document, pk=doc_id)
    doc.status = 'signe'
    doc.signed_at = timezone.now().date()
    doc.save()
    messages.success(request, f"Document '{doc.title}' signé.")
    return redirect('core:documents')


@login_required
def document_validate(request, doc_id):
    """Valider un document"""
    if not request.user.profile.can_approve_documents():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:documents')
    
    doc = get_object_or_404(Document, pk=doc_id)
    doc.status = 'a_signer'
    doc.save()
    messages.success(request, f"Document '{doc.title}' validé, en attente de signature.")
    return redirect('core:documents')


# ==================== REQUEST CRUD ====================

@login_required
def request_create(request):
    """Créer une nouvelle demande"""
    from .forms_project import RequestForm
    
    if request.method == 'POST':
        form = RequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Demande créée avec succès.")
            return redirect('core:requests')
    else:
        form = RequestForm()
    
    return render(request, 'core/request_form.html', {'form': form, 'title': 'Nouvelle demande'})


@login_required
def request_approve(request, req_id):
    """Approuver une demande"""
    if not request.user.profile.can_approve_requests():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:requests')
    
    req = get_object_or_404(Request, pk=req_id)
    req.status = 'approuve'
    req.approved_at = timezone.now().date()
    req.save()
    messages.success(request, f"Demande '{req.title}' approuvée.")
    return redirect('core:requests')


@login_required
def request_reject(request, req_id):
    """Rejeter une demande"""
    if not request.user.profile.can_approve_requests():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:requests')
    
    req = get_object_or_404(Request, pk=req_id)
    req.status = 'rejete'
    req.save()
    messages.success(request, f"Demande '{req.title}' rejetée.")
    return redirect('core:requests')


# ==================== PARTNER CRUD ====================

@login_required
def partner_create(request):
    """Créer un nouveau partenaire"""
    from .forms_project import PartnerForm
    
    if not request.user.profile.can_manage_partners():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:partners')
    
    if request.method == 'POST':
        form = PartnerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Partenaire créé avec succès.")
            return redirect('core:partners')
    else:
        form = PartnerForm()
    
    return render(request, 'core/partner_form.html', {'form': form, 'title': 'Nouveau partenaire'})


@login_required
def partner_edit(request, partner_id):
    """Modifier un partenaire"""
    from .forms_project import PartnerForm
    
    if not request.user.profile.can_manage_partners():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:partners')
    
    partner = get_object_or_404(Partner, pk=partner_id)
    
    if request.method == 'POST':
        form = PartnerForm(request.POST, request.FILES, instance=partner)
        if form.is_valid():
            form.save()
            messages.success(request, "Partenaire modifié avec succès.")
            return redirect('core:partners')
    else:
        form = PartnerForm(instance=partner)
    
    return render(request, 'core/partner_form.html', {'form': form, 'partner': partner, 'title': f'Modifier {partner.name}'})


@login_required
def partner_delete(request, partner_id):
    """Supprimer un partenaire"""
    if not request.user.profile.can_manage_partners():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:partners')
    
    partner = get_object_or_404(Partner, pk=partner_id)
    
    if request.method == 'POST':
        partner.delete()
        messages.success(request, "Partenaire supprimé.")
        return redirect('core:partners')
    
    return render(request, 'core/confirm_delete.html', {'object': partner, 'type': 'partenaire', 'back_url': 'core:partners'})


# Employee management views
@login_required
def employee_create(request):
    """Créer un nouvel employé"""
    from .forms_project import EmployeeForm
    
    if not request.user.profile.can_manage_budgets():
        messages.error(request, "Vous n'avez pas les permissions pour gérer les employés.")
        return redirect('core:resources')
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé créé avec succès.")
            return redirect('core:resources')
    else:
        form = EmployeeForm()
    
    return render(request, 'core/employee_form.html', {'form': form, 'title': 'Nouvel employé'})


@login_required
def employee_edit(request, employee_id):
    """Modifier un employé existant"""
    from .forms_project import EmployeeForm
    
    if not request.user.profile.can_manage_budgets():
        messages.error(request, "Vous n'avez pas les permissions pour gérer les employés.")
        return redirect('core:resources')
    
    employee = get_object_or_404(Employee, pk=employee_id)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé modifié avec succès.")
            return redirect('core:resources')
    else:
        form = EmployeeForm(instance=employee)
    
    return render(request, 'core/employee_form.html', {'form': form, 'employee': employee, 'title': f'Modifier {employee.name}'})


@login_required
def employee_delete(request, employee_id):
    """Supprimer un employé"""
    if not request.user.profile.can_manage_budgets():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:resources')
    
    employee = get_object_or_404(Employee, pk=employee_id)
    
    if request.method == 'POST':
        employee.delete()
        messages.success(request, "Employé supprimé.")
        return redirect('core:resources')
    
    return render(request, 'core/confirm_delete.html', {'object': employee, 'type': 'employé', 'back_url': 'core:resources'})


# Budget management views
@login_required
def budget_create(request):
    """Créer un nouveau budget"""
    from .forms_project import BudgetForm
    
    if not request.user.profile.can_manage_budgets():
        messages.error(request, "Vous n'avez pas les permissions pour gérer les budgets.")
        return redirect('core:resources')
    
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Budget créé avec succès.")
            return redirect('core:resources')
    else:
        form = BudgetForm()
    
    return render(request, 'core/budget_form.html', {'form': form, 'title': 'Nouveau budget'})


@login_required
def budget_edit(request, budget_id):
    """Modifier un budget existant"""
    from .forms_project import BudgetForm
    
    if not request.user.profile.can_manage_budgets():
        messages.error(request, "Vous n'avez pas les permissions pour gérer les budgets.")
        return redirect('core:resources')
    
    budget = get_object_or_404(Budget, pk=budget_id)
    
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, "Budget modifié avec succès.")
            return redirect('core:resources')
    else:
        form = BudgetForm(instance=budget)
    
    return render(request, 'core/budget_form.html', {'form': form, 'budget': budget, 'title': f'Modifier budget {budget.direction.code}'})


@login_required
def budget_delete(request, budget_id):
    """Supprimer un budget"""
    if not request.user.profile.can_manage_budgets():
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:resources')
    
    budget = get_object_or_404(Budget, pk=budget_id)
    
    if request.method == 'POST':
        budget.delete()
        messages.success(request, "Budget supprimé.")
        return redirect('core:resources')
    
    return render(request, 'core/confirm_delete.html', {'object': budget, 'type': 'budget', 'back_url': 'core:resources'})


# API endpoints pour les graphiques
def api_budget_data(request):
    """API pour les données de budget"""
    can_view_budgets = request.user.profile.can_view_budgets()
    can_view_all_budget_directions = request.user.profile.can_view_all_budget_directions()

    budgets = Budget.objects.select_related('direction')
    if not can_view_budgets:
        budgets = budgets.none()
    elif not can_view_all_budget_directions:
        budgets = budgets.filter(direction=request.user.profile.direction)

    budgets = budgets.all()
    data = []
    for budget in budgets:
        data.append({
            'direction': budget.direction.code,
            'allocated': float(budget.allocated),
            'consumed': float(budget.consumed),
        })
    return JsonResponse(data, safe=False)


def api_projects_data(request):
    """API pour les données de projets"""
    directions = Direction.objects.all()
    data = []
    for direction in directions:
        data.append({
            'direction': direction.code,
            'en_cours': Project.objects.filter(direction=direction, status='en_cours').count(),
            'termine': Project.objects.filter(direction=direction, status='termine').count(),
        })
    return JsonResponse(data, safe=False)
