"""Vues pour la gestion des demandes de conge CSIG."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms_leave import (
    LeaveRequestForm,
    LeaveManagerDecisionForm,
    LeaveHRDecisionForm,
    LeaveFinalDecisionForm,
)
from .models import LeaveRequest
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
    if profile.role == 'directeur':
        return profile.direction_id is not None and profile.direction_id == leave.direction_id
    # RH : uniquement apres avis hierarchique
    if profile.is_hr():
        return leave.status not in ['soumise']
    # Validateur explicite (can_approve_leaves) : seulement les demandes qu'il a touche
    if profile.can_approve_leaves and leave.manager_user_id == user.id:
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
    if profile.role == 'directeur' or profile.can_approve_leaves:
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
    can_manager = bool(profile and (profile.role == 'directeur' or profile.can_approve_leaves or profile.can_give_final_approval()))
    can_hr = bool(profile and profile.can_give_hr_check())
    can_final = bool(profile and profile.can_give_final_approval())

    # Querysets contextuels
    if tab == 'to_approve_manager':
        if not can_manager:
            return HttpResponseForbidden()
        qs = base_qs.filter(status='soumise')
        if profile.role == 'directeur' and not profile.can_give_final_approval():
            qs = qs.filter(direction_id=profile.direction_id)
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
        if profile.role == 'directeur' and not profile.can_give_final_approval():
            mgr_qs = mgr_qs.filter(direction_id=profile.direction_id)
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
            try:
                notifications.notify_leave_submitted(leave)
            except Exception:
                pass
            messages.success(request, "Demande de congé soumise. Elle suit maintenant le circuit de validation.")
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
        messages.error(request, "Cette demande ne peut plus être modifiée.")
        return redirect('core:leave_detail', leave_id=leave.id)

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES, instance=leave, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Demande mise à jour.")
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
        messages.info(request, "Demande annulée.")
    return redirect('core:leave_list')


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
        messages.error(request, "Cette demande n'est plus en attente d'avis hiérarchique.")
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
            except Exception:
                pass
            messages.success(request, "Avis hiérarchique enregistré.")
            return redirect('core:leave_detail', leave_id=obj.id)
    return redirect('core:leave_detail', leave_id=leave.id)


@login_required
def leave_decide_hr(request, leave_id):
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    profile = _profile(request.user)
    if not (profile and profile.can_give_hr_check()):
        return HttpResponseForbidden()
    if leave.status != 'avis_favorable':
        messages.error(request, "Cette demande n'est pas au stade de la vérification RH.")
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
            except Exception:
                pass
            messages.success(request, "Vérification RH enregistrée.")
            return redirect('core:leave_detail', leave_id=obj.id)
    return redirect('core:leave_detail', leave_id=leave.id)


@login_required
def leave_decide_final(request, leave_id):
    leave = get_object_or_404(LeaveRequest, pk=leave_id)
    profile = _profile(request.user)
    if not (profile and profile.can_give_final_approval()):
        return HttpResponseForbidden()
    if leave.status != 'rh_conforme':
        messages.error(request, "Cette demande n'est pas prête pour la décision finale.")
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
                notifications.notify_leave_final_decided(obj)
            except Exception:
                pass
            messages.success(request, "Décision finale enregistrée et notifiée.")
            return redirect('core:leave_detail', leave_id=obj.id)
    return redirect('core:leave_detail', leave_id=leave.id)
