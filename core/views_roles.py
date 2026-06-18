"""Vues RBAC : gestion des rôles globaux et des rôles projet."""
from django.utils.translation import gettext as _
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Permission, Role, ProjectRole


def _require_role_admin(request):
    """Retourne None si l'utilisateur peut gérer les rôles, ou une réponse redirect."""
    if not request.user.profile.can('manage', 'Role'):
        messages.error(request, _("Vous n'avez pas la permission de gérer les rôles."))
        return redirect('core:dashboard')
    return None


# ---------------------------------------------------------------------------
# Rôles globaux
# ---------------------------------------------------------------------------

@login_required
def roles_list(request):
    guard = _require_role_admin(request)
    if guard:
        return guard

    roles = Role.objects.prefetch_related('permissions').order_by('name')
    permissions = Permission.objects.all().order_by('subject', 'action')

    # Grouper les permissions par subject pour l'affichage
    subjects = {}
    for perm in permissions:
        subjects.setdefault(perm.subject, []).append(perm)

    context = {
        'roles': roles,
        'subjects': subjects,
        'permission_count': permissions.count(),
    }
    return render(request, 'core/roles/roles_list.html', context)


@login_required
def role_detail(request, role_id):
    guard = _require_role_admin(request)
    if guard:
        return guard

    role = get_object_or_404(Role, pk=role_id)
    all_permissions = Permission.objects.all().order_by('subject', 'action')
    role_perm_ids = set(role.permissions.values_list('id', flat=True))

    subjects = {}
    for perm in all_permissions:
        subjects.setdefault(perm.subject, []).append(perm)

    context = {
        'role': role,
        'subjects': subjects,
        'role_perm_ids': role_perm_ids,
        'user_count': role.users.count(),
    }
    return render(request, 'core/roles/role_detail.html', context)


@login_required
def role_create(request):
    guard = _require_role_admin(request)
    if guard:
        return guard

    all_permissions = Permission.objects.all().order_by('subject', 'action')
    subjects = {}
    for perm in all_permissions:
        subjects.setdefault(perm.subject, []).append(perm)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip()
        description = request.POST.get('description', '').strip()
        perm_ids = request.POST.getlist('permissions')

        if not name or not slug:
            messages.error(request, _("Le nom et l'identifiant sont obligatoires."))
        elif Role.objects.filter(slug=slug).exists():
            messages.error(request, _("Un rôle avec cet identifiant existe déjà."))
        else:
            role = Role.objects.create(name=name, slug=slug, description=description)
            role.permissions.set(Permission.objects.filter(id__in=perm_ids))
            messages.success(request, _("Rôle « {name} » créé avec succès.").format(name=name))
            return redirect('core:role_detail', role_id=role.pk)

    context = {'subjects': subjects, 'role_perm_ids': set()}
    return render(request, 'core/roles/role_form.html', context)


@login_required
def role_edit(request, role_id):
    guard = _require_role_admin(request)
    if guard:
        return guard

    role = get_object_or_404(Role, pk=role_id)
    all_permissions = Permission.objects.all().order_by('subject', 'action')
    subjects = {}
    for perm in all_permissions:
        subjects.setdefault(perm.subject, []).append(perm)

    if request.method == 'POST':
        role.name        = request.POST.get('name', role.name).strip()
        role.description = request.POST.get('description', '').strip()
        perm_ids = request.POST.getlist('permissions')
        role.permissions.set(Permission.objects.filter(id__in=perm_ids))
        role.save()
        messages.success(request, _("Rôle « {name} » mis à jour.").format(name=role.name))
        return redirect('core:role_detail', role_id=role.pk)

    context = {
        'role': role,
        'subjects': subjects,
        'role_perm_ids': set(role.permissions.values_list('id', flat=True)),
        'editing': True,
    }
    return render(request, 'core/roles/role_form.html', context)


@login_required
def role_duplicate(request, role_id):
    guard = _require_role_admin(request)
    if guard:
        return guard

    source = get_object_or_404(Role, pk=role_id)
    base_slug = f"{source.slug}-copie"
    slug, n = base_slug, 2
    while Role.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1

    new_role = Role.objects.create(
        name=f"{source.name} (copie)",
        slug=slug,
        description=source.description,
        is_system=False,
    )
    new_role.permissions.set(source.permissions.all())
    messages.success(request, _("Rôle « {name} » créé à partir de « {source} ».").format(name=new_role.name, source=source.name))
    return redirect('core:role_edit', role_id=new_role.pk)


