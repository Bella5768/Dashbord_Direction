from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Avg, Q
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
from .models import Direction, Project, Document, Partner, Event, Request, Employee, Budget, UserProfile, UserActivity, ProjectMember, Milestone, ProjectNeed, ProjectComment, ProjectDocument, ProjectFolder, ProjectActivity


def log_project_activity(project, action, description, user):
    """Enregistre une activité sur un projet"""
    username = user.get_full_name() or user.username if hasattr(user, 'get_full_name') else str(user)
    ProjectActivity.objects.create(
        project=project,
        action=action,
        description=description,
        user=username
    )


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
def global_search(request):
    """Recherche globale depuis la barre du header"""
    query = request.GET.get('q', '').strip()
    results = {
        'projects': [],
        'partners': [],
        'employees': [],
        'requests': [],
        'documents': [],
    }
    
    if query:
        from django.db.models import Q
        
        # Projets
        projects_qs = Project.objects.select_related('direction').filter(
            Q(name__icontains=query) | Q(manager__icontains=query) | Q(description__icontains=query)
        )
        # Filtrer par permissions
        if not (request.user.profile.is_directeur_general() or request.user.is_staff):
            user_name = request.user.get_full_name() or request.user.username
            employee_id = getattr(request.user.profile, 'employee_id', None)
            member_q = (
                Q(members__employee_id=employee_id)
                if employee_id
                else Q(members__employee__name__iexact=user_name) | Q(members__employee__name__icontains=request.user.username)
            )
            projects_qs = projects_qs.filter(Q(manager__icontains=user_name) | member_q).distinct()
        results['projects'] = projects_qs[:10]
        
        # Partenaires
        results['partners'] = Partner.objects.filter(
            Q(name__icontains=query) | Q(contact_person__icontains=query)
        )[:10]
        
        # Employés
        results['employees'] = Employee.objects.select_related('direction').filter(
            Q(name__icontains=query) | Q(role__icontains=query) | Q(email__icontains=query)
        )[:10]
        
        # Demandes
        results['requests'] = Request.objects.select_related('direction').filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )[:10]
        
        # Documents
        results['documents'] = Document.objects.select_related('direction').filter(
            Q(title__icontains=query)
        )[:10]
    
    total = sum(len(v) for v in results.values())
    
    context = {
        'query': query,
        'results': results,
        'total': total,
    }
    return render(request, 'core/global_search.html', context)


