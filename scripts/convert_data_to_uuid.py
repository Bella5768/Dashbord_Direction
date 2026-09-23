"""
Migration des données : ancienne base (PK int) -> nouvelle base (PK UUID).

Usage :
    python scripts/convert_data_to_uuid.py "postgresql://<old_user>:<old_pass>@<host>/<db>?sslmode=require&channel_binding=require"

La nouvelle base (celle des settings Django actifs) doit déjà être migrée
(core.0001 UUID + core.0002 seeds).

Règles :
- auth_user est copié tel quel (PK int conservées ; les FK vers User restent int).
- Les seeds (Direction/Permission/Role/ProjectRole) sont réconciliés par clé
  naturelle avec ceux déjà présents dans la nouvelle base ; les directions
  manquantes sont créées.
- Les données métier reçoivent une PK UUID déterministe
  ``uuid5(NAMESPACE_URL, f"{Class}:{old_id}")`` ; les FK internes sont remappées.
- Les M2M (role_permissions, projectrole_permissions, assigned_to, event_participants)
  sont recopiées avec les nouveaux UUID.
- Idempotent : aucun doublon si relancé partiellement.
"""

import os
import sys
import uuid

sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard_csig.settings')

import django
django.setup()

import psycopg

from django.contrib.auth.models import User
from django.db import transaction
from core import models as M

OLD_URL = sys.argv[1] if len(sys.argv) > 1 else None
if not OLD_URL:
    print("URL de l'ancienne base requise.")
    sys.exit(1)

NS = uuid.NAMESPACE_URL


def new_id(klass, old_id):
    if old_id is None:
        return None
    return uuid.uuid5(NS, f"{klass}:{old_id}")


