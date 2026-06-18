"""
Extraction des strings i18n depuis les templates Django et les fichiers Python.
Compare avec le .po existant et génère un rapport des nouvelles strings.
Usage: python scripts/extract_messages.py [--update]
"""
import re, os, sys, datetime

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDATE = '--update' in sys.argv

# ─── extraction depuis les templates  ────────────────────────────────
def extract_from_templates():
    strings = set()
    tpl_dir = os.path.join(ROOT, 'templates')
    pat_trans = re.compile(r'\{%\s*trans\s+"([^"]+)"\s*%\}|\{%\s*trans\s+\'([^\']+)\'\s*%\}')
    pat_btrans = re.compile(r'\{%\s*blocktrans[^%]*%\}(.*?)\{%\s*endblocktrans\s*%\}', re.DOTALL)
    pat_plural = re.compile(r'\{%\s*plural\s*%\}')

    for dirpath, _, files in os.walk(tpl_dir):
        for fname in files:
            if not fname.endswith('.html'):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, encoding='utf-8', errors='replace') as f:
                src = f.read()

            for m in pat_trans.finditer(src):
                s = m.group(1) or m.group(2)
                strings.add(s.strip())

            for m in pat_btrans.finditer(src):
                body = m.group(1)
                parts = pat_plural.split(body, 1)
                singular = re.sub(r'\{[{%].*?[}%]\}', '%s', parts[0]).strip()
                if singular:
                    strings.add(singular)

    return strings


# ─── extraction depuis les fichiers Python  ──────────────────────────
def extract_from_python():
    strings = set()
    py_dirs = [os.path.join(ROOT, 'core'), os.path.join(ROOT, 'dashboard_csig')]
    pat = re.compile(r'_\(\s*["\']([^"\']+)["\']\s*\)')

    for d in py_dirs:
        for dirpath, _, files in os.walk(d):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                fpath = os.path.join(dirpath, fname)
                with open(fpath, encoding='utf-8', errors='replace') as f:
                    src = f.read()
                for m in pat.finditer(src):
                    strings.add(m.group(1).strip())

    return strings


# ─── lire le .po existant  ───────────────────────────────────────────
def load_po(path):
    import polib
    if not os.path.exists(path):
        return polib.POFile(), set()
    po = polib.pofile(path, encoding='utf-8')
    ids = {e.msgid for e in po}
    return po, ids


