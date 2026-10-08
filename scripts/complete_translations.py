"""
Complete all missing EN translations in locale/en/LC_MESSAGES/django.po
Run: python scripts/complete_translations.py
"""
import sys, os, polib
sys.stdout.reconfigure(encoding='utf-8')

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PO     = os.path.join(ROOT, 'locale', 'en', 'LC_MESSAGES', 'django.po')
MO     = PO.replace('.po', '.mo')

TRANSLATIONS = {
    # ── Plurals / internal ──────────────────────────────────────────────
    '%s utilisateur':                               '%s user',
    '%s utilisateurs':                              '%s users',
    '<strong>%s</strong> utilisateur aura ces permissions.':
                                                    '<strong>%s</strong> user will have these permissions.',
    '<strong>%s</strong> utilisateurs auront ces permissions.':
                                                    '<strong>%s</strong> users will have these permissions.',
    'Supprimer « %s » ?':                           'Delete « %s »?',

    # ── Slugs / model internal values ───────────────────────────────────
    'all':          'all',
    'en_cours':     'in_progress',
    'manage':       'manage',
    'membre':       'member',
    'projet':       'project',
    'rôle':         'role',
    'tâche':        'task',
    'terminée':     'completed',
    'utilisateur':  'user',
    'voir':         'view',
    'si aucune sous-étape': 'if no sub-step',
    'optionnel':    'optional',
    'par':          'by',
    'permission':   'permission',
    'jour(s)':      'day(s)',

    # ── Technical model names ────────────────────────────────────────────
    'Comment':          'Comment',
    'Event':            'Event',
    'LeaveRequest':     'LeaveRequest',
    'Milestone':        'Milestone',
    'Partner':          'Partner',
    'Project':          'Project',
    'ProjectMember':    'ProjectMember',
    'Report':           'Report',
    'Request':          'Request',
    'User':             'User',

    # ── Leave workflow ───────────────────────────────────────────────────
    '48h hiérarchie, 72h RH, 3j Direction.':
        '48h manager, 72h HR, 3d Management.',
    'Action requise : avis hiérarchique':
        'Action required: manager review',
    'Action requise : décision finale':
        'Action required: final decision',
    'Action requise : vérification RH':
        'Action required: HR verification',
    'Avis hiérarchique enregistré.':
        'Manager review recorded.',
    'Circuit de validation':
        'Approval workflow',
    'Continuité de service':
        'Service continuity',
    'Contrôlez la conformité réglementaire et les droits disponibles avant transmission à la Direction.':
        'Check regulatory compliance and available leave balance before forwarding to Management.',
    'Créer ma première demande':
        'Create my first request',
    'Décision Direction':
        'Management decision',
    'Décision Direction / Coordination':
        'Management / Coordination decision',
    'Décision finale enregistrée et notifiée.':
        'Final decision recorded and notified.',
    "Décision officielle de la Direction Générale / Coordination. Une notification sera envoyée automatiquement à l'agent et à la chaîne de validation.":
        'Official decision from General Management / Coordination. A notification will be sent automatically to the employee and the approval chain.',
    'Décrivez brièvement le motif de votre demande.':
        'Briefly describe the reason for your request.',
    'Délai de traitement':
        'Processing time',
    'Détail des étapes de validation':
        'Validation steps details',
    'Le détail des étapes de validation est confidentiel.':
        'The details of the validation steps are confidential.',
    'Demande annulée.':
        'Request cancelled.',
    'Demande créée avec succès.':
        'Request created successfully.',
    'Demande de congé soumise. Elle suit maintenant le circuit de validation.':
        'Leave request submitted. It is now following the approval workflow.',
    'Demande mise à jour.':
        'Request updated.',
    'Documents justificatifs':
        'Supporting documents',
    'Elle sera transmise immédiatement à votre hiérarchie pour validation.':
        'It will be forwarded immediately to your manager for approval.',
    'En cours de validation':
        'Under review',
    'Enregistrer la décision finale':
        'Save final decision',
    'Enregistrer mon avis':
        'Save my review',
    'Formulaire de demande - CSIG':
        'Request form - CSIG',
    'Gestion des congés':
        'Leave management',
    'Jours':
        'Days',
    'Maladie / maternité / formation':
        'Sick / maternity / training',
    'Mes demandes':
        'My requests',
    'Mes demandes de congé':
        'My leave requests',
    'Mes validations':
        'My reviews',
    'Mes vérifications':
        'My verifications',
    'Pensez à désigner un suppléant pour faciliter la continuité du service. Une note de passation bien rédigée accélère la validation.':
        'Remember to designate a substitute to ensure service continuity. A well-written handover note speeds up validation.',
    'Pièce jointe supprimée.':
        'Attachment deleted.',
    'Pièces déjà jointes':
        'Already attached documents',
    'Pièces jointes':
        'Attachments',
    "Pièces à fournir selon le type de congé":
        'Documents required by leave type',
    'Prêt à soumettre votre demande ?':
        'Ready to submit your request?',
    'Remplacement et passation des dossiers':
        'Replacement and file handover',
    'Remplissez ce formulaire pour soumettre votre demande. Elle suivra le circuit officiel : Hiérarchie → RH → Direction.':
        'Fill in this form to submit your request. It will follow the official workflow: Manager → HR → Management.',
    'Refusées':
        'Refused',
    'Suivez vos demandes en temps réel et soumettez-en de nouvelles en quelques clics.':
        'Track your requests in real time and submit new ones in a few clicks.',
    'Suppléant':
        'Substitute',
    'Type de congé, dates et motif':
        'Leave type, dates and reason',
    'Valider':
        'Validate',
    'Valider la vérification RH':
        'Validate HR verification',
    'Vérification RH enregistrée.':
        'HR verification recorded.',
    'Workflow CSIG : Employé → Hiérarchie → RH → Direction':
        'CSIG workflow: Employee → Manager → HR → Management',
    'Vous serez notifié par email à chaque étape.':
        'You will be notified by email at each step.',
    'Détails du congé':
        'Leave details',
    'Détails de la demande':
        'Request details',
    'Annuler ma demande':
        'Cancel my request',
    'Certificat médical, acte de naissance, convocation, ordre de mission… (PDF, image, Word)':
        'Medical certificate, birth certificate, summons, mission order… (PDF, image, Word)',
    'à demander au moins 15 jours avant le départ.':
        'must be requested at least 15 days before departure.',
    'Personne désignée pour assurer la continuité du service pendant votre absence.':
        'Person designated to ensure service continuity during your absence.',
    'Évaluez l\'impact de cette absence sur le fonctionnement du service avant de transmettre à la RH.':
        "Evaluate the impact of this absence on the service's functioning before forwarding to HR.",
    'Étape 1/3':    'Step 1/3',
    'Étape 2/3':    'Step 2/3',
    'Étape 3/3':    'Step 3/3',
    'Étape':        'Step',

    # ── Project ──────────────────────────────────────────────────────────
    'Ajouter des jalons':               'Add milestones',
    'Assigner à un membre':             'Assign to a member',
    'Ce jalon contient des sous-étapes : sa progression est calculée automatiquement.':
        'This milestone contains sub-steps: its progress is calculated automatically.',
    'Cette personne externe doit avoir un compte pour consulter le projet.':
        'This external person must have an account to view the project.',
    "L'employé sera rattaché à la direction du projet et stocké dans le système.":
        'The employee will be linked to the project department and stored in the system.',
    'Marquer comme complété':           'Mark as completed',
    'Marquer comme complétée':          'Mark as completed',
    'Marquer non terminé':              'Mark as not done',
    'Marquer terminé':                  'Mark as done',
    'Membre ajouté avec succès.':       'Member added successfully.',
    'Membre supprimé du projet.':       'Member removed from project.',
    'Membres du projet':                'Project members',
    'Modifier le projet':               'Edit project',
    'Jalon créé avec succès.':          'Milestone created successfully.',
    'Jalon modifié avec succès.':       'Milestone updated successfully.',
    'Jalon supprimé.':                  'Milestone deleted.',
    'Sous-étape ajoutée avec succès.':  'Sub-step added successfully.',
    'Sous-étape modifiée avec succès.': 'Sub-step updated successfully.',
    'Sous-étape supprimée.':            'Sub-step deleted.',
    'Projet créé avec succès.':         'Project created successfully.',
    'Projet modifié avec succès.':      'Project updated successfully.',
    'Projet supprimé.':                 'Project deleted.',
    'Seul le Directeur Général peut supprimer un projet.':
        'Only the General Director can delete a project.',
    'Responsable du projet':            'Project manager',
    'Rôle du membre modifié avec succès.': 'Member role updated successfully.',
    'Rôle et direction':                'Role and department',
    'Rôle personnalisé — cochez les permissions souhaitées pour ce membre.':
        'Custom role — check the desired permissions for this member.',
    'Rôles disponibles':                'Available roles',
    'Rechercher un membre...':          'Search for a member...',
    'Personne externe au projet':       'External person on project',
    'Informations de la sous-étape':    'Sub-step information',
    'Gérer les membres':                'Manage members',
    'Type de membre':                   'Member type',
    'Permissions du rôle':              'Role permissions',
    'Mes tâches':                       'My tasks',
    'Toutes les tâches qui vous sont assignées': 'All tasks assigned to you',
    'Dossier créé avec succès.':        'Folder created successfully.',
    'Dossier modifié avec succès.':     'Folder updated successfully.',
    'Dossier supprimé.':                'Folder deleted.',
    'Avancement':                       'Progress',

    # ── Documents ────────────────────────────────────────────────────────
    'Document ajouté avec succès.':     'Document added successfully.',
    'Document créé avec succès.':       'Document created successfully.',
    'Document modifié avec succès.':    'Document updated successfully.',
    'Document supprimé.':               'Document deleted.',
    'Fichier actuel':                   'Current file',
    'Fichier introuvable.':             'File not found.',
    'Fichier non trouvé.':              'File not found.',
    'Aucun fichier attaché à ce document.': 'No file attached to this document.',
    'Cliquez ou glissez un fichier':    'Click or drag a file',
    'Cliquez ou glissez une image':     'Click or drag an image',
    'Cliquez pour ajouter ou glissez vos fichiers': 'Click to add or drag your files',
    'Signer':                           'Sign',
    'Télécharger':                      'Download',
    'Fiche employé':                    'Employee file',

    # ── Employees ────────────────────────────────────────────────────────
    'Aucun employé disponible':         'No employee available',
    'Aucun employé lié':                'No linked employee',
    'Autres employés':                  'Other employees',
    'Consultant, partenaire…':          'Consultant, partner…',
    'Consultant, prestataire, partenaire — la fiche est créée et stockée avec le marqueur « Externe ».':
        'Consultant, contractor, partner — the record is created and stored with the "External" marker.',
    'Créer un compte de connexion pour cette personne': 'Create a login account for this person',
    'Créer un nouvel employé interne':  'Create a new internal employee',
    'Créer une fiche interne':          'Create an internal record',
    'Déjà dans le système':             'Already in the system',
    'Employé créé avec succès.':        'Employee created successfully.',
    'Employé modifié avec succès.':     'Employee updated successfully.',
    'Ex : Amadou Diallo':               'Ex: Amadou Diallo',
    'Ex : Cabinet XYZ, ONG Alpha…':     'Ex: Cabinet XYZ, NGO Alpha…',
    'Ex : Consultant senior, Expert technique…': 'Ex: Senior consultant, Technical expert…',
    'Ex : Ingénieur, Analyste, Chef de division…': 'Ex: Engineer, Analyst, Division head…',
    'Ex : Marie Konaté':                'Ex: Marie Konaté',
    'Ex : Rédiger le cahier des charges': 'Ex: Write the specifications',
    'Externe':                          'External',
    'Identité (depuis la fiche employé)': 'Identity (from employee record)',
    'Informations personnelles':        'Personal information',
    'Poste / Fonction':                 'Position / Function',
    'Sélectionner un employé existant': 'Select an existing employee',

    # ── Budget ───────────────────────────────────────────────────────────
    'Budget alloué (GNF)':              'Allocated budget (GNF)',
    'Budget créé avec succès.':         'Budget created successfully.',
    'Budget général':                   'General budget',
    'Budget modifié avec succès.':      'Budget updated successfully.',
    'Budget supprimé.':                 'Budget deleted.',
    'Budget total (GNF)':               'Total budget (GNF)',
    'Consommation par projet':          'Consumption by project',
    'Consommé (GNF)':                   'Consumed (GNF)',
    'Date du taux figé':                'Fixed rate date',
    'Devise préférée':                  'Preferred currency',
    'Disponible (GNF)':                 'Available (GNF)',
    'Détail des budgets par projet':    'Budget details by project',
    'Projet / Direction':               'Project / Department',
    'Répartition du budget par projet': 'Budget breakdown by project',
    'Sans affectation':                 'Unassigned',
    'Taux figé (GNF pour 1 USD)':       'Fixed rate (GNF per 1 USD)',
    'Total':                            'Total',
    'Valeur par défaut des formulaires de budget.':
                                        'Default value for budget forms.',

    # ── Partners ─────────────────────────────────────────────────────────
    'Partenaire créé avec succès.':     'Partner created successfully.',
    'Partenaire modifié avec succès.':  'Partner updated successfully.',
    'Partenaire supprimé.':             'Partner deleted.',
    'Partenariats':                     'Partnerships',

    # ── Events / Calendar ────────────────────────────────────────────────
    'Cet événement est passé.':         'This event is past.',
    'Événement créé avec succès.':      'Event created successfully.',
    'Événement modifié avec succès.':   'Event updated successfully.',
    'Événement supprimé.':              'Event deleted.',
    'Modifier cet événement':           'Edit this event',
    'Réunions':                         'Meetings',
    'Ce mois-ci':                       'This month',

    # ── Directions ───────────────────────────────────────────────────────
    'Direction créée avec succès.':     'Department created successfully.',
    'Direction modifiée avec succès.':  'Department updated successfully.',
    'Direction supprimée.':             'Department deleted.',
    'Aucune direction associée':        'No associated department',
    'Toutes directions':                'All departments',

    # ── Users / Auth ─────────────────────────────────────────────────────
    'Accès insuffisant pour consulter les rapports.': 'Insufficient access to view reports.',
    'Accès refusé.':                    'Access denied.',
    'Accès réservé aux directeurs et administrateurs.': 'Access restricted to directors and administrators.',
    'Ce compte est déjà activé. Connectez-vous normalement.': 'This account is already activated. Sign in normally.',
    'Cette section est réservée au Directeur Général.': 'This section is reserved for the General Director.',
    'Compte':                           'Account',
    'Créer un compte':                  'Create an account',
    'Erreurs':                          'Errors',
    'Identifiants incorrects.':         'Incorrect credentials.',
    'Identité (depuis la fiche employé)': 'Identity (from employee record)',
    'Mot de passe modifié avec succès.': 'Password changed successfully.',
    'Mot de passe réinitialisé. Vous pouvez vous connecter.': 'Password reset. You can now sign in.',
    'Permissions insuffisantes.':       'Insufficient permissions.',
    'Permission insuffisante pour créer des événements.': 'Insufficient permission to create events.',
    'Profil mis à jour avec succès.':   'Profile updated successfully.',
    'Votre compte a été désactivé. Contactez un administrateur.': 'Your account has been deactivated. Contact an administrator.',
    'Votre identité et votre direction de rattachement': 'Your identity and attached department',
    'Vous avez été déconnecté avec succès.': 'You have been logged out successfully.',
    'Vous ne pouvez gérer que les employés de votre direction.': 'You can only manage employees from your department.',
    'Vous ne pouvez modifier que vos propres événements.': 'You can only edit your own events.',
    'Vous ne pouvez pas désactiver votre propre compte.': 'You cannot deactivate your own account.',
    'Vous ne pouvez pas supprimer votre propre compte.': 'You cannot delete your own account.',
    'Vous ne pouvez supprimer que les employés de votre direction.': 'You can only delete employees from your department.',
    'Vous ne pouvez supprimer que vos propres événements.': 'You can only delete your own events.',
    'Un rôle avec cet identifiant existe déjà.': 'A role with this identifier already exists.',
    'Un rôle projet avec cet identifiant existe déjà.': 'A project role with this identifier already exists.',

    # ── Reports ──────────────────────────────────────────────────────────
    'Congés':                           'Leave',
    'Conseil':                          'Advisory',

    # ── Misc UI ──────────────────────────────────────────────────────────
    'Aucun élément ne correspond à cette vue pour le moment.': 'No items match this view for now.',
    'Aucune demande à afficher':        'No requests to display',
    'Besoin ajouté avec succès.':       'Need added successfully.',
    'Cette demande ne peut plus être modifiée.': 'This request can no longer be modified.',
    'Commentaire ajouté.':              'Comment added.',
    'Logo actuel':                      'Current logo',
    'Membre':                           'Member',
    'Période':                          'Period',
    'Soumise':                          'Submitted',
    'Statut actuel':                    'Current status',
    'Statut invalide.':                 'Invalid status.',
    'Suspendus':                        'Suspended',
    'Toutes':                           'All',

    # ── Language string ──────────────────────────────────────────────────
    'Français':                         'French',
    'Fran\\u00e7ais':                   'French',

    # ── i18n template context strings ───────────────────────────────────
    ' permission':                      ' permission',
    ' permissions':                     ' permissions',
    ' utilisateur':                     ' user',
    ' utilisateurs':                    ' users',
    ' membre':                          ' member',
    ' membres':                         ' members',

    # ── Error pages (400/403/404/500) ────────────────────────────────────
    'Accès refusé':                     'Access denied',
    'Erreur interne':                   'Internal error',
    'Erreur interne du serveur':        'Internal server error',
    'Page introuvable':                 'Page not found',
    'Requête invalide':                 'Invalid request',
    'Retour au tableau de bord':        'Back to dashboard',
    "La page demandée n'existe pas ou a été déplacée.":
        'The requested page does not exist or has been moved.',
    "La requête n'a pas pu être traitée. Vérifiez l'adresse saisie puis réessayez.":
        'The request could not be processed. Check the address you entered and try again.',
    "Une erreur est survenue de notre côté. L'incident a été enregistré, merci de réessayer plus tard.":
        "An error occurred on our side. The incident has been logged, please try again later.",
    "Vous n'avez pas les permissions nécessaires pour accéder à cette page.":
        "You don't have the required permissions to access this page.",

    # ── Requests / invitations ───────────────────────────────────────────
    'Code unique :':                    'Unique code:',
    "Renvoyer l'invitation à %s ?":     'Resend invitation to %s ?',
    "Renvoyer l'invitation à %(email)s ?": 'Resend invitation to %(email)s ?',
    'Supprimer « %(name)s » ?':         'Delete « %(name)s » ?',
    'Vous devez être rattaché(e) à un compte employé pour soumettre une demande.':
        'You must be linked to an employee account to submit a request.',
    'Vous ne pouvez pas statuer sur votre propre demande.':
        'You cannot decide on your own request.',
    'Vous ne pouvez statuer que sur les demandes de votre direction.':
        'You can only decide on requests from your department.',

    # ── Singular %s forms (legacy extraction of blocktrans count) ────────
    '%s besoin':                        '%s need',
    '%s commentaire':                   '%s comment',
    '%s document':                      '%s document',
    '%s dossier':                       '%s folder',
    '%s étape définie':                 '%s step defined',
    '%s membre':                        '%s member',
    '%s participant':                   '%s participant',
    '%s projet au total':               '%s project in total',
    '%s projet dans votre direction':   '%s project in your department',

    # ── Emails par destinataire : types de tâche et phrases ──────────────
    'jalon':            'milestone',
    'Langue des emails': 'Email language',
    "Pas d'email pour cet employé": 'No email for this employee',
    'Un nouveau jalon vous est attribué :':        'A new milestone has been assigned to you:',
    'Une nouvelle sous-étape vous est attribuée :': 'A new sub-step has been assigned to you:',
    'Une nouvelle tâche vous est attribuée :':      'A new task has been assigned to you:',
    'Une nouvelle %(type)s vous est attribuée :':   'A new %(type)s has been assigned to you:',
    'Un nouveau jalon a été attribué à %(name)s :':         'A new milestone has been assigned to %(name)s:',
    'Une nouvelle sous-étape a été attribuée à %(name)s :': 'A new sub-step has been assigned to %(name)s:',
    'Une nouvelle tâche a été attribuée à %(name)s :':      'A new task has been assigned to %(name)s:',
    'Une nouvelle %(type)s a été attribuée à %(name)s :':   'A new %(type)s has been assigned to %(name)s:',
    'Le jalon « %(name)s » est maintenant terminé.':     'Milestone “%(name)s” is now completed.',
    'La sous-étape « %(name)s » est maintenant terminée.': 'Sub-step “%(name)s” is now completed.',
    'La tâche « %(name)s » est maintenant terminée.':    'Task “%(name)s” is now completed.',
    'La %(type)s « %(name)s » est maintenant terminée.': 'The %(type)s “%(name)s” is now completed.',
    'Jalon terminé':        'Milestone completed',
    'Sous-étape terminée':  'Sub-step completed',
    'Tâche terminée':       'Task completed',
    '%(type)s terminée':    '%(type)s completed',
    '[CSIG] Jalon terminé : %(task)s':       '[CSIG] Milestone completed: %(task)s',
    '[CSIG] Sous-étape terminée : %(task)s': '[CSIG] Sub-step completed: %(task)s',
    '[CSIG] Tâche terminée : %(task)s':      '[CSIG] Task completed: %(task)s',
    '[CSIG] %(type)s terminée : %(task)s':   '[CSIG] %(type)s completed: %(task)s',
    "Le jalon ci-dessous (responsable : %(name)s) n'est pas encore terminé.":     'The milestone below (owner: %(name)s) is not yet completed.',
    "La sous-étape ci-dessous (responsable : %(name)s) n'est pas encore terminée.": 'The sub-step below (owner: %(name)s) is not yet completed.',
    "La tâche ci-dessous (responsable : %(name)s) n'est pas encore terminée.":    'The task below (owner: %(name)s) is not yet completed.',
    "La %(type)s ci-dessous (responsable : %(name)s) n'est pas encore terminée.": 'The %(type)s below (owner: %(name)s) is not yet completed.',
    'En tant que responsable, vous devez traiter ce jalon impérativement :':        'As the owner, you must handle this milestone as a priority:',
    'En tant que responsable, vous devez traiter cette sous-étape impérativement :': 'As the owner, you must handle this sub-step as a priority:',
    'En tant que responsable, vous devez traiter cette tâche impérativement :':      'As the owner, you must handle this task as a priority:',
    'En tant que responsable, vous devez traiter cette %(type)s impérativement :':   'As the owner, you must handle this %(type)s as a priority:',
    '[CSIG] Événement annulé : {title}': '[CSIG] Event cancelled: {title}',
    'Événement annulé : {title}':        'Event cancelled: {title}',
    "L'événement « {title} » prévu le {date} a été annulé par {actor}.": 'The event “{title}” scheduled on {date} was cancelled by {actor}.',
}

