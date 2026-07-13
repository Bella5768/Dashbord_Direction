"""Vues pour la gestion des demandes de conge CSIG."""
from django.utils.translation import gettext as _
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms_leave import (
    LeaveRequestForm,
    LeaveManagerDecisionForm,
    LeaveHRDecisionForm,
    LeaveFinalDecisionForm,
)
from .models import LeaveRequest, LeaveDocument
from . import notifications


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(user):
    return getattr(user, 'profile', None)


def _user_can_view_leave(user, leave):
    """Visibilite stricte par role :
    - Demandeur : voit sa demande
    - Admin / DG : voit tout
    - Directeur : voit uniquement les demandes de sa direction
    - RH : voit uniquement les demandes deja validees par la hierarchie (avis_favorable et plus)
    """
    if user.is_superuser:
        return True
    profile = _profile(user)
    if not profile:
        return False
    if leave.user_id == user.id:
        return True
    # Admin / DG : acces complet
    if profile.can_give_final_approval():
        return True
    # Directeur : uniquement sa direction
    if profile.role_slug == 'directeur':
        return profile.direction_id is not None and profile.direction_id == leave.direction_id
    # RH : uniquement les demandes qui entrent dans son périmètre de traitement
    if profile.is_hr():
        return leave.status in ['avis_favorable', 'rh_conforme', 'rh_non_conforme', 'approuvee', 'rejetee']
    # Validateur explicite (can_approve_leaves) : seulement les demandes qu'il a touche
    if profile.can_give_manager_approval() and leave.manager_user_id == user.id:
        return True
    return False


def _user_is_owner(user, leave):
    return leave.user_id == user.id


def _can_see_step(user, leave, step):
    """Determine si l'utilisateur peut voir une etape du workflow.

    step : 'manager' | 'hr' | 'final'
    Regles :
    - Demandeur : voit toutes les etapes (c'est sa demande)
    - Admin / DG : voit tout
    - Directeur : voit uniquement etape 'manager'
    - RH : voit etapes 'manager' et 'hr', pas 'final'
    """
    if user.is_superuser:
        return True
    profile = _profile(user)
    if not profile:
        return False
    if leave.user_id == user.id:
        return True
    if profile.can_give_final_approval():
        return True
    if profile.is_hr():
        return step in ('manager', 'hr')
    if profile.role_slug == 'directeur' or profile.can_give_manager_approval():
        return step == 'manager'
    return False


# ---------------------------------------------------------------------------
# Liste & detail
# ---------------------------------------------------------------------------