# ─── TRANSLATIONS ANGLAISES CONNUES  ─────────────────────────────────
# Table de traduction pour les nouvelles strings issues des choices/views
KNOWN_EN = {
    # Choices Project
    'Planifié': 'Planned',
    'En cours': 'In progress',
    'Suspendu': 'Suspended',
    'Terminé': 'Completed',
    'En retard': 'Overdue',
    'Basse': 'Low',
    'Moyenne': 'Medium',
    'Haute': 'High',
    # Choices Milestone
    'À faire': 'To do',
    'Bloqué': 'Blocked',
    'En révision': 'In review',
    # Choices Document
    'Contrat': 'Contract',
    'Budget': 'Budget',
    'Rapport': 'Report',
    'Note': 'Note',
    'À signer': 'To sign',
    'À valider': 'To validate',
    'Signé': 'Signed',
    # Choices Partner
    'Entreprise': 'Company',
    'Université': 'University',
    'Institution': 'Institution',
    'ONG': 'NGO',
    'Actif': 'Active',
    'En discussion': 'In discussion',
    'Inactif': 'Inactive',
    # Choices Event
    'Réunion': 'Meeting',
    'Événement': 'Event',
    'Deadline': 'Deadline',
    # Choices Request
    'En attente': 'Pending',
    'Approuvé': 'Approved',
    'Rejeté': 'Rejected',
    # Choices LeaveRequest types
    'Congé annuel': 'Annual leave',
    'Congé maladie': 'Sick leave',
    'Congé maternité / paternité': 'Maternity / paternity leave',
    'Permission exceptionnelle': 'Exceptional leave',
    'Congé sans solde': 'Unpaid leave',
    'Formation / Mission': 'Training / Mission',
    # LeaveRequest status
    'Soumise - en attente avis hiérarchique': 'Submitted - awaiting manager review',
    'Avis hiérarchique favorable - en attente RH': 'Manager approved - awaiting HR',
    'Avis hiérarchique défavorable': 'Manager disapproved',
    'Vérifiée RH - en attente décision finale': 'HR verified - awaiting final decision',
    'Non conforme RH': 'HR non-compliant',
    'Approuvée': 'Approved',
    'Rejetée': 'Rejected',
    'Annulée par le demandeur': 'Cancelled by requester',
    # LeaveRequest decisions
    'Favorable': 'Favorable',
    'Défavorable': 'Unfavorable',
    'Conforme': 'Compliant',
    'Non conforme': 'Non-compliant',
    # Choices ProjectNeed status
    'Ouvert': 'Open',
    'Résolu': 'Resolved',
    # ProjectActivity choices
    'Création': 'Creation',
    'Modification': 'Modification',
    'Suppression': 'Deletion',
    'Ajout de membre': 'Member added',
    'Retrait de membre': 'Member removed',
    'Ajout de jalon': 'Milestone added',
    'Modification de jalon': 'Milestone modified',
    'Suppression de jalon': 'Milestone deleted',
    'Ajout de sous-étape': 'Sub-step added',
    'Modification de sous-étape': 'Sub-step modified',
    'Suppression de sous-étape': 'Sub-step deleted',
    'Changement statut jalon': 'Milestone status changed',
    'Modification statut jalon': 'Milestone status modified',
    'Changement statut sous-étape': 'Sub-step status changed',
    'Ajout de document': 'Document added',
    'Suppression de document': 'Document deleted',
    'Ajout de dossier': 'Folder added',
    'Suppression de dossier': 'Folder deleted',
    'Ajout de besoin': 'Need added',
    'Ajout de commentaire': 'Comment added',
    'Changement de statut': 'Status changed',
    'Changement de progression': 'Progress changed',
    # UserActivity choices
    'Connexion': 'Login',
    'Déconnexion': 'Logout',
    'Consultation': 'View',
    # Permission choices
    'Lire': 'Read',
    'Créer': 'Create',
    'Modifier': 'Edit',
    'Supprimer': 'Delete',
    'Gérer (tout)': 'Manage (all)',
    'Approuver': 'Approve',
    'Exporter': 'Export',
    'Tout': 'All',
    'Projets': 'Projects',
    'Jalons / Tâches': 'Milestones / Tasks',
    'Commentaires projet': 'Project comments',
    'Membres de projet': 'Project members',
    'Budgets': 'Budgets',
    'Utilisateurs': 'Users',
    'Employés': 'Employees',
    'Demandes de congé': 'Leave requests',
    'Partenaires': 'Partners',
    'Documents': 'Documents',
    'Demandes / Besoins projet': 'Requests / Project needs',
    'Événements': 'Events',
    'Directions': 'Departments',
    'Rôles': 'Roles',
    'Rapports': 'Reports',
    'Aucune (accès global)': 'None (global access)',
    'Même direction': 'Same department',
    'Est manager du projet': 'Is project manager',
    'Est membre du projet': 'Is project member',
    'Est propriétaire': 'Is owner',
    'Pipeline RH (après avis hiérarchique)': 'HR pipeline (after manager review)',
    # verbose_name strings
    'Action': 'Action',
    'Sujet': 'Subject',
    'Condition': 'Condition',
    'Description': 'Description',
    'Permission': 'Permission',
    'Permissions': 'Permissions',
    'Nom': 'Name',
    'Identifiant': 'Identifier',
    'Identifiant (slug)': 'Identifier (slug)',
    'Permissions projet': 'Project permissions',
    "Rôle système (non supprimable)": 'System role (cannot be deleted)',
    'Rôle': 'Role',
    'Rôle projet': 'Project role',
    'Profil utilisateur': 'User profile',
    'Profils utilisateurs': 'User profiles',
    'Téléphone': 'Phone',
    'Photo': 'Photo',
    'Profil actif': 'Active profile',
    'Direction': 'Department',
    'Employé': 'Employee',
    'ID Employé': 'Employee ID',
    'Nom du projet': 'Project name',
    'Statut': 'Status',
    'Priorité': 'Priority',
    'Progression (%)': 'Progress (%)',
    'Budget alloué': 'Allocated budget',
    'Budget consommé': 'Consumed budget',
    'Devise': 'Currency',
    'Date de début': 'Start date',
    'Date de fin': 'End date',
    'Date de début originale': 'Original start date',
    'Date de fin originale': 'Original end date',
    'Responsable': 'Manager',
    'Responsable (lié)': 'Manager (linked)',
    'Projet': 'Project',
    'Projet': 'Project',
    'Membre de projet': 'Project member',
    'Membres de projet': 'Project members',
    'Date d\'ajout': 'Date added',
    'Nom du jalon': 'Milestone name',
    'Responsables': 'Managers',
    'Attribué par': 'Assigned by',
    'Date de la tâche': 'Task date',
    'Complété': 'Completed',
    'Terminé le': 'Completed on',
    'Besoin': 'Need',
    'Progression manuelle (%)': 'Manual progress (%)',
    'Ordre': 'Order',
    'Jalon': 'Milestone',
    'Jalons': 'Milestones',
    'Jalon parent': 'Parent milestone',
    'Nom de la sous-étape': 'Sub-step name',
    'Date de la sous-tâche': 'Sub-task date',
    'Complétée': 'Completed',
    'Terminée le': 'Completed on',
    'Sous-étape': 'Sub-step',
    'Sous-étapes': 'Sub-steps',
    'Titre': 'Title',
    'Créé par': 'Created by',
    'Traité par': 'Processed by',
    'Traité le': 'Processed on',
    'Besoin de projet': 'Project need',
    'Besoins de projet': 'Project needs',
    'Commentaire': 'Comment',
    'Commentaire de projet': 'Project comment',
    'Commentaires de projet': 'Project comments',
    'Activité de projet': 'Project activity',
    'Activités de projet': 'Project activities',
    'Utilisateur': 'User',
    'Nom du dossier': 'Folder name',
    'Dossier parent': 'Parent folder',
    'Dossier de projet': 'Project folder',
    'Dossiers de projet': 'Project folders',
    'Fichier': 'File',
    'Uploadé par': 'Uploaded by',
    'Document de projet': 'Project document',
    'Documents de projet': 'Project documents',
    'Type': 'Type',
    'Date de création': 'Creation date',
    'Date limite': 'Due date',
    'Date de signature': 'Signature date',
    'Document': 'Document',
    'Partenaire': 'Partner',
    'Personne de contact': 'Contact person',
    'Email': 'Email',
    'Logo': 'Logo',
    'Événement': 'Event',
    'Heure': 'Time',
    'Durée (minutes)': 'Duration (minutes)',
    'Lieu': 'Location',
    'Participants': 'Participants',
    'Créé le': 'Created on',
    'Modifié le': 'Modified on',
    'Demande': 'Request',
    'Demandes': 'Requests',
    'Date d\'approbation': 'Approval date',
    'Nom': 'Name',
    'Rôle / Fonction': 'Role / Function',
    'Charge de travail (%)': 'Workload (%)',
    'Compétences': 'Skills',
    'Personne externe': 'External person',
    'Organisation / Entreprise': 'Organization / Company',
    'Adresse IP': 'IP address',
    'Navigateur': 'Browser',
    'Date': 'Date',
    'Activité utilisateur': 'User activity',
    'Activités utilisateurs': 'User activities',
    'Demande de congé': 'Leave request',
    'Demandes de congé': 'Leave requests',
    'Type de congé': 'Leave type',
    'Nombre de jours': 'Number of days',
    'Motif': 'Reason',
    'Suppléant / agent intérimaire': 'Substitute / interim agent',
    'Note de passation': 'Handover note',
    'Justificatif': 'Justification',
    'Avis hiérarchique': 'Manager review',
    'Observations hiérarchie': 'Manager comments',
    'Validé par (hiérarchie)': 'Validated by (manager)',
    'Date avis hiérarchique': 'Manager review date',
    'Vérification RH': 'HR verification',
    'Observations RH': 'HR comments',
    'Vérifié par (RH)': 'Verified by (HR)',
    'Date vérification RH': 'HR verification date',
    'Décision finale': 'Final decision',
    'Observations Direction': 'Management comments',
    'Décidé par (Direction)': 'Decided by (Management)',
    'Date décision finale': 'Final decision date',
    'Soumise le': 'Submitted on',
    'Document de congé': 'Leave document',
    'Documents de congé': 'Leave documents',
    'Libellé': 'Label',
    'Direction / Service': 'Department / Service',
    # Modal i18n
    'Confirmation': 'Confirmation',
    'Confirmer la suppression': 'Confirm deletion',
    'Voulez-vous supprimer': 'Do you want to delete',
    'Cette action est irréversible.': 'This action is irreversible.',
    'Supprimer': 'Delete',
    'Confirmer': 'Confirm',
    'Tapez': 'Type',
    'pour confirmer': 'to confirm',
    'Le nom ne correspond pas exactement.': 'The name does not match exactly.',
    # Role templates
    'Rôles & Permissions': 'Roles & Permissions',
    'Gérer les rôles globaux et leurs permissions': 'Manage global roles and their permissions',
    'Rôles globaux': 'Global roles',
    'Rôles projet': 'Project roles',
    'Nouveau rôle': 'New role',
    'Système': 'System',
    'Voir le détail': 'View details',
    'Dupliquer': 'Duplicate',
    'le rôle': 'the role',
    'Aucun rôle défini.': 'No role defined.',
    'Créer le premier rôle': 'Create the first role',
    'Rôle': 'Role',
    'Tout (super-admin)': 'All (super-admin)',
    'Permissions accordées': 'Granted permissions',
    'Informations': 'Information',
    'Rôle système': 'System role',
    'Rôle personnalisé': 'Custom role',
    'Assigné à': 'Assigned to',
    'Modifier les permissions': 'Edit permissions',
    'Dupliquer ce rôle': 'Duplicate this role',
    'Définir les permissions associées à ce rôle': 'Define permissions for this role',
    'Informations du rôle': 'Role information',
    'Ex: Chef de projet externe': 'Ex: External project manager',
    'ex: chef-projet-externe': 'ex: external-project-manager',
    'Lettres minuscules, chiffres et tirets. Non modifiable après création.': 'Lowercase letters, numbers and hyphens. Cannot be changed after creation.',
    'Décrivez le rôle et son périmètre...': 'Describe the role and its scope...',
    'Tout cocher': 'Check all',
    'Tout effacer': 'Clear all',
    'Tout module': 'Entire module',
    'Aucune permission définie dans le système.': 'No permissions defined in the system.',
    'Récapitulatif': 'Summary',
    'permissions sélectionnées': 'permissions selected',
    'À savoir': 'Good to know',
    '<strong>Gérer (tout)</strong> inclut lire, créer, modifier et supprimer.': '<strong>Manage (all)</strong> includes read, create, edit and delete.',
    'Les conditions <em>restreignent</em> une permission à un sous-ensemble.': 'Conditions <em>restrict</em> a permission to a subset.',
    'Les rôles système ne peuvent pas être supprimés.': 'System roles cannot be deleted.',
    'Enregistrer': 'Save',
    'Créer le rôle': 'Create role',
    'Annuler': 'Cancel',
    'Permissions attribuées dans le contexte d\'un projet': 'Permissions assigned in the context of a project',
    'Nouveau rôle projet': 'New project role',
    'Aucun rôle projet défini.': 'No project role defined.',
    'Créer le premier rôle projet': 'Create the first project role',
    'Supprimer le rôle': 'Delete role',
    'Supprimer un rôle': 'Delete a role',
    'Cette action est irréversible': 'This action is irreversible',
    'Ce rôle sera supprimé <strong>définitivement</strong>.': 'This role will be <strong>permanently</strong> deleted.',
    'Les utilisateurs qui l\'ont seront sans rôle.': 'Users assigned to it will have no role.',
    'Utilisateurs assignés': 'Assigned users',
    'Supprimer définitivement': 'Delete permanently',
    # common
    'Retour': 'Back',
    'autres': 'more',
    'Aucune permission': 'No permissions',
    'Détail du rôle et des permissions associées': 'Role details and associated permissions',
    # Profile
    'Mon profil': 'My profile',
    'Gérez vos informations personnelles et vos accès': 'Manage your personal information and access',
    'Compte actif': 'Active account',
    'Compte inactif': 'Inactive account',
    'Informations personnelles': 'Personal information',
    'Adresse email': 'Email address',
    "Cet email est utilisé pour recevoir les notifications et les liens d'invitation.": "This email is used to receive notifications and invitation links.",
    'Optionnel.': 'Optional.',
    'Enregistrer les modifications': 'Save changes',
    # my_tasks
    '%s tâche': '%s task',
    '%s tâches': '%s tasks',
    '%s terminée': '%s completed',
    '%s terminées': '%s completed',
    # confirm_delete dependencies
    'Dépendances détectées :': 'Dependencies detected:',
    "A un compte utilisateur — le lien sera retiré (le compte reste)": "Has a user account — the link will be removed (the account stays)",
    'Chef de projet sur %s projet :': 'Project manager for %s project:',
    'Chef de projet sur %s projets :': 'Project manager for %s projects:',
    'le lien responsable sera effacé': 'the manager link will be removed',
    'Membre de %s projet — les appartenances seront supprimées': 'Member of %s project — memberships will be deleted',
    'Membre de %s projets — les appartenances seront supprimées': 'Member of %s projects — memberships will be deleted',
    '%s demande de congé liée — la suppression est bloquée': '%s leave request linked — deletion is blocked',
    '%s demandes de congé liées — la suppression est bloquée': '%s leave requests linked — deletion is blocked',
    # event_form Select2
    'Sélectionner des directions...': 'Select departments...',
    'Aucune direction trouvée': 'No department found',
    ' permission': ' permission',
    ' permissions': ' permissions',
    ' utilisateur': ' user',
    ' utilisateurs': ' users',
    ' membre': ' member',
    ' membres': ' members',
}