@login_required
def dashboard(request):
    """Vue principale du tableau de bord"""
    today = timezone.now().date()
    
    # KPIs
    total_projects = Project.objects.count()
    projects_in_progress = Project.objects.filter(status='en_cours').count()
    projects_completed = Project.objects.filter(status='termine').count()
    projects_planned = Project.objects.filter(status='planifie').count()
    
    # Budget : combiner table Budget (par direction ou projet) + Project.budget direct
    budget_table_allocated = Budget.objects.aggregate(total=Sum('allocated'))['total'] or 0
    budget_table_consumed = Budget.objects.aggregate(total=Sum('consumed'))['total'] or 0
    # Projects.budget direct, en excluant ceux deja couverts par une ligne Budget(project=...)
    project_ids_with_budget_row = set(
        Budget.objects.filter(project__isnull=False).values_list('project_id', flat=True)
    )
    project_direct = Project.objects.exclude(id__in=project_ids_with_budget_row).aggregate(
        total_allocated=Sum('budget'), total_consumed=Sum('budget_consumed'),
    )
    project_direct_allocated = project_direct['total_allocated'] or 0
    project_direct_consumed = project_direct['total_consumed'] or 0
    total_budget = float(budget_table_allocated) + float(project_direct_allocated)
    total_consumed = float(budget_table_consumed) + float(project_direct_consumed)
    budget_percentage = round((total_consumed / total_budget * 100), 1) if total_budget > 0 else 0
    
    # Documents et demandes
    pending_documents = Document.objects.exclude(status='signe').count()
    pending_requests = Request.objects.filter(status='en_attente').count()
    
    # Partenaires
    active_partners = Partner.objects.filter(status='actif').count()
    
    # Projets en cours (filtrés par permissions)
    if request.user.profile.is_directeur_general() or request.user.is_staff:
        active_projects = Project.objects.filter(status='en_cours').select_related('direction')[:4]
    else:
        user_name = request.user.get_full_name() or request.user.username
        employee_id = getattr(request.user.profile, 'employee_id', None)
        member_q = (
            Q(members__employee_id=employee_id)
            if employee_id
            else Q(members__employee__name__iexact=user_name) | Q(members__employee__name__icontains=request.user.username)
        )
        active_projects = Project.objects.filter(
            Q(manager__icontains=user_name) | member_q, status='en_cours'
        ).select_related('direction').distinct()[:4]
    
    # Documents en attente
    pending_docs = Document.objects.exclude(status='signe').select_related('direction')[:4]
    
    # Demandes en attente
    pending_reqs = Request.objects.filter(status='en_attente').select_related('direction')[:4]
    
    # Événements à venir
    upcoming_events = Event.objects.filter(date__gte=today).prefetch_related('participants')[:4]
    
    # Donnees pour le graphique Budget : budget PAR PROJET (independant de toute direction).
    # Deux sources combinees :
    #   1) Project.budget / Project.budget_consumed (saisis dans le formulaire projet)
    #   2) Budget(project=...) (lignes budgetaires creees via "Affecter un budget")
    budget_by_project = {}  # project_id -> {'name', 'allocated', 'consumed'}

    # Source 1 : champ budget directement sur le projet
    for p in Project.objects.filter(Q(budget__gt=0) | Q(budget_consumed__gt=0)):
        budget_by_project[p.id] = {
            'name': p.name,
            'allocated': float(p.budget or 0),
            'consumed': float(p.budget_consumed or 0),
        }

    # Source 2 : lignes budgetaires rattachees a un projet (somme)
    project_budget_rows = (
        Budget.objects
        .filter(project__isnull=False)
        .values('project_id', 'project__name')
        .annotate(total_allocated=Sum('allocated'), total_consumed=Sum('consumed'))
    )
    for row in project_budget_rows:
        pid = row['project_id']
        entry = budget_by_project.setdefault(pid, {
            'name': row['project__name'] or 'Projet sans nom',
            'allocated': 0.0,
            'consumed': 0.0,
        })
        entry['allocated'] += float(row['total_allocated'] or 0)
        entry['consumed'] += float(row['total_consumed'] or 0)

    # Tri par alloue desc, top 10, conversion en millions
    sorted_entries = sorted(budget_by_project.values(), key=lambda e: e['allocated'], reverse=True)[:10]
    budget_data = []
    for entry in sorted_entries:
        name = entry['name']
        budget_data.append({
            'direction': name[:30] + ('…' if len(name) > 30 else ''),
            'name': name,
            'color': '#3b82f6',
            'allocated': entry['allocated'] / 1000000,
            'consumed': entry['consumed'] / 1000000,
        })
    
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
    """Vue de la liste des projets avec restrictions par role."""
    status_filter = request.GET.get('status', 'all')
    direction_filter = request.GET.get('direction', 'all')
    search = request.GET.get('search', '')

    projects_qs = Project.objects.select_related('direction').prefetch_related('milestones')
    profile = request.user.profile

    # Permission filtering
    if profile.is_directeur_general() or request.user.is_staff:
        # DG et admin voient tous les projets
        pass
    elif profile.role == 'directeur':
        # Directeur : uniquement les projets de sa direction
        if profile.direction_id:
            projects_qs = projects_qs.filter(direction_id=profile.direction_id)
        else:
            projects_qs = projects_qs.none()
    else:
        # Chef de projet et autres : seulement les projets où ils sont manager OU membres
        from django.db.models import Q

        user_name = request.user.get_full_name() or request.user.username
        employee_id = getattr(profile, 'employee_id', None)

        member_q = (
            Q(members__employee_id=employee_id)
            if employee_id
            else Q(members__employee__name__iexact=user_name) | Q(members__employee__name__icontains=request.user.username)
        )

        projects_qs = projects_qs.filter(Q(manager__icontains=user_name) | member_q).distinct()

    if status_filter != 'all':
        projects_qs = projects_qs.filter(status=status_filter)
    if direction_filter != 'all':
        projects_qs = projects_qs.filter(direction__code=direction_filter)
    if search:
        projects_qs = projects_qs.filter(name__icontains=search)

    directions = Direction.objects.all()

    # Stats filtered by permissions (même logique que le filtrage principal)
    if profile.is_directeur_general() or request.user.is_staff:
        base_qs = Project.objects.all()
    elif profile.role == 'directeur':
        if profile.direction_id:
            base_qs = Project.objects.filter(direction_id=profile.direction_id)
        else:
            base_qs = Project.objects.none()
    else:
        from django.db.models import Q
        user_name = request.user.get_full_name() or request.user.username
        employee_id = getattr(profile, 'employee_id', None)
        member_q = (
            Q(members__employee_id=employee_id)
            if employee_id
            else Q(members__employee__name__iexact=user_name) | Q(members__employee__name__icontains=request.user.username)
        )
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

    budgets_qs = Budget.objects.select_related('direction', 'project')
    if not can_view_budgets:
        budgets_qs = budgets_qs.none()
    elif not can_view_all_budget_directions:
        budgets_qs = budgets_qs.filter(Q(project__isnull=False) | Q(direction=request.user.profile.direction))

    from .currencies import convert_currency, format_currency
    from types import SimpleNamespace

    # 1) Budgets reels (table Budget)
    budgets = list(budgets_qs.all())

    # Projects deja couverts par une ligne Budget(project=...)
    projects_with_budget_row = {b.project_id for b in budgets if b.project_id}

    # 2) Synthese : Project.budget saisi directement sur le projet (sans ligne Budget dediee)
    if can_view_budgets:
        for p in Project.objects.exclude(id__in=projects_with_budget_row).filter(Q(budget__gt=0) | Q(budget_consumed__gt=0)):
            budgets.append(SimpleNamespace(
                id=None,
                is_inline=True,  # source = Project.budget
                project=p,
                direction=p.direction,
                allocated=p.budget or 0,
                consumed=p.budget_consumed or 0,
                currency=p.currency or 'GNF',
                available=(p.budget or 0) - (p.budget_consumed or 0),
                consumption_rate=round((float(p.budget_consumed) / float(p.budget)) * 100, 1) if p.budget and p.budget > 0 else 0,
            ))

    # Conversion GNF + totaux
    total_allocated = 0
    total_consumed = 0
    for b in budgets:
        b.allocated_gnf = round(convert_currency(float(b.allocated), b.currency, 'GNF'))
        b.consumed_gnf = round(convert_currency(float(b.consumed), b.currency, 'GNF'))
        b.available_gnf = b.allocated_gnf - b.consumed_gnf
        total_allocated += b.allocated_gnf
        total_consumed += b.consumed_gnf
    total_allocated = round(total_allocated)
    total_consumed = round(total_consumed)
    
    # Employees data : un directeur ne voit que sa direction
    employees = Employee.objects.select_related('direction').all()
    profile = request.user.profile
    if profile.role == 'directeur' and profile.direction_id:
        employees = employees.filter(direction_id=profile.direction_id)
    elif profile.role not in ['admin', 'directeur_general'] and not profile.can_view_all_budget_directions():
        # Autres roles : limites a leur direction si definie
        if profile.direction_id:
            employees = employees.filter(direction_id=profile.direction_id)
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
    import json
    import calendar as cal

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
    cal_obj = cal.Calendar(firstweekday=0)
    month_days = cal_obj.monthdayscalendar(year, month)
    
    # Associer les événements aux jours
    events_by_day = {}
    for event in events_qs:
        day = event.date.day
        if day not in events_by_day:
            events_by_day[day] = []
        events_by_day[day].append(event)

    # Serialiser les events pour les vues Kanban et Gantt (JS)
    events_json = []
    edit_url_template = reverse('core:event_edit', args=[0]).replace('/0/', '/__ID__/')
    for ev in events_qs:
        events_json.append({
            'id': ev.id,
            'title': ev.title,
            'type': ev.event_type,
            'type_label': ev.get_event_type_display(),
            'description': ev.description or '',
            'date': ev.date.isoformat(),
            'day': ev.date.day,
            'time': ev.time.strftime('%H:%M'),
            'duration': ev.duration,
            'location': ev.location or '',
            'participants': [p.code for p in ev.participants.all()],
            'edit_url': edit_url_template.replace('__ID__', str(ev.id)),
        })

    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    # Nombre de jours dans le mois (pour Gantt)
    days_in_month = cal.monthrange(year, month)[1]
    
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
        'events_json': json.dumps(events_json),
        'days_in_month': days_in_month,
        'days_range': list(range(1, days_in_month + 1)),
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
    """Vue des rapports - Réservée au Directeur Général"""
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        messages.error(request, "Cette section est réservée au Directeur Général.")
        return redirect('core:dashboard')
    
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
    
    # Budget par direction
    budget_by_direction = []
    for direction in directions:
        budgets = direction.budgets.all()
        if budgets.exists():
            # Agréger tous les budgets de la direction
            total_allocated = sum(b.allocated for b in budgets)
            total_consumed = sum(b.consumed for b in budgets)
            budget_by_direction.append({
                'direction': direction.code,
                'name': direction.name,
                'allocated': float(total_allocated),
                'consumed': float(total_consumed),
                'rate': round((float(total_consumed) / float(total_allocated) * 100)) if total_allocated > 0 else 0,
            })
        else:
            budget_by_direction.append({
                'direction': direction.code,
                'name': direction.name,
                'allocated': 0,
                'consumed': 0,
                'rate': 0,
            })
    
    # Performance par projet
    projects_en_retard = Project.objects.filter(status='en_retard').count()
    projects_en_cours = Project.objects.filter(status='en_cours').count()
    avg_progress = all_projects.aggregate(avg=Avg('progress'))['avg'] or 0
    
    # Demandes en attente
    pending_requests = Request.objects.filter(status='en_attente').count()
    
    context = {
        'projects_by_direction': projects_by_direction,
        'projects_by_status': projects_by_status,
        'total_projects': total_projects,
        'projects_completed': projects_completed,
        'budget_rate': budget_rate,
        'active_partners': active_partners,
        'pending_docs': pending_docs,
        'pending_requests': pending_requests,
        'all_projects': all_projects,
        'total_budget': total_budget,
        'total_consumed': total_consumed,
        'budget_by_direction': budget_by_direction,
        'projects_en_retard': projects_en_retard,
        'projects_en_cours': projects_en_cours,
        'avg_progress': round(avg_progress),
    }
    return render(request, 'core/reports.html', context)