@login_required
def leave_list(request):
    """Liste filtrable des demandes de conge avec restrictions par role.

    Onglets disponibles selon le role :
    - Tous : 'mine' (Mes demandes)
    - Directeur : + 'to_approve_manager' (sa direction uniquement) + 'history_mine_decisions'
    - RH : + 'to_check_hr' + 'history_hr'
    - Admin / DG : + 'to_decide' + 'all'
    """
    profile = _profile(request.user)
    tab = request.GET.get('tab', 'mine')
    status_filter = request.GET.get('status', '')

    base_qs = LeaveRequest.objects.select_related('employee', 'direction', 'user')

    # Permissions par onglet
    can_manager = bool(profile and (profile.role_slug == 'directeur' or profile.can_give_manager_approval() or profile.can_give_final_approval()))
    can_hr = bool(profile and profile.can_give_hr_check())
    can_final = bool(profile and profile.can_give_final_approval())

    # Querysets contextuels
    if tab == 'to_approve_manager':
        if not can_manager:
            return HttpResponseForbidden()
        qs = base_qs.filter(status='soumise')
        # Tout non-DG est scopé à sa direction (couvre directeur ET rôles custom avec same_direction)
        if not profile.can_give_final_approval():
            if profile.direction_id:
                qs = qs.filter(direction_id=profile.direction_id)
            else:
                qs = base_qs.none()
    elif tab == 'history_mine_decisions':
        if not can_manager:
            return HttpResponseForbidden()
        qs = base_qs.filter(manager_user=request.user)
    elif tab == 'to_check_hr':
        if not can_hr:
            return HttpResponseForbidden()
        qs = base_qs.filter(status='avis_favorable')
    elif tab == 'history_hr':
        if not can_hr:
            return HttpResponseForbidden()
        qs = base_qs.filter(hr_user=request.user)
    elif tab == 'to_decide':
        if not can_final:
            return HttpResponseForbidden()
        qs = base_qs.filter(status='rh_conforme')
    elif tab == 'all':
        if not can_final:
            return HttpResponseForbidden()
        qs = base_qs.all()
    else:  # mine
        tab = 'mine'
        qs = base_qs.filter(user=request.user)

    if status_filter:
        qs = qs.filter(status=status_filter)

    # Compteurs pour les onglets visibles
    counts = {
        'mine': base_qs.filter(user=request.user).count(),
        'to_approve_manager': 0,
        'history_mine_decisions': 0,
        'to_check_hr': 0,
        'history_hr': 0,
        'to_decide': 0,
        'all': 0,
    }
    if can_manager:
        mgr_qs = base_qs.filter(status='soumise')
        if not profile.can_give_final_approval():
            if profile.direction_id:
                mgr_qs = mgr_qs.filter(direction_id=profile.direction_id)
            else:
                mgr_qs = base_qs.none()
        counts['to_approve_manager'] = mgr_qs.count()
        counts['history_mine_decisions'] = base_qs.filter(manager_user=request.user).count()
    if can_hr:
        counts['to_check_hr'] = base_qs.filter(status='avis_favorable').count()
        counts['history_hr'] = base_qs.filter(hr_user=request.user).count()
    if can_final:
        counts['to_decide'] = base_qs.filter(status='rh_conforme').count()
        counts['all'] = base_qs.count()

    # Stats personnelles (onglet "mine")
    mine_qs = base_qs.filter(user=request.user)
    my_stats = {
        'total': mine_qs.count(),
        'pending': mine_qs.filter(status__in=['soumise', 'avis_favorable', 'rh_conforme']).count(),
        'approved': mine_qs.filter(status='approuvee').count(),
        'rejected': mine_qs.filter(status__in=['rejetee', 'avis_defavorable', 'rh_non_conforme']).count(),
        'days_approved': sum(l.days_count for l in mine_qs.filter(status='approuvee')),
    }

    context = {
        'leaves': qs.order_by('-created_at'),
        'tab': tab,
        'counts': counts,
        'status_filter': status_filter,
        'status_choices': LeaveRequest.STATUS_CHOICES,
        'profile': profile,
        'can_manager': can_manager,
        'can_hr': can_hr,
        'can_final': can_final,
        'my_stats': my_stats,
    }
    return render(request, 'core/leaves/leave_list.html', context)


@login_required
def leave_detail(request, leave_id):
    leave = get_object_or_404(
        LeaveRequest.objects.select_related('employee', 'direction', 'user', 'manager_user', 'hr_user', 'final_user'),
        pk=leave_id,
    )
    if not _user_can_view_leave(request.user, leave):
        return HttpResponseForbidden("Vous n'avez pas accès à cette demande.")

    profile = _profile(request.user)
    can_act_manager = bool(profile and profile.can_give_manager_approval(leave) and leave.status == 'soumise')
    can_act_hr = bool(profile and profile.can_give_hr_check() and leave.status == 'avis_favorable')
    can_act_final = bool(profile and profile.can_give_final_approval() and leave.status == 'rh_conforme')
    can_cancel = _user_is_owner(request.user, leave) and leave.is_pending

    # Visibilite par etape selon le role
    can_see_manager_step = _can_see_step(request.user, leave, 'manager')
    can_see_hr_step = _can_see_step(request.user, leave, 'hr')
    can_see_final_step = _can_see_step(request.user, leave, 'final')

    context = {
        'leave': leave,
        'documents': leave.documents.all(),
        'can_act_manager': can_act_manager,
        'can_act_hr': can_act_hr,
        'can_act_final': can_act_final,
        'can_cancel': can_cancel,
        'can_see_manager_step': can_see_manager_step,
        'can_see_hr_step': can_see_hr_step,
        'can_see_final_step': can_see_final_step,
        'manager_form': LeaveManagerDecisionForm(instance=leave) if can_act_manager else None,
        'hr_form': LeaveHRDecisionForm(instance=leave) if can_act_hr else None,
        'final_form': LeaveFinalDecisionForm(instance=leave) if can_act_final else None,
    }
    return render(request, 'core/leaves/leave_detail.html', context)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