@login_required
def role_delete(request, role_id):
    guard = _require_role_admin(request)
    if guard:
        return guard

    role = get_object_or_404(Role, pk=role_id)
    if role.is_system:
        messages.error(request, _("Les rôles système ne peuvent pas être supprimés."))
        return redirect('core:roles_list')
    if role.users.exists():
        messages.error(request, _("Ce rôle est assigné à {count} utilisateur(s). Réassignez-les d'abord.").format(count=role.users.count()))
        return redirect('core:role_detail', role_id=role.pk)
    if request.method == 'POST':
        name = role.name
        role.delete()
        messages.success(request, _("Rôle « {name} » supprimé.").format(name=name))
        return redirect('core:roles_list')
    return render(request, 'core/roles/role_confirm_delete.html', {'role': role})


# ---------------------------------------------------------------------------
# Rôles projet
# ---------------------------------------------------------------------------

@login_required
def project_roles_list(request):
    guard = _require_role_admin(request)
    if guard:
        return guard

    project_roles = ProjectRole.objects.prefetch_related('permissions').order_by('name')
    permissions = Permission.objects.all().order_by('subject', 'action')
    subjects = {}
    for perm in permissions:
        subjects.setdefault(perm.subject, []).append(perm)

    context = {'project_roles': project_roles, 'subjects': subjects}
    return render(request, 'core/roles/project_roles_list.html', context)


@login_required
def project_role_create(request):
    guard = _require_role_admin(request)
    if guard:
        return guard

    all_permissions = Permission.objects.all().order_by('subject', 'action')
    subjects = {}
    for perm in all_permissions:
        subjects.setdefault(perm.subject, []).append(perm)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip()
        description = request.POST.get('description', '').strip()
        perm_ids = request.POST.getlist('permissions')

        if not name or not slug:
            messages.error(request, _("Le nom et l'identifiant sont obligatoires."))
        elif ProjectRole.objects.filter(slug=slug).exists():
            messages.error(request, _("Un rôle projet avec cet identifiant existe déjà."))
        else:
            pr = ProjectRole.objects.create(name=name, slug=slug, description=description)
            pr.permissions.set(Permission.objects.filter(id__in=perm_ids))
            messages.success(request, _("Rôle projet « {name} » créé.").format(name=name))
            return redirect('core:project_roles_list')

    context = {'subjects': subjects, 'role_perm_ids': set(), 'is_project': True}
    return render(request, 'core/roles/role_form.html', context)


@login_required
def project_role_edit(request, role_id):
    guard = _require_role_admin(request)
    if guard:
        return guard

    role = get_object_or_404(ProjectRole, pk=role_id)
    all_permissions = Permission.objects.all().order_by('subject', 'action')
    subjects = {}
    for perm in all_permissions:
        subjects.setdefault(perm.subject, []).append(perm)

    if request.method == 'POST':
        role.name        = request.POST.get('name', role.name).strip()
        role.description = request.POST.get('description', '').strip()
        perm_ids = request.POST.getlist('permissions')
        role.permissions.set(Permission.objects.filter(id__in=perm_ids))
        role.save()
        messages.success(request, _("Rôle projet « {name} » mis à jour.").format(name=role.name))
        return redirect('core:project_roles_list')

    context = {
        'role': role,
        'subjects': subjects,
        'role_perm_ids': set(role.permissions.values_list('id', flat=True)),
        'editing': True,
        'is_project': True,
    }
    return render(request, 'core/roles/role_form.html', context)


@login_required
def project_role_duplicate(request, role_id):
    guard = _require_role_admin(request)
    if guard:
        return guard

    source = get_object_or_404(ProjectRole, pk=role_id)
    base_slug = f"{source.slug}-copie"
    slug, n = base_slug, 2
    while ProjectRole.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1

    new_role = ProjectRole.objects.create(
        name=f"{source.name} (copie)",
        slug=slug,
        description=source.description,
        is_system=False,
    )
    new_role.permissions.set(source.permissions.all())
    messages.success(request, _("Rôle projet « {name} » créé.").format(name=new_role.name))
    return redirect('core:project_role_edit', role_id=new_role.pk)


@login_required
def project_role_delete(request, role_id):
    guard = _require_role_admin(request)
    if guard:
        return guard

    role = get_object_or_404(ProjectRole, pk=role_id)
    if role.is_system:
        messages.error(request, _("Les rôles système ne peuvent pas être supprimés."))
        return redirect('core:project_roles_list')
    if request.method == 'POST':
        name = role.name
        role.delete()
        messages.success(request, _("Rôle projet « {name} » supprimé.").format(name=name))
        return redirect('core:project_roles_list')
    return render(request, 'core/roles/role_confirm_delete.html', {'role': role, 'is_project': True})