@login_required
def export_employees_pdf(request):
    """Exporter la liste des employés en PDF"""
    employees = Employee.objects.select_related('direction').all()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="employes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'EmpTitle',
        parent=styles['Heading1'],
        fontSize=22,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    subtitle_style = ParagraphStyle(
        'EmpSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    
    heading_style = ParagraphStyle(
        'EmpHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        spaceBefore=15,
        textColor=colors.darkblue
    )
    
    # En-tête
    story.append(Paragraph("LISTE DES EMPLOYÉS", title_style))
    story.append(Paragraph(f"Exporté le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", subtitle_style))
    story.append(Paragraph(f"Effectif total : {employees.count()} employés", subtitle_style))
    story.append(Spacer(1, 20))
    
    # Tableau des employés
    story.append(Paragraph("RÉPERTOIRE DU PERSONNEL", heading_style))
    
    table_data = [['Nom', 'Direction', 'Rôle', 'Téléphone', 'Email', 'Charge']]
    
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10)
    header_cell_style = ParagraphStyle('HeaderCell', parent=styles['Normal'], fontSize=9, leading=11, textColor=colors.whitesmoke)
    
    table_data = [[
        Paragraph('<b>Nom</b>', header_cell_style),
        Paragraph('<b>Direction</b>', header_cell_style),
        Paragraph('<b>Rôle</b>', header_cell_style),
        Paragraph('<b>Téléphone</b>', header_cell_style),
        Paragraph('<b>Email</b>', header_cell_style),
        Paragraph('<b>Charge</b>', header_cell_style),
    ]]
    
    for emp in employees:
        table_data.append([
            Paragraph(emp.name, cell_style),
            Paragraph(emp.direction.code if emp.direction else '-', cell_style),
            Paragraph(emp.role, cell_style),
            Paragraph(emp.phone or '-', cell_style),
            Paragraph(emp.email or '-', cell_style),
            Paragraph(f'{emp.workload}%', cell_style),
        ])
    
    col_widths = [1.4*inch, 0.8*inch, 1.3*inch, 1.0*inch, 1.6*inch, 0.6*inch]
    emp_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
    ]
    
    # Alterner les couleurs de fond
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.97)))
    
    emp_table.setStyle(TableStyle(table_style))
    story.append(emp_table)
    story.append(Spacer(1, 20))
    
    # Résumé par direction
    story.append(Paragraph("RÉPARTITION PAR DIRECTION", heading_style))
    
    dir_data = [[
        Paragraph('<b>Direction</b>', header_cell_style),
        Paragraph('<b>Effectif</b>', header_cell_style),
        Paragraph('<b>Charge moyenne</b>', header_cell_style),
    ]]
    
    directions = Direction.objects.all()
    for d in directions:
        dir_employees = employees.filter(direction=d)
        count = dir_employees.count()
        if count > 0:
            avg_wl = round(sum(e.workload for e in dir_employees) / count)
            dir_data.append([
                Paragraph(f'{d.code} - {d.name}', cell_style),
                Paragraph(str(count), cell_style),
                Paragraph(f'{avg_wl}%', cell_style),
            ])
    
    dir_table = Table(dir_data, colWidths=[3*inch, 1.2*inch, 1.5*inch], repeatRows=1)
    dir_table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for i in range(1, len(dir_data)):
        if i % 2 == 0:
            dir_table_style.append(('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.97)))
    
    dir_table.setStyle(TableStyle(dir_table_style))
    story.append(dir_table)
    
    doc.build(story)
    return response


@login_required
def export_reports_pdf(request):
    """Exporter les rapports en PDF - Réservé au DG"""
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        messages.error(request, "Cette section est réservée au Directeur Général.")
        return redirect('core:dashboard')
    
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
            project.direction.code if project.direction else '-',
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


# ==================== DIRECTIONS CRUD ====================

@login_required
def directions_list(request):
    """Liste des directions"""
    # Seuls admin et DG peuvent gérer les directions
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        messages.error(request, "Vous n'avez pas la permission de gérer les directions.")
        return redirect('core:dashboard')
    
    directions = Direction.objects.annotate(
        projects_count=Count('projects'),
        users_count=Count('users')
    ).order_by('name')
    
    context = {
        'directions': directions,
    }
    return render(request, 'core/directions_list.html', context)


@login_required
def direction_create(request):
    """Créer une nouvelle direction"""
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        messages.error(request, "Vous n'avez pas la permission de créer des directions.")
        return redirect('core:dashboard')
    
    from .forms import DirectionForm
    
    if request.method == 'POST':
        form = DirectionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Direction créée avec succès.")
            return redirect('core:directions_list')
    else:
        form = DirectionForm()
    
    context = {
        'form': form,
        'title': 'Nouvelle direction',
    }
    return render(request, 'core/direction_form.html', context)


@login_required
def direction_edit(request, direction_id):
    """Modifier une direction"""
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        messages.error(request, "Vous n'avez pas la permission de modifier les directions.")
        return redirect('core:dashboard')
    
    direction = get_object_or_404(Direction, pk=direction_id)
    from .forms import DirectionForm
    
    if request.method == 'POST':
        form = DirectionForm(request.POST, instance=direction)
        if form.is_valid():
            form.save()
            messages.success(request, "Direction modifiée avec succès.")
            return redirect('core:directions_list')
    else:
        form = DirectionForm(instance=direction)
    
    context = {
        'form': form,
        'direction': direction,
        'title': f'Modifier {direction.name}',
    }
    return render(request, 'core/direction_form.html', context)


@login_required
def direction_delete(request, direction_id):
    """Supprimer une direction"""
    if not (request.user.profile.is_directeur_general() or request.user.is_staff):
        messages.error(request, "Vous n'avez pas la permission de supprimer les directions.")
        return redirect('core:dashboard')
    
    direction = get_object_or_404(Direction, pk=direction_id)
    
    if request.method == 'POST':
        direction.delete()
        messages.success(request, "Direction supprimée.")
        return redirect('core:directions_list')
    
    return render(request, 'core/confirm_delete.html', {
        'object': direction,
        'type': 'direction',
        'back_url': 'core:directions_list'
    })


# ==================== USER MANAGEMENT ====================

@login_required
def users_list(request):
    """Liste des utilisateurs"""
    from django.contrib.auth.models import User
    from .models import UserActivity
    
    # Check permission
    if not request.user.profile.has_manage_users_permission():
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
    
    if not request.user.profile.has_manage_users_permission():
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
    
    if not request.user.profile.has_manage_users_permission():
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
    
    if not request.user.profile.has_manage_users_permission():
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
    
    if not request.user.profile.has_manage_users_permission():
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
    
    if not request.user.profile.has_manage_users_permission():
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
    
    if not request.user.profile.has_manage_users_permission():
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
        Project.objects.select_related('direction').prefetch_related('milestones', 'needs', 'comments', 'members', 'project_documents'),
        pk=project_id,
    )

    # Nouveau système de permissions basé sur les rôles des membres
    can_manage_members = request.user.profile.can_manage_project_members(project)
    can_perform_actions = request.user.profile.can_perform_actions_as_member(project)
    is_readonly = request.user.profile.is_project_readonly(project)
    can_edit_project = request.user.profile.can_edit_project(project)
    can_add_milestones = request.user.profile.can_add_project_milestones(project)
    can_add_documents = request.user.profile.can_add_project_documents(project)

    # Permission check
    if not request.user.profile.can_view_project(project):
        messages.error(request, "Vous n'avez pas accès à ce projet.")
        return redirect('core:projects')

    context = {
        'project': project,
        'milestones': project.milestones.all(),
        'needs': project.needs.all(),
        'comments': project.comments.all(),
        'activities': project.activities.all()[:20],
        'members': project.members.all(),
        'documents': project.project_documents.all(),
        'can_manage_members': can_manage_members,
        'can_perform_actions': can_perform_actions,
        'is_readonly': is_readonly,
        'can_edit_project': can_edit_project,
        'can_add_milestones': can_add_milestones,
        'can_add_documents': can_add_documents,
    }
    return render(request, 'core/project_detail.html', context)


@login_required
def export_project_activities(request, project_id):
    """Exporter le journal d'activité d'un projet en PDF"""
    project = get_object_or_404(Project, pk=project_id)
    activities = project.activities.all()
    
    # Créer le PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="journal_activite_{project.name.replace(" ", "_")}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    # Style personnalisé pour le titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey,
        spaceAfter=30
    )
    
    elements = []
    
    # Titre
    elements.append(Paragraph(f"Journal d'activité", title_style))
    elements.append(Paragraph(f"Projet : {project.name}", subtitle_style))
    elements.append(Paragraph(f"Exporté le {timezone.now().strftime('%d/%m/%Y à %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 20))
    
    if activities:
        # Tableau des activités
        data = [['Date', 'Utilisateur', 'Action', 'Description']]
        
        for activity in activities:
            data.append([
                activity.created_at.strftime('%d/%m/%Y %H:%M'),
                activity.user,
                activity.get_action_display(),
                activity.description[:50] + '...' if len(activity.description) > 50 else activity.description
            ])
        
        table = Table(data, colWidths=[80, 90, 100, 200])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("Aucune activité enregistrée pour ce projet.", styles['Normal']))
    
    doc.build(elements)
    return response


@login_required
def project_need_create(request, project_id):
    """Créer un besoin sur un projet"""
    from .forms_project import ProjectNeedForm

    project = get_object_or_404(Project, pk=project_id)

    # Permission check - utiliser le nouveau système basé sur les rôles
    if not request.user.profile.can_perform_actions_as_member(project):
        messages.error(request, "Vous n'avez pas les permissions pour ajouter des besoins à ce projet.")
        return redirect('core:project_detail', project_id=project.id)

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

    # Permission check - utiliser le nouveau système basé sur les rôles
    if not request.user.profile.can_perform_actions_as_member(project):
        messages.error(request, "Vous n'avez pas les permissions pour ajouter des commentaires à ce projet.")
        return redirect('core:project_detail', project_id=project.id)

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
            log_project_activity(project, 'creation', f"Création du projet '{project.name}'", request.user)
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
            log_project_activity(project, 'modification', f"Modification des informations du projet", request.user)
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
    if not request.user.profile.can_add_project_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour ajouter des jalons à ce projet.")
        return redirect('core:projects')
    
    if request.method == 'POST':
        form = MilestoneForm(project=project, data=request.POST)
        if form.is_valid():
            milestone = form.save(commit=False)
            milestone.project = project
            if milestone.assigned_to:
                milestone.assigned_by = request.user
            milestone.save()
            log_project_activity(project, 'ajout_jalon', f"Ajout du jalon '{milestone.name}'", request.user)
            # Notification email au responsable + chef de projet en CC
            if milestone.assigned_to:
                from .notifications import notify_assignment
                assigned_by = request.user.get_full_name() or request.user.username
                success, msg = notify_assignment(milestone.assigned_to, 'jalon', milestone.name, project.name, assigned_by, project=project, due_date=milestone.due_date)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Jalon créé mais notification email échouée : {msg}")
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
    if not request.user.profile.can_add_project_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour modifier ce jalon.")
        return redirect('core:projects')
    
    old_assigned = milestone.assigned_to_id
    was_completed = milestone.completed
    if request.method == 'POST':
        form = MilestoneForm(project=project, data=request.POST, instance=milestone)
        if form.is_valid():
            milestone = form.save(commit=False)
            if milestone.assigned_to and milestone.assigned_to_id != old_assigned:
                milestone.assigned_by = request.user
            milestone.save()
            log_project_activity(project, 'modif_jalon', f"Modification du jalon '{milestone.name}'", request.user)
            # Notification email si le responsable a changé (chef de projet en CC)
            if milestone.assigned_to and milestone.assigned_to_id != old_assigned:
                from .notifications import notify_assignment
                assigned_by = request.user.get_full_name() or request.user.username
                success, msg = notify_assignment(milestone.assigned_to, 'jalon', milestone.name, project.name, assigned_by, project=project, due_date=milestone.due_date)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Jalon modifié mais notification email échouée : {msg}")
            if milestone.completed and not was_completed:
                from .notifications import notify_task_completed
                success, msg = notify_task_completed('jalon', milestone.name, project, milestone.assigned_to, milestone.assigned_by, request.user)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Jalon terminé mais notification email échouée : {msg}")
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
    if not request.user.profile.can_add_project_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour supprimer ce jalon.")
        return redirect('core:projects')
    
    if request.method == 'POST':
        milestone_name = milestone.name
        milestone.delete()
        log_project_activity(project, 'suppr_jalon', f"Suppression du jalon '{milestone_name}'", request.user)
        messages.success(request, "Jalon supprimé.")
        return redirect('core:project_detail', project_id=project.id)
    
    return render(request, 'core/confirm_delete.html', {'object': milestone, 'type': 'jalon', 'back_url': 'core:project_detail', 'back_args': {'project_id': project.id}})


# ==================== SUB-MILESTONE CRUD ====================

@login_required
def sub_milestone_create(request, milestone_id):
    """Créer une sous-étape pour un jalon"""
    from .forms_project import SubMilestoneForm
    from .models import Milestone
    
    milestone = get_object_or_404(Milestone.objects.select_related('project'), pk=milestone_id)
    project = milestone.project
    
    # Permission check
    if not request.user.profile.can_add_project_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour ajouter des sous-étapes.")
        return redirect('core:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        form = SubMilestoneForm(milestone=milestone, data=request.POST)
        if form.is_valid():
            sub_milestone = form.save(commit=False)
            sub_milestone.milestone = milestone
            if sub_milestone.assigned_to:
                sub_milestone.assigned_by = request.user
            sub_milestone.save()
            log_project_activity(project, 'ajout_sous_etape', f"Ajout de la sous-étape '{sub_milestone.name}' au jalon '{milestone.name}'", request.user)
            # Notification email au responsable + chef de projet en CC
            if sub_milestone.assigned_to:
                from .notifications import notify_assignment
                assigned_by = request.user.get_full_name() or request.user.username
                success, msg = notify_assignment(sub_milestone.assigned_to, 'sous-étape', sub_milestone.name, project.name, assigned_by, project=project, due_date=sub_milestone.due_date)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Sous-étape créée mais notification email échouée : {msg}")
            messages.success(request, "Sous-étape ajoutée avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = SubMilestoneForm(milestone=milestone)
    
    return render(request, 'core/sub_milestone_form.html', {
        'form': form, 
        'milestone': milestone, 
        'project': project, 
        'title': f'Nouvelle sous-étape pour "{milestone.name}"'
    })


@login_required
def sub_milestone_edit(request, sub_milestone_id):
    """Modifier une sous-étape"""
    from .forms_project import SubMilestoneForm
    from .models import SubMilestone
    
    sub_milestone = get_object_or_404(SubMilestone.objects.select_related('milestone__project'), pk=sub_milestone_id)
    milestone = sub_milestone.milestone
    project = milestone.project
    
    # Permission check
    if not request.user.profile.can_add_project_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour modifier cette sous-étape.")
        return redirect('core:project_detail', project_id=project.id)
    
    old_assigned = sub_milestone.assigned_to_id
    was_completed = sub_milestone.completed
    if request.method == 'POST':
        form = SubMilestoneForm(milestone=milestone, data=request.POST, instance=sub_milestone)
        if form.is_valid():
            sub_milestone = form.save(commit=False)
            if sub_milestone.assigned_to and sub_milestone.assigned_to_id != old_assigned:
                sub_milestone.assigned_by = request.user
            sub_milestone.save()
            log_project_activity(project, 'modif_sous_etape', f"Modification de la sous-étape '{sub_milestone.name}'", request.user)
            # Notification email si le responsable a changé (chef de projet en CC)
            if sub_milestone.assigned_to and sub_milestone.assigned_to_id != old_assigned:
                from .notifications import notify_assignment
                assigned_by = request.user.get_full_name() or request.user.username
                success, msg = notify_assignment(sub_milestone.assigned_to, 'sous-étape', sub_milestone.name, project.name, assigned_by, project=project, due_date=sub_milestone.due_date)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Sous-étape modifiée mais notification email échouée : {msg}")
            if sub_milestone.completed and not was_completed:
                from .notifications import notify_task_completed
                success, msg = notify_task_completed('sous-étape', sub_milestone.name, project, sub_milestone.assigned_to, sub_milestone.assigned_by, request.user)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Sous-étape terminée mais notification email échouée : {msg}")
            messages.success(request, "Sous-étape modifiée avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = SubMilestoneForm(milestone=milestone, instance=sub_milestone)
    
    return render(request, 'core/sub_milestone_form.html', {
        'form': form, 
        'milestone': milestone, 
        'project': project, 
        'sub_milestone': sub_milestone,
        'title': f'Modifier "{sub_milestone.name}"'
    })


@login_required
def sub_milestone_delete(request, sub_milestone_id):
    """Supprimer une sous-étape"""
    from .models import SubMilestone
    
    sub_milestone = get_object_or_404(SubMilestone.objects.select_related('milestone__project'), pk=sub_milestone_id)
    milestone = sub_milestone.milestone
    project = milestone.project
    
    # Permission check
    if not request.user.profile.can_add_project_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions pour supprimer cette sous-étape.")
        return redirect('core:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        sub_name = sub_milestone.name
        sub_milestone.delete()
        milestone.update_completion()
        project.recalculate_progress()
        log_project_activity(project, 'suppr_sous_etape', f"Suppression de la sous-étape '{sub_name}'", request.user)
        messages.success(request, "Sous-étape supprimée.")
        return redirect('core:project_detail', project_id=project.id)
    
    return render(request, 'core/confirm_delete.html', {
        'object': sub_milestone, 
        'type': 'sous-étape', 
        'back_url': 'core:project_detail', 
        'back_args': {'project_id': project.id}
    })


@login_required
def sub_milestone_toggle(request, sub_milestone_id):
    """Basculer le statut complété d'une sous-étape"""
    from .models import SubMilestone
    
    sub_milestone = get_object_or_404(SubMilestone.objects.select_related('milestone__project'), pk=sub_milestone_id)
    milestone = sub_milestone.milestone
    project = milestone.project
    
    # Permission check
    if not request.user.profile.can_add_project_milestones(project):
        messages.error(request, "Vous n'avez pas les permissions.")
        return redirect('core:project_detail', project_id=project.id)
    
    was_completed = sub_milestone.completed
    sub_milestone.completed = not sub_milestone.completed
    sub_milestone.save()
    
    status = "complétée" if sub_milestone.completed else "non complétée"
    log_project_activity(project, 'toggle_sous_etape', f"Sous-étape '{sub_milestone.name}' marquée comme {status}", request.user)
    if sub_milestone.completed and not was_completed:
        from .notifications import notify_task_completed
        success, msg = notify_task_completed('sous-étape', sub_milestone.name, project, sub_milestone.assigned_to, sub_milestone.assigned_by, request.user)
        if success:
            messages.info(request, msg)
        else:
            messages.warning(request, f"Sous-étape terminée mais notification email échouée : {msg}")
    messages.success(request, f"Sous-étape marquée comme {status}.")
    return redirect('core:project_detail', project_id=project.id)


@login_required
def api_project_task_create(request, project_id):
    """Créer une tâche de projet depuis le board Planner."""
    import json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    project = get_object_or_404(Project, pk=project_id)
    if not request.user.profile.can_add_project_milestones(project):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body or '{}')
        title = (data.get('title') or '').strip()
        status = data.get('status') or 'a_faire'
        if not title:
            return JsonResponse({'error': 'Le titre est requis.'}, status=400)

        max_order = project.milestones.aggregate(models.Max('order'))['order__max'] or 0
        progress = 0
        completed = False
        if status == 'en_cours':
            progress = 50
        elif status == 'termine':
            progress = 100
            completed = True

        milestone = Milestone.objects.create(
            project=project,
            name=title,
            manual_progress=progress,
            completed=completed,
            order=max_order + 1,
        )
        project.recalculate_progress()
        log_project_activity(project, 'ajout_jalon', f"Ajout de la tâche '{milestone.name}'", request.user)
        return JsonResponse({
            'success': True,
            'task': {
                'id': milestone.id,
                'name': milestone.name,
                'progress': milestone.progress,
                'completed': milestone.completed,
                'sub_count': 0,
                'edit_url': reverse('core:milestone_edit', args=[milestone.id]),
                'sub_url': reverse('core:sub_milestone_create', args=[milestone.id]),
                'update_url': reverse('core:api_project_task_update', args=[milestone.id]),
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_project_task_update(request, milestone_id):
    """Mettre à jour une tâche depuis la fiche latérale Planner."""
    import json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    milestone = get_object_or_404(Milestone.objects.select_related('project'), pk=milestone_id)
    project = milestone.project
    if not request.user.profile.can_add_project_milestones(project):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body or '{}')
        if 'title' in data:
            title = (data.get('title') or '').strip()
            if title:
                milestone.name = title
        if 'description' in data:
            milestone.need = data.get('description') or ''
        if 'status' in data:
            status = data.get('status')
            if status == 'a_faire':
                milestone.manual_progress = 0
                milestone.completed = False
            elif status == 'en_cours':
                milestone.manual_progress = 50
                milestone.completed = False
            elif status == 'termine':
                milestone.manual_progress = 100
                milestone.completed = True
        if 'progress' in data:
            progress = max(0, min(100, int(data.get('progress') or 0)))
            milestone.manual_progress = progress
            milestone.completed = progress >= 100

        milestone.save()
        project.recalculate_progress()
        log_project_activity(project, 'modif_jalon', f"Mise à jour de la tâche '{milestone.name}'", request.user)
        return JsonResponse({'success': True, 'task': {'id': milestone.id, 'name': milestone.name, 'progress': milestone.progress, 'completed': milestone.completed, 'update_url': reverse('core:api_project_task_update', args=[milestone.id])}})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


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
            log_project_activity(project, 'ajout_document', f"Ajout du document '{doc.title}'", request.user)
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


@login_required
def project_document_download(request, doc_id):
    """Télécharger un document de projet"""
    from django.http import FileResponse
    import os
    
    doc = get_object_or_404(ProjectDocument.objects.select_related('project'), pk=doc_id)
    project = doc.project
    
    # Permission check
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
    
    # Retourner le fichier
    file_path = doc.file.path
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    else:
        messages.error(request, "Fichier non trouvé.")
        return redirect('core:project_detail', project_id=project.id)


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
    
    # Calculate available employees count
    existing_member_ids = project.members.values_list('employee_id', flat=True)
    available_employees_count = Employee.objects.exclude(id__in=existing_member_ids).count()
    
    context = {
        'project': project,
        'title': 'Ajouter un membre',
        'directions': directions,
        'available_employees_count': available_employees_count,
    }
    
    if request.method == 'POST':
        # Debug: afficher les données POST
        print(f"POST data: {request.POST}")
        create_new_employee = request.POST.get('create_new_employee') == 'on'
        
        if create_new_employee:
            # Créer un nouvel employé
            new_name = request.POST.get('new_employee_name', '').strip()
            new_role_employee = request.POST.get('new_employee_role', '').strip()
            new_phone = request.POST.get('new_employee_phone', '').strip()
            new_email = request.POST.get('new_employee_email', '').strip()
            project_role = request.POST.get('role', 'membre')
            
            # Validation
            errors = []
            if not new_name:
                errors.append("Le nom de l'employé est requis.")
            if not new_role_employee:
                errors.append("Le poste/fonction est requis.")
            
            if errors:
                for error in errors:
                    messages.error(request, error)
                context['create_new_employee'] = True
                context['new_employee_name'] = new_name
                context['new_employee_role'] = new_role_employee
                context['new_employee_phone'] = new_phone
                context['new_employee_email'] = new_email
                # Créer un formulaire avec les données POST pour préserver les permissions
                form = ProjectMemberForm(project, request.POST)
                context['form'] = form
                return render(request, 'core/project_member_form.html', context)
            
            # Créer l'employé (utiliser la direction du projet)
            try:
                new_employee = Employee.objects.create(
                    name=new_name,
                    direction=project.direction,
                    role=new_role_employee,
                    phone=new_phone,
                    email=new_email
                )
                
                # Créer le membre de projet
                member = ProjectMember.objects.create(
                    project=project,
                    employee=new_employee,
                    role=project_role
                )
                
                # Si le rôle est personnalisé, récupérer les permissions du formulaire
                if project_role == 'custom':
                    member.can_manage_members_perm = request.POST.get('can_manage_members_perm') == 'on'
                    member.can_edit_project_perm = request.POST.get('can_edit_project_perm') == 'on'
                    member.can_add_milestones_perm = request.POST.get('can_add_milestones_perm') == 'on'
                    member.can_add_documents_perm = request.POST.get('can_add_documents_perm') == 'on'
                    member.can_add_needs_perm = request.POST.get('can_add_needs_perm') == 'on'
                    member.can_add_comments_perm = request.POST.get('can_add_comments_perm') == 'on'
                    member.save()
                
                log_project_activity(project, 'ajout_membre', f"Ajout du membre '{new_name}' ({project_role})", request.user)
                from .notifications import notify_project_member_added
                success, msg = notify_project_member_added(member, request.user)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Membre ajouté mais notification email échouée : {msg}")
                messages.success(request, f"Employé '{new_name}' créé et ajouté au projet avec succès.")
                return redirect('core:project_detail', project_id=project.id)
            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f"Erreur lors de la création: {str(e)}")
                context['create_new_employee'] = True
                context['new_employee_name'] = new_name
                context['new_employee_role'] = new_role_employee
                context['new_employee_phone'] = new_phone
                context['new_employee_email'] = new_email
                form = ProjectMemberForm(project, request.POST)
                context['form'] = form
                return render(request, 'core/project_member_form.html', context)
        else:
            # Employé existant
            form = ProjectMemberForm(project, request.POST)
            if form.is_valid():
                member = form.save(commit=False)
                member.project = project
                member.save()
                log_project_activity(project, 'ajout_membre', f"Ajout du membre '{member.employee.name}' ({member.get_role_display()})", request.user)
                from .notifications import notify_project_member_added
                success, msg = notify_project_member_added(member, request.user)
                if success:
                    messages.info(request, msg)
                else:
                    messages.warning(request, f"Membre ajouté mais notification email échouée : {msg}")
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
            log_project_activity(project, 'ajout_membre', f"Modification du rôle de '{member.employee.name}' en '{member.get_role_display()}'", request.user)
            messages.success(request, "Rôle du membre modifié avec succès.")
            return redirect('core:project_detail', project_id=project.id)
    else:
        form = ProjectMemberForm(project, instance=member)
    
    # Calculate available employees count
    existing_member_ids = project.members.values_list('employee_id', flat=True)
    available_employees_count = Employee.objects.exclude(id__in=existing_member_ids).count()
    
    return render(request, 'core/project_member_form.html', {
        'form': form, 
        'project': project, 
        'member': member, 
        'title': f'Modifier {member.employee.name}',
        'available_employees_count': available_employees_count,
    })


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
        member_name = member.employee.name
        member.delete()
        log_project_activity(project, 'retrait_membre', f"Retrait du membre '{member_name}'", request.user)
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
    if not request.user.profile.can_approve_requests:
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
    if not request.user.profile.can_approve_requests:
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


def _user_can_manage_employee(user, employee=None):
    """Verifie si l'utilisateur peut gerer (creer/modifier/supprimer) un employe.
    - Admin / DG : tous
    - Directeur : uniquement les employes de sa direction
    """
    profile = getattr(user, 'profile', None)
    if not profile:
        return False
    if profile.role in ['admin', 'directeur_general']:
        return True
    if profile.role == 'directeur':
        if employee is None:
            return profile.direction_id is not None
        return profile.direction_id is not None and employee.direction_id == profile.direction_id
    # Permission heritee budget_manage etc.
    return profile.can_manage_budgets() and (employee is None or profile.direction_id == employee.direction_id)


# Employee management views
@login_required
def employee_create(request):
    """Créer un nouvel employé"""
    from .forms_project import EmployeeForm

    if not _user_can_manage_employee(request.user):
        messages.error(request, "Vous n'avez pas les permissions pour gérer les employés.")
        return redirect('core:resources')

    profile = request.user.profile

    if request.method == 'POST':
        form = EmployeeForm(request.POST, user=request.user)
        if form.is_valid():
            employee = form.save(commit=False)
            # Forcer la direction si l'utilisateur est un directeur
            if profile.role == 'directeur' and profile.direction_id:
                employee.direction_id = profile.direction_id
            employee.save()
            messages.success(request, "Employé créé avec succès.")
            return redirect('core:resources')
    else:
        form = EmployeeForm(user=request.user)

    return render(request, 'core/employee_form.html', {'form': form, 'title': 'Nouvel employé'})


@login_required
def employee_edit(request, employee_id):
    """Modifier un employé existant"""
    from .forms_project import EmployeeForm

    employee = get_object_or_404(Employee, pk=employee_id)

    if not _user_can_manage_employee(request.user, employee):
        messages.error(request, "Vous ne pouvez gérer que les employés de votre direction.")
        return redirect('core:resources')

    profile = request.user.profile

    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            if profile.role == 'directeur' and profile.direction_id:
                obj.direction_id = profile.direction_id
            obj.save()
            messages.success(request, "Employé modifié avec succès.")
            return redirect('core:resources')
    else:
        form = EmployeeForm(instance=employee, user=request.user)

    return render(request, 'core/employee_form.html', {'form': form, 'employee': employee, 'title': f'Modifier {employee.name}'})


@login_required
def employee_delete(request, employee_id):
    """Supprimer un employé"""
    employee = get_object_or_404(Employee, pk=employee_id)

    if not _user_can_manage_employee(request.user, employee):
        messages.error(request, "Vous ne pouvez supprimer que les employés de votre direction.")
        return redirect('core:resources')

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
    
    budget_label = budget.project.name if budget.project else (budget.direction.code if budget.direction else 'sans affectation')
    return render(request, 'core/budget_form.html', {'form': form, 'budget': budget, 'title': f'Modifier budget {budget_label}'})


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
            'direction': budget.direction.code if budget.direction else '-',
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


@login_required
def milestone_reorder(request, project_id):
    """API pour réordonner les jalons par drag & drop"""
    import json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    project = get_object_or_404(Project, pk=project_id)
    
    try:
        data = json.loads(request.body)
        order_list = data.get('order', [])
        for index, milestone_id in enumerate(order_list):
            Milestone.objects.filter(pk=milestone_id, project=project).update(order=index + 1)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def sub_milestone_reorder(request, milestone_id):
    """API pour réordonner les sous-étapes par drag & drop"""
    import json
    from .models import SubMilestone
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    milestone = get_object_or_404(Milestone, pk=milestone_id)
    
    try:
        data = json.loads(request.body)
        order_list = data.get('order', [])
        for index, sub_id in enumerate(order_list):
            SubMilestone.objects.filter(pk=sub_id, milestone=milestone).update(order=index + 1)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_project_update_status(request, project_id):
    """API pour mettre à jour le statut d'un projet (Kanban drag & drop)"""
    import json
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    project = get_object_or_404(Project, pk=project_id)
    
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        valid_statuses = [s[0] for s in Project.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({'error': f'Invalid status: {new_status}'}, status=400)
        
        project.status = new_status
        project.save(update_fields=['status', 'updated_at'])
        return JsonResponse({'success': True, 'status': new_status})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