def main():
    import polib

    tpl_strings = extract_from_templates()
    py_strings  = extract_from_python()
    all_strings = tpl_strings | py_strings

    po_path = os.path.join(ROOT, 'locale', 'en', 'LC_MESSAGES', 'django.po')
    po, existing_ids = load_po(po_path)

    new_strings = all_strings - existing_ids
    print(f'Total strings extracted: {len(all_strings)}')
    print(f'Already in .po: {len(existing_ids)}')
    print(f'New strings: {len(new_strings)}')

    if not new_strings:
        print('Nothing to add.')
        return

    translated = {s: KNOWN_EN[s] for s in new_strings if s in KNOWN_EN}
    untranslated = new_strings - set(KNOWN_EN.keys())

    print(f'  With known translation: {len(translated)}')
    print(f'  Need manual translation: {len(untranslated)}')

    if untranslated:
        print('\n=== Strings needing manual EN translation ===')
        for s in sorted(untranslated)[:40]:
            print(f'  {repr(s)}')
        if len(untranslated) > 40:
            print(f'  ... and {len(untranslated)-40} more')

    if UPDATE:
        for fr, en in translated.items():
            e = polib.POEntry(msgid=fr, msgstr=en)
            po.append(e)
        # Add untranslated as empty
        for fr in untranslated:
            e = polib.POEntry(msgid=fr, msgstr='')
            po.append(e)
        po.save(po_path)
        # Compile
        mo_path = po_path.replace('.po', '.mo')
        po.save_as_mofile(mo_path)
        print(f'\nUpdated {po_path}')
        print(f'Compiled {mo_path}')
    else:
        print('\nRun with --update to apply changes.')


if __name__ == '__main__':
    main()