def main():
    po = polib.pofile(PO, encoding='utf-8')
    existing = {e.msgid: e for e in po}

    updated = 0
    added   = 0

    for fr, en in TRANSLATIONS.items():
        if fr in existing:
            entry = existing[fr]
            if entry.msgid_plural:
                continue
            if not entry.msgstr.strip():
                entry.msgstr = en
                updated += 1
        else:
            po.append(polib.POEntry(msgid=fr, msgstr=en))
            added += 1

    po.save(PO)
    po.save_as_mofile(MO)
    print(f'Updated: {updated}  |  Added: {added}')
    print(f'Saved: {PO}')
    print(f'Compiled: {MO}')

    # Report remaining empty (plural-aware: msgstr_plural forms count too)
    po2 = polib.pofile(PO, encoding='utf-8')
    remaining = [e.msgid for e in po2
                 if not e.obsolete and not e.msgid_plural and not e.msgstr.strip()]
    remaining_plural = [e.msgid for e in po2
                        if not e.obsolete and e.msgid_plural
                        and not any(v.strip() for v in e.msgstr_plural.values())]
    print(f'\nStill untranslated: {len(remaining)}')
    for s in remaining:
        print(' ', repr(s))
    print(f'Still untranslated (plural entries): {len(remaining_plural)}')
    for s in remaining_plural:
        print(' ', repr(s))

if __name__ == '__main__':
    main()