@login_required
def leave_create(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.user = request.user
            leave.status = 'soumise'
            leave.save()
            form.save_extra_documents(leave)
            try:
                notifications.notify_leave_submitted(leave)
            except (AttributeError, ValueError, ConnectionError) as e:
                from .error_logging import ErrorLogger
                ErrorLogger.log_exception(e, context={'function': 'leave_create', 'leave_id': leave.id}, user=request.user)
            messages.success(request, _("Demande de congé soumise. Elle suit maintenant le circuit de validation."))
            return redirect('core:leave_detail', leave_id=leave.id)
    else:
        form = LeaveRequestForm(user=request.user)

    return render(request, 'core/leaves/leave_form.html', {
        'form': form,
        'title': 'Nouvelle demande de congé',
    })


@login_required
def leave_edit(request, leave_id):
    """Modifier une demande encore au stade 'soumise' (par son auteur)."""
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    if not _user_is_owner(request.user, leave):
        return HttpResponseForbidden()
    if leave.status != 'soumise':
        messages.error(request, _("Cette demande ne peut plus être modifiée."))
        return redirect('core:leave_detail', leave_id=leave.id)

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES, instance=leave, user=request.user)
        if form.is_valid():
            form.save()
            form.save_extra_documents(leave)
            messages.success(request, _("Demande mise à jour."))
            return redirect('core:leave_detail', leave_id=leave.id)
    else:
        form = LeaveRequestForm(instance=leave, user=request.user)

    return render(request, 'core/leaves/leave_form.html', {
        'form': form,
        'title': 'Modifier la demande de congé',
        'leave': leave,
    })


@login_required
def leave_cancel(request, leave_id):
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    if not _user_is_owner(request.user, leave) or not leave.is_pending:
        return HttpResponseForbidden()
    if request.method == 'POST':
        leave.status = 'annulee'
        leave.save(update_fields=['status', 'updated_at'])
        messages.info(request, _("Demande annulée."))
    return redirect('core:leave_list')


@login_required
def leave_document_delete(request, leave_id, doc_id):
    """Supprime une piece jointe. Reserve a l'auteur tant que la demande
    est encore au stade 'soumise'."""
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    doc = get_object_or_404(LeaveDocument, pk=doc_id, leave_request=leave)
    if not _user_is_owner(request.user, leave) or leave.status != 'soumise':
        return HttpResponseForbidden()
    if request.method == 'POST':
        try:
            doc.file.delete(save=False)
        except (AttributeError, OSError, ValueError) as e:
            from .error_logging import ErrorLogger
            ErrorLogger.log_exception(e, context={'function': 'leave_document_delete', 'doc_id': doc.id}, user=request.user)
        doc.delete()
        messages.success(request, _("Pièce jointe supprimée."))
    return redirect('core:leave_detail', leave_id=leave.id)


# ---------------------------------------------------------------------------
# Workflow (3 etapes)
# ---------------------------------------------------------------------------

@login_required
def leave_decide_manager(request, leave_id):
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    profile = _profile(request.user)
    if not (profile and profile.can_give_manager_approval(leave)):
        return HttpResponseForbidden()
    if leave.status != 'soumise':
        messages.error(request, _("Cette demande n'est plus en attente d'avis hiérarchique."))
        return redirect('core:leave_detail', leave_id=leave.id)

    if request.method == 'POST':
        form = LeaveManagerDecisionForm(request.POST, instance=leave)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.manager_user = request.user
            obj.manager_decision_at = timezone.now()
            if obj.manager_decision == 'favorable':
                obj.status = 'avis_favorable'
            else:
                obj.status = 'avis_defavorable'
            obj.save()
            try:
                notifications.notify_leave_manager_decided(obj)
            except (AttributeError, ValueError, ConnectionError) as e:
                from .error_logging import ErrorLogger
                ErrorLogger.log_exception(e, context={'function': 'leave_decide_manager', 'leave_id': obj.id}, user=request.user)
            from .notifs import notify_conge_avis
            notify_conge_avis(obj, request.user)
            messages.success(request, _("Avis hiérarchique enregistré."))
            return redirect('core:leave_detail', leave_id=obj.id)
    return redirect('core:leave_detail', leave_id=leave.id)