def execute(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


def single(cur, sql, args=()):
    cur.execute(sql, args)
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Connexion ancienne base
# ---------------------------------------------------------------------------
old = psycopg.connect(OLD_URL)
old.autocommit = True
cur = old.cursor()

# ---------------------------------------------------------------------------
# 1) auth_user
# ---------------------------------------------------------------------------
print("== auth_user ==")
existing_user_ids = set(User.objects.values_list('pk', flat=True))
user_rows = execute(cur, "SELECT id, password, last_login, is_superuser, username, last_name, email, is_staff, is_active, date_joined, first_name FROM auth_user ORDER BY id")
created_users = 0
for (uid, password, last_login, is_superuser, username, last_name, email,
     is_staff, is_active, date_joined, first_name) in user_rows:
    if uid in existing_user_ids:
        continue
    User.objects.create(
        id=uid,
        password=password,
        last_login=last_login,
        is_superuser=is_superuser,
        username=username,
        last_name=last_name,
        email=email,
        is_staff=is_staff,
        is_active=is_active,
        date_joined=date_joined,
        first_name=first_name,
    )
    created_users += 1
print(f"  utilisateurs créés : {created_users} / {len(user_rows)}")

# ---------------------------------------------------------------------------
# 2) Seeds : Direction / Permission / Role / ProjectRole réconciliés
# ---------------------------------------------------------------------------


def reconcile_directions(cur):
    print("== Direction ==")
    dir_map = {}
    existing_codes = set(M.Direction.objects.values_list('code', flat=True))
    rows = execute(cur, "SELECT id, name, code, color FROM core_direction ORDER BY id")
    created = 0
    for old_id, name, code, color in rows:
        direction = M.Direction.objects.filter(code=code).first()
        if direction is None:
            direction = M.Direction(id=new_id('Direction', old_id), name=name, code=code, color=color)
            direction.save()
            created += 1
        elif direction.slug is None:
            direction.slug = M.Direction._make_unique_slug(direction)
            direction.save(update_fields=['slug'])
        old_code = code
        dir_map[old_id] = (old_code, direction.id)
    print(f"  directions créées : {created}, mappées : {len(dir_map)}")
    return dir_map


def reconcile_permissions(cur):
    print("== Permission ==")
    perm_map = {}
    rows = execute(cur, "SELECT id, action, subject, condition, description FROM core_permission ORDER BY id")
    created = 0
    existing = {}
    for p in M.Permission.objects.all():
        existing[(p.action, p.subject, p.condition)] = p.id
    for old_id, action, subject, condition, description in rows:
        key = (action, subject, condition)
        new_pk = existing.get(key)
        if new_pk is None:
            perm = M.Permission(id=new_id('Permission', old_id), action=action, subject=subject,
                                condition=condition, description=description)
            perm.save()
            new_pk = perm.id
            existing[key] = new_pk
            created += 1
        perm_map[old_id] = (key, new_pk)
    print(f"  permissions créées : {created}, mappées : {len(perm_map)}")
    return perm_map


def reconcile_roles(cur):
    print("== Role / ProjectRole ==")
    role_map = {}
    existing_slugs = set(M.Role.objects.values_list('slug', flat=True))
    rows = execute(cur, "SELECT id, name, slug, description, is_system, created_at FROM core_role ORDER BY id")
    created = 0
    for old_id, name, slug, description, is_system, created_at in rows:
        role = M.Role.objects.filter(slug=slug).first()
        if role is None:
            role = M.Role(id=new_id('Role', old_id), name=name, slug=slug,
                          description=description, is_system=is_system)
            role.save()
            created += 1
        role_map[old_id] = (slug, role.id)
    print(f"  rôles créés : {created}, mappés : {len(role_map)}")

    prole_map = {}
    existing_slugs = set(M.ProjectRole.objects.values_list('slug', flat=True))
    prows = execute(cur, "SELECT id, name, slug, description, is_system, created_at FROM core_projectrole ORDER BY id")
    pcreated = 0
    for old_id, name, slug, description, is_system, created_at in prows:
        prole = M.ProjectRole.objects.filter(slug=slug).first()
        if prole is None:
            prole = M.ProjectRole(id=new_id('ProjectRole', old_id), name=name, slug=slug,
                                  description=description, is_system=is_system)
            prole.save()
            pcreated += 1
        prole_map[old_id] = (slug, prole.id)
    print(f"  rôles projet créés : {pcreated}, mappés : {len(prole_map)}")
    return role_map, prole_map


dir_map = reconcile_directions(cur)
perm_map = reconcile_permissions(cur)
role_map, prole_map = reconcile_roles(cur)


# ---------------------------------------------------------------------------
# 3) Données métier — ordre topologique
# ---------------------------------------------------------------------------


@transaction.atomic
def copy_employee():
    print("  Employee ...")
    map_emp = {}
    rows = execute(cur,
                   "SELECT id, name, direction_id, role, phone, email, workload, skills, is_external, organization "
                   "FROM core_employee ORDER BY id")
    existing_by_name = {e.name: e.id for e in M.Employee.objects.all()}
    created = 0
    for (old_id, name, direction_id, role, phone, email, workload, skills,
         is_external, organization) in rows:
        existing = M.Employee.objects.filter(id=new_id('Employee', old_id)).first()
        if existing:
            map_emp[old_id] = existing.id
            continue
        emp = M.Employee(
            id=new_id('Employee', old_id),
            name=name,
            direction_id=dir_map[direction_id][1] if direction_id else None,
            role=role,
            phone=phone or '',
            email=email or '',
            workload=workload or 0,
            skills=skills or '',
            is_external=is_external or False,
            organization=organization or '',
        )
        emp.save()
        map_emp[old_id] = emp.id
        created += 1
    print(f"    créés : {created} / {len(rows)}")
    return map_emp


def copy_partner():
    print("  Partner ...")
    map_part = {}
    rows = execute(cur,
                   "SELECT id, name, partner_type, status, contact_person, email, phone, start_date, logo "
                   "FROM core_partner ORDER BY id")
    created = 0
    for (old_id, name, partner_type, status, contact_person, email, phone,
         start_date, logo) in rows:
        obj = M.Partner.objects.filter(id=new_id('Partner', old_id)).first()
        if obj:
            map_part[old_id] = obj.id
            continue
        obj = M.Partner(
            id=new_id('Partner', old_id),
            name=name,
            partner_type=partner_type,
            status=status,
            contact_person=contact_person or '',
            email=email or '',
            phone=phone or '',
            start_date=start_date,
            logo=logo or '',
        )
        obj.save()
        map_part[old_id] = obj.id
        created += 1
    print(f"    créés : {created} / {len(rows)}")
    return map_part


def copy_project(map_emp):
    print("  Project ...")
    map_proj = {}
    rows = execute(cur,
                   "SELECT id, name, description, status, priority, progress, budget, budget_consumed, "
                   "start_date, end_date, manager, created_at, updated_at, direction_id, currency, "
                   "original_end_date, original_start_date, manager_employee_id "
                   "FROM core_project ORDER BY id")
    created = 0
    for (old_id, name, description, status, priority, progress, budget, budget_consumed,
         start_date, end_date, manager, created_at, updated_at, direction_id, currency,
         original_end_date, original_start_date, manager_employee_id) in rows:
        obj = M.Project.objects.filter(id=new_id('Project', old_id)).first()
        if obj:
            map_proj[old_id] = obj.id
            continue
        obj = M.Project(
            id=new_id('Project', old_id),
            name=name,
            description=description or '',
            status=status,
            priority=priority,
            progress=progress,
            budget=budget,
            budget_consumed=budget_consumed,
            start_date=start_date,
            end_date=end_date,
            manager=manager or '',
            created_at=created_at,
            updated_at=updated_at,
            direction_id=dir_map[direction_id][1] if direction_id else None,
            currency=currency or '',
            original_end_date=original_end_date,
            original_start_date=original_start_date,
            manager_employee_id=map_emp.get(manager_employee_id),
        )
        obj.save()
        map_proj[old_id] = obj.id
        created += 1
    print(f"    créés : {created} / {len(rows)}")
    return map_proj


def copy_userprofile(map_emp):
    print("  UserProfile ...")
    map_usr = {}
    rows = execute(cur,
                   "SELECT id, phone, avatar, is_active_profile, created_at, updated_at, direction_id, user_id, "
                   "employee_id, employee_identifier, role_id "
                   "FROM core_userprofile ORDER BY id")
    created = 0
    for (old_id, phone, avatar, is_active_profile, created_at, updated_at,
         direction_id, user_id, employee_id, employee_identifier, role_id) in rows:
        # Le signal post_save(created) a déjà créé un profil vide pour l'utilisateur :
        # on le réutilise (conserve son UUID) et on complète ses champs.
        obj = M.UserProfile.objects.filter(user_id=user_id).first()
        if obj is None:
            obj = M.UserProfile(id=new_id('UserProfile', old_id), user_id=user_id)
        obj.phone = phone or ''
        obj.avatar = avatar or ''
        obj.is_active_profile = is_active_profile if is_active_profile is not None else True
        obj.updated_at = updated_at
        obj.direction_id = dir_map[direction_id][1] if direction_id else None
        obj.employee_id = map_emp.get(employee_id)
        obj.employee_identifier = employee_identifier
        obj.role_id = role_map[role_id][1] if role_id else None
        obj.save()
        map_usr[old_id] = obj.id
        created += 1
    print(f"    à jour : {created} / {len(rows)}")
    return map_usr


def copy_milestones(map_proj):
    print("  Milestone ...")
    map_mil = {}
    rows = execute(cur,
                   "SELECT id, name, completed, \"order\", project_id, manual_progress, need, assigned_by_id, "
                   "due_date, completed_at, status "
                   "FROM core_milestone ORDER BY id")
    created = 0
    for (old_id, name, completed, order, project_id, manual_progress, need,
         assigned_by_id, due_date, completed_at, status) in rows:
        obj = M.Milestone.objects.filter(id=new_id('Milestone', old_id)).first()
        if obj:
            map_mil[old_id] = obj.id
            continue
        obj = M.Milestone(
            id=new_id('Milestone', old_id),
            name=name,
            completed=completed or False,
            order=order,
            project_id=map_proj[project_id],
            manual_progress=manual_progress,
            need=need or '',
            assigned_by_id=assigned_by_id,
            due_date=due_date,
            completed_at=completed_at,
            status=status,
        )
        obj.save()
        map_mil[old_id] = obj.id
        created += 1
    print(f"    créés : {created} / {len(rows)}")
    return map_mil


def copy_submilestones(map_mil):
    print("  SubMilestone ...")
    map_submil = {}
    rows = execute(cur,
                   "SELECT id, name, completed, \"order\", created_at, milestone_id, need, assigned_by_id, "
                   "due_date, completed_at "
                   "FROM core_submilestone ORDER BY id")
    created = 0
    for (old_id, name, completed, order, created_at, milestone_id, need,
         assigned_by_id, due_date, completed_at) in rows:
        obj = M.SubMilestone.objects.filter(id=new_id('SubMilestone', old_id)).first()
        if obj:
            map_submil[old_id] = obj.id
            continue
        obj = M.SubMilestone(
            id=new_id('SubMilestone', old_id),
            name=name,
            completed=completed or False,
            order=order,
            created_at=created_at,
            milestone_id=map_mil[milestone_id],
            need=need or '',
            assigned_by_id=assigned_by_id,
            due_date=due_date,
            completed_at=completed_at,
        )
        obj.save()
        map_submil[old_id] = obj.id
        created += 1
    print(f"    créés : {created} / {len(rows)}")
    return map_submil


def copy_project_children(map_proj):
    print("  ProjectNeed / Comment / Activity ...")
    rows = execute(cur,
                   "SELECT id, title, description, priority, created_by, created_at, project_id, "
                   "resolved_at, resolved_by, status FROM core_projectneed ORDER BY id")
    created = 0
    for (old_id, title, description, priority, created_by, created_at, project_id,
         resolved_at, resolved_by, status) in rows:
        if M.ProjectNeed.objects.filter(id=new_id('ProjectNeed', old_id)).exists():
            continue
        M.ProjectNeed.objects.create(
            id=new_id('ProjectNeed', old_id),
            title=title,
            description=description or '',
            priority=priority,
            created_by=created_by or '',
            created_at=created_at,
            project_id=map_proj[project_id],
            resolved_at=resolved_at,
            resolved_by=resolved_by or '',
            status=status,
        )
        created += 1
    print(f"  ProjectNeed créés : {created} / {len(rows)}")

    rows = execute(cur,
                   "SELECT id, message, created_by, created_at, project_id FROM core_projectcomment ORDER BY id")
    created = 0
    for (old_id, message, created_by, created_at, project_id) in rows:
        if M.ProjectComment.objects.filter(id=new_id('ProjectComment', old_id)).exists():
            continue
        M.ProjectComment.objects.create(
            id=new_id('ProjectComment', old_id),
            message=message,
            created_by=created_by or '',
            created_at=created_at,
            project_id=map_proj[project_id],
        )
        created += 1
    print(f"  ProjectComment créés : {created} / {len(rows)}")

    rows = execute(cur,
                   "SELECT id, action, description, user, created_at, project_id, description_context "
                   "FROM core_projectactivity ORDER BY id")
    created = 0
    for (old_id, action, description, user, created_at, project_id, description_context) in rows:
        if M.ProjectActivity.objects.filter(id=new_id('ProjectActivity', old_id)).exists():
            continue
        M.ProjectActivity.objects.create(
            id=new_id('ProjectActivity', old_id),
            action=action,
            description=description or '',
            user=user or '',
            created_at=created_at,
            project_id=map_proj[project_id],
            description_context=description_context or {},
        )
        created += 1
    print(f"  ProjectActivity créés : {created} / {len(rows)}")


def copy_folders_documents(map_proj):
    print("  ProjectFolder ...")
    map_folder = {}
    rows = execute(cur,
                   "SELECT id, name, created_at, parent_id, project_id FROM core_projectfolder ORDER BY id")
    created = 0
    # deux passes car parent
    for (old_id, name, created_at, parent_id, project_id) in rows:
        if M.ProjectFolder.objects.filter(id=new_id('ProjectFolder', old_id)).exists():
            map_folder[old_id] = M.ProjectFolder.objects.get(id=new_id('ProjectFolder', old_id)).id
            continue
        M.ProjectFolder.objects.create(
            id=new_id('ProjectFolder', old_id),
            name=name,
            created_at=created_at,
            parent_id=None,  # resolv après
            project_id=map_proj[project_id],
        )
        map_folder[old_id] = new_id('ProjectFolder', old_id)
        created += 1
    for (old_id, name, created_at, parent_id, project_id) in rows:
        if parent_id:
            M.ProjectFolder.objects.filter(id=new_id('ProjectFolder', old_id)).update(
                parent_id=map_folder[parent_id])
    print(f"    créés : {created} / {len(rows)}")

    print("  ProjectDocument ...")
    rows = execute(cur,
                   "SELECT id, title, description, file, uploaded_by, uploaded_at, project_id, folder_id "
                   "FROM core_projectdocument ORDER BY id")
    created = 0
    for (old_id, title, description, file, uploaded_by, uploaded_at, project_id, folder_id) in rows:
        if M.ProjectDocument.objects.filter(id=new_id('ProjectDocument', old_id)).exists():
            continue
        M.ProjectDocument.objects.create(
            id=new_id('ProjectDocument', old_id),
            title=title,
            description=description or '',
            file=file or '',
            uploaded_by=uploaded_by or '',
            uploaded_at=uploaded_at,
            project_id=map_proj[project_id],
            folder_id=map_folder.get(folder_id),
        )
        created += 1
    print(f"    créés : {created} / {len(rows)}")
    return map_folder


def copy_documents():
    print("  Document ...")
    rows = execute(cur,
                   "SELECT id, title, doc_type, status, priority, created_by, created_at, due_date, "
                   "signed_at, file, direction_id FROM core_document ORDER BY id")
    created = 0
    for (old_id, title, doc_type, status, priority, created_by, created_at, due_date,
         signed_at, file, direction_id) in rows:
        if M.Document.objects.filter(id=new_id('Document', old_id)).exists():
            continue
        M.Document.objects.create(
            id=new_id('Document', old_id),
            title=title,
            doc_type=doc_type,
            status=status,
            priority=priority,
            created_by=created_by or '',
            created_at=created_at,
            due_date=due_date,
            signed_at=signed_at,
            file=file or '',
            direction_id=dir_map[direction_id][1] if direction_id else None,
        )
        created += 1
    print(f"    créés : {created} / {len(rows)}")


def copy_project_members(map_proj, map_emp):
    print("  ProjectMember ...")
    rows = execute(cur,
                   "SELECT id, joined_at, employee_id, project_id, project_role_id "
                   "FROM core_projectmember ORDER BY id")
    created = 0
    for (old_id, joined_at, employee_id, project_id, project_role_id) in rows:
        if M.ProjectMember.objects.filter(id=new_id('ProjectMember', old_id)).exists():
            continue
        M.ProjectMember.objects.create(
            id=new_id('ProjectMember', old_id),
            joined_at=joined_at,
            employee_id=map_emp[employee_id],
            project_id=map_proj[project_id],
            project_role_id=prole_map[project_role_id][1] if project_role_id else None,
        )
        created += 1
    print(f"    créés : {created} / {len(rows)}")


def copy_events(map_emp):
    print("  Event / EventMember ...")
    map_evt = {}
    rows = execute(cur,
                   "SELECT id, title, event_type, description, date, time, duration, location, "
                   "created_at, created_by_id, updated_at FROM core_event ORDER BY id")
    created = 0
    for (old_id, title, event_type, description, date, time, duration, location,
         created_at, created_by_id, updated_at) in rows:
        obj = M.Event.objects.filter(id=new_id('Event', old_id)).first()
        if obj:
            map_evt[old_id] = obj.id
            continue
        obj = M.Event.objects.create(
            id=new_id('Event', old_id),
            title=title,
            event_type=event_type,
            description=description or '',
            date=date,
            time=time,
            duration=duration,
            location=location or '',
            created_at=created_at,
            created_by_id=created_by_id,
            updated_at=updated_at,
        )
        map_evt[old_id] = obj.id
        created += 1
    print(f"    créés : {created} / {len(rows)}")

    print("  EventMember ...")
    erows = execute(cur,
                    "SELECT id, status, invited_at, responded_at, note, employee_id, event_id "
                    "FROM core_eventmember ORDER BY id")
    created = 0
    for (old_id, status, invited_at, responded_at, note, employee_id, event_id) in erows:
        if M.EventMember.objects.filter(id=new_id('EventMember', old_id)).exists():
            continue
        M.EventMember.objects.create(
            id=new_id('EventMember', old_id),
            status=status,
            invited_at=invited_at,
            responded_at=responded_at,
            note=note or '',
            employee_id=map_emp[employee_id],
            event_id=map_evt[event_id],
        )
        created += 1
    print(f"    créés : {created} / {len(erows)}")
    return map_evt


def copy_leave(map_emp):
    print("  LeaveRequest / LeaveDocument ...")
    map_leave = {}
    rows = execute(cur,
                   "SELECT id, leave_type, start_date, end_date, days_count, reason, replacement, handover_note, "
                   "justification, status, manager_decision, manager_comment, manager_decision_at, "
                   "hr_decision, hr_comment, hr_decision_at, final_decision, final_comment, final_decision_at, "
                   "created_at, updated_at, direction_id, employee_id, final_user_id, hr_user_id, "
                   "manager_user_id, user_id "
                   "FROM core_leaverequest ORDER BY id")
    created = 0
    for (old_id, leave_type, start_date, end_date, days_count, reason, replacement, handover_note,
         justification, status, manager_decision, manager_comment, manager_decision_at,
         hr_decision, hr_comment, hr_decision_at, final_decision, final_comment, final_decision_at,
         created_at, updated_at, direction_id, employee_id, final_user_id, hr_user_id,
         manager_user_id, user_id) in rows:
        obj = M.LeaveRequest.objects.filter(id=new_id('LeaveRequest', old_id)).first()
        if obj:
            map_leave[old_id] = obj.id
            continue
        obj = M.LeaveRequest.objects.create(
            id=new_id('LeaveRequest', old_id),
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            days_count=days_count,
            reason=reason or '',
            replacement=replacement or '',
            handover_note=handover_note or '',
            justification=justification or '',
            status=status,
            manager_decision=manager_decision,
            manager_comment=manager_comment or '',
            manager_decision_at=manager_decision_at,
            hr_decision=hr_decision,
            hr_comment=hr_comment or '',
            hr_decision_at=hr_decision_at,
            final_decision=final_decision,
            final_comment=final_comment or '',
            final_decision_at=final_decision_at,
            created_at=created_at,
            updated_at=updated_at,
            direction_id=dir_map[direction_id][1] if direction_id else None,
            employee_id=map_emp[employee_id],
            final_user_id=final_user_id,
            hr_user_id=hr_user_id,
            manager_user_id=manager_user_id,
            user_id=user_id,
        )
        map_leave[old_id] = obj.id
        created += 1
    print(f"    créés : {created} / {len(rows)}")

    print("  LeaveDocument ...")
    drows = execute(cur,
                    "SELECT id, file, label, uploaded_at, leave_request_id FROM core_leavedocument ORDER BY id")
    created = 0
    for (old_id, file, label, uploaded_at, leave_request_id) in drows:
        if M.LeaveDocument.objects.filter(id=new_id('LeaveDocument', old_id)).exists():
            continue
        M.LeaveDocument.objects.create(
            id=new_id('LeaveDocument', old_id),
            file=file or '',
            label=label or '',
            uploaded_at=uploaded_at,
            leave_request_id=map_leave[leave_request_id],
        )
        created += 1
    print(f"    créés : {created} / {len(drows)}")


def copy_user_activity():
    print("  UserActivity ...")
    rows = execute(cur,
                   "SELECT id, action, description, ip_address, user_agent, created_at, user_id, "
                   "description_context FROM core_useractivity ORDER BY id")
    created = 0
    for (old_id, action, description, ip_address, user_agent, created_at, user_id,
         description_context) in rows:
        if M.UserActivity.objects.filter(id=new_id('UserActivity', old_id)).exists():
            continue
        M.UserActivity.objects.create(
            id=new_id('UserActivity', old_id),
            action=action,
            description=description or '',
            ip_address=str(ip_address) if ip_address else '',
            user_agent=user_agent or '',
            created_at=created_at,
            user_id=user_id,
            description_context=description_context or {},
        )
        created += 1
    print(f"    créés : {created} / {len(rows)}")


def copy_m2m(role_map, prole_map, map_emp, map_mil, map_submil, map_evt, dir_map):
    print("  M2M ...")
    # role_permissions
    rows = execute(cur, "SELECT role_id, permission_id FROM core_role_permissions")
    n = 0
    for role_id, permission_id in rows:
        role = M.Role.objects.get(pk=role_map[role_id][1]).permissions
        perm = M.Permission.objects.get(pk=perm_map[permission_id][1])
        if not role.filter(pk=perm.pk).exists():
            role.add(perm)
            n += 1
    print(f"    role_permissions ajoutées : {n}")

    rows = execute(cur, "SELECT projectrole_id, permission_id FROM core_projectrole_permissions")
    n = 0
    for prole_id, permission_id in rows:
        prole = M.ProjectRole.objects.get(pk=prole_map[prole_id][1]).permissions
        perm = M.Permission.objects.get(pk=perm_map[permission_id][1])
        if not prole.filter(pk=perm.pk).exists():
            prole.add(perm)
            n += 1
    print(f"    projectrole_permissions ajoutées : {n}")

    # assigned_to milestones
    try:
        rows = execute(cur, "SELECT milestone_id, employee_id FROM core_milestone_assigned_to")
        n = 0
        for milestone_id, employee_id in rows:
            m = M.Milestone.objects.get(pk=map_mil[milestone_id])
            emp = M.Employee.objects.get(pk=map_emp[employee_id])
            if not m.assigned_to.filter(pk=emp.pk).exists():
                m.assigned_to.add(emp)
                n += 1
        print(f"    milestone assigned_to ajoutés : {n}")
    except Exception as e:
        print(f"    milestone assigned_to : SKIP ({e})")

    try:
        rows = execute(cur, "SELECT submilestone_id, employee_id FROM core_submilestone_assigned_to")
        n = 0
        for submilestone_id, employee_id in rows:
            s = M.SubMilestone.objects.get(pk=map_submil[submilestone_id])
            emp = M.Employee.objects.get(pk=map_emp[employee_id])
            if not s.assigned_to.filter(pk=emp.pk).exists():
                s.assigned_to.add(emp)
                n += 1
        print(f"    submilestone assigned_to ajoutés : {n}")
    except Exception as e:
        print(f"    submilestone assigned_to : SKIP ({e})")

    # event participants (M2M Event -> Direction)
    try:
        rows = execute(cur, "SELECT event_id, direction_id FROM core_event_participants")
        n = 0
        for event_id, direction_id in rows:
            ev = M.Event.objects.get(pk=map_evt[event_id])
            dr = M.Direction.objects.get(pk=dir_map[direction_id][1])
            if not ev.participants.filter(pk=dr.pk).exists():
                ev.participants.add(dr)
                n += 1
        print(f"    event participants ajoutés : {n}")
    except Exception as e:
        print(f"    event participants : SKIP ({e})")


map_emp = copy_employee()
map_part = copy_partner()
map_proj = copy_project(map_emp)
map_usr = copy_userprofile(map_emp)
map_mil = copy_milestones(map_proj)
map_submil = copy_submilestones(map_mil)
copy_project_children(map_proj)
map_folder = copy_folders_documents(map_proj)
copy_documents()
copy_project_members(map_proj, map_emp)
map_evt = copy_events(map_emp)
copy_leave(map_emp)
copy_user_activity()
copy_m2m(role_map, prole_map, map_emp, map_mil, map_submil, map_evt, dir_map)

# Budget / Request / Notification : tables vides dans l'ancienne base, ne pas traiter.

print("\n=== Terminé ===")
old.close()