@login_required
def leave_decide_hr(request, leave_id):
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    profile = _profile(request.user)
    if not (profile and profile.can_give_hr_check()):
        return HttpResponseForbidden()
    if leave.status != 'avis_favorable':
        messages.error(request, _("Cette demande n'est pas au stade de la vérification RH."))
        return redirect('core:leave_detail', leave_id=leave.id)

    if request.method == 'POST':
        form = LeaveHRDecisionForm(request.POST, instance=leave)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.hr_user = request.user
            obj.hr_decision_at = timezone.now()
            if obj.hr_decision == 'conforme':
                obj.status = 'rh_conforme'
            else:
                obj.status = 'rh_non_conforme'
            obj.save()
            try:
                notifications.notify_leave_hr_decided(obj)
            except (AttributeError, ValueError, ConnectionError) as e:
                from .error_logging import ErrorLogger
                ErrorLogger.log_exception(e, context={'function': 'leave_decide_hr', 'leave_id': obj.id}, user=request.user)
            from .notifs import notify_conge_rh
            notify_conge_rh(obj, request.user)
            messages.success(request, _("Vérification RH enregistrée."))
            return redirect('core:leave_detail', leave_id=obj.id)
    return redirect('core:leave_detail', leave_id=leave.id)


@login_required
def leave_decide_final(request, leave_id):
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    profile = _profile(request.user)
    if not (profile and profile.can_give_final_approval()):
        return HttpResponseForbidden()
    if leave.status != 'rh_conforme':
        messages.error(request, _("Cette demande n'est pas prête pour la décision finale."))
        return redirect('core:leave_detail', leave_id=leave.id)

    if request.method == 'POST':
        form = LeaveFinalDecisionForm(request.POST, instance=leave)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.final_user = request.user
            obj.final_decision_at = timezone.now()
            if obj.final_decision == 'approuve':
                obj.status = 'approuvee'
            else:
                obj.status = 'rejetee'
            obj.save()
            try:
                # Générer le PDF d'attestation si approuvé
                pdf_bytes = None
                if obj.status == 'approuvee':
                    from .pdf_generator import generate_leave_approval_pdf
                    pdf_bytes = generate_leave_approval_pdf(obj)
                notifications.notify_leave_final_decided(obj, pdf_bytes)
            except (AttributeError, ValueError, ConnectionError) as e:
                from .error_logging import ErrorLogger
                ErrorLogger.log_exception(e, context={'function': 'leave_decide_final', 'leave_id': obj.id}, user=request.user)
            from .notifs import notify_conge_decision
            notify_conge_decision(obj, request.user)
            messages.success(request, _("Décision finale enregistrée et notifiée."))
            return redirect('core:leave_detail', leave_id=obj.id)
    return redirect('core:leave_detail', leave_id=leave.id)


@login_required
def leave_pdf_download(request, leave_id):
    """Telecharge le PDF d'attestation de conge approuve.
    Accessible a tous les stakeholders qui peuvent voir la demande.
    """
    leave = get_object_or_404(
        LeaveRequest.objects.select_related('employee', 'direction', 'user', 'manager_user', 'hr_user', 'final_user'),
        pk=leave_id,
    )
    if not _user_can_view_leave(request.user, leave):
        return HttpResponseForbidden("Vous n'avez pas accès à cette demande.")
    if leave.status != 'approuvee':
        messages.error(request, _("L'attestation n'est disponible que pour les demandes approuvées."))
        return redirect('core:leave_detail', leave_id=leave.id)

    from .pdf_generator import generate_leave_approval_pdf
    pdf_bytes = generate_leave_approval_pdf(leave)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"attestation_conge_{leave.employee.name.replace(' ', '_')}_{leave.id}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
