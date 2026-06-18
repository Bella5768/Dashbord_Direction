"""Add English translations for all new strings."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import polib

TRANSLATIONS = {
    # ── password change
    'Changer mon mot de passe': 'Change my password',
    'Votre nouveau mot de passe prendra effet immédiatement': 'Your new password will take effect immediately',
    'Nouveau mot de passe': 'New password',
    'Votre mot de passe doit :': 'Your password must:',
    'Contenir au moins 8 caractères': 'Contain at least 8 characters',
    'Contenir une majuscule et une minuscule': 'Contain an uppercase and a lowercase letter',
    'Contenir au moins un chiffre': 'Contain at least one digit',
    'Correspondre à la confirmation': 'Match the confirmation',
    'Mot de passe actuel': 'Current password',
    'Confirmer le nouveau mot de passe': 'Confirm new password',
    'Enregistrer le nouveau mot de passe': 'Save new password',
    'Afficher/masquer': 'Show/hide',
    # password strength
    'Très faible': 'Very weak',
    'Faible': 'Weak',
    'Moyen': 'Medium',
    'Fort': 'Strong',
    'Très fort': 'Very strong',
    # password reset
    'Mot de passe oublié': 'Forgot password',
    'Email envoyé': 'Email sent',
    'Vérifiez votre email': 'Check your email',
    'Adresse email du compte': 'Account email address',
    "Utilisez l'adresse associée à votre compte CSIG.": "Use the address associated with your CSIG account.",
    'Envoyer le lien de réinitialisation': 'Send reset link',
    'Retour à la': 'Back to',
    'connexion': 'login',
    'Réinitialiser mon mot de passe': 'Reset my password',
    'Choisir un nouveau mot de passe': 'Choose a new password',
    'Lien invalide': 'Invalid link',
    'Lien invalide ou expiré': 'Invalid or expired link',
    'Faire une nouvelle demande': 'Submit a new request',
    "Recevoir un nouveau lien d'activation": 'Receive a new activation link',
    'Bonjour': 'Hello',
    'choisissez un nouveau mot de passe sécurisé.': 'choose a secure new password.',
    'Votre identifiant de connexion': 'Your login identifier',
    "Si un compte actif correspond à cette adresse, un <strong>lien de réinitialisation</strong> vient d'être envoyé.":
        "If an active account matches this address, a <strong>reset link</strong> has just been sent.",
    "Le lien sera valable <strong>3 jours</strong>. Vérifiez aussi vos spams.":
        "The link will be valid for <strong>3 days</strong>. Also check your spam.",
    "Si vous ne recevez rien, votre adresse email est peut-être différente. Contactez votre administrateur si besoin.":
        "If you receive nothing, your email address may be different. Contact your administrator if needed.",
    "Ce lien de réinitialisation n'est plus valide.": "This reset link is no longer valid.",
    "Il a peut-être <strong>déjà été utilisé</strong> ou il a <strong>expiré</strong> (validité : 3 jours).":
        "It may have <strong>already been used</strong> or it has <strong>expired</strong> (validity: 3 days).",
    "Ce compte n'a pas encore été activé. Utilisez le lien d'activation qui vous a été envoyé par email.":
        "This account has not been activated yet. Use the activation link sent to you by email.",
    'Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe :':
        'Click the button below to choose a new password:',
    'Ou copiez ce lien dans votre navigateur :': 'Or copy this link in your browser:',
    "Ce lien est valable <strong>3 jours</strong>. Si vous n'avez pas demandé cette réinitialisation, ignorez cet email — votre mot de passe reste inchangé.":
        "This link is valid for <strong>3 days</strong>. If you did not request this reset, ignore this email — your password remains unchanged.",
    # account activation
    'Activation de votre compte': 'Account activation',
    'Activer mon compte': 'Activate my account',
    'Pour activer votre compte et choisir votre mot de passe, cliquez sur le bouton ci-dessous :':
        'To activate your account and choose your password, click the button below:',
    "Ce lien est valable <strong>3 jours</strong>. Si vous n'avez pas demandé ce compte, ignorez cet email.":
        "This link is valid for <strong>3 days</strong>. If you did not request this account, ignore this email.",
    "Merci de vous être inscrit sur notre plateforme. Pour activer votre compte, veuillez cliquer sur le bouton ci-dessous :":
        "Thank you for registering on our platform. To activate your account, please click the button below:",
    'Ou copiez et collez ce lien dans votre navigateur :': 'Or copy and paste this link in your browser:',
    'Ce lien expire dans 24 heures.': 'This link expires in 24 hours.',
    "Si vous n'avez pas demandé cette inscription, vous pouvez ignorer cet email.":
        "If you did not request this registration, you can ignore this email.",
    'a créé un compte pour vous sur le tableau de bord CSIG.':
        'created an account for you on the CSIG Dashboard.',
    'Un compte a été créé pour vous sur le tableau de bord CSIG.':
        'An account has been created for you on the CSIG Dashboard.',
    # email base / footer
    "Centre de Suivi et d'Information de Gestion": "Centre de Suivi et d'Information de Gestion",
    'Email automatique — merci de ne pas répondre.': 'Automated email — please do not reply.',
    # email content
    'Consulter la demande': 'View request',
    'Accéder au projet': 'View project',
    'Vous avez été ajouté au projet suivant :': 'You have been added to the following project:',
    'Ajouté par': 'Added by',
    'Terminée par': 'Completed by',
    'Connectez-vous au tableau de bord CSIG pour consulter les détails.':
        'Log in to the CSIG Dashboard to view the details.',
    "Connectez-vous au tableau de bord CSIG pour mettre à jour l'avancement.":
        "Log in to the CSIG Dashboard to update the progress.",
    'responsable': 'responsible',
    'Action requise': 'Action required',
    'Cordialement,': 'Best regards,',
    "L'équipe CSIG": 'The CSIG Team',
    'Nous avons reçu une demande de réinitialisation du mot de passe pour le compte associé à votre adresse email.':
        'We received a password reset request for the account associated with your email address.',
    "Saisissez l'adresse email de votre compte. Si elle existe, vous recevrez un lien pour choisir un nouveau mot de passe.":
        "Enter your account email address. If it exists, you will receive a link to choose a new password.",
    # dashboard
    'Budget par projet': 'Budget by project',
    'Alloué vs Consommé — Top 10 (en millions GNF)': 'Allocated vs Consumed — Top 10 (in millions GNF)',
    'Voir détail': 'View details',
    "Aucun projet n'a encore de budget renseigné.": 'No project has a budget entered yet.',
    'Créer / éditer un projet': 'Create / edit a project',
    'Répartition des projets': 'Project breakdown',
    'Aucun projet enregistré.': 'No projects registered.',
    'Créer un projet': 'Create a project',
    # data-delete-type labels
    "l'événement": 'the event',
    'la direction': 'the department',
    'le document': 'the document',
    'le jalon': 'the milestone',
    'la sous-étape': 'the sub-step',
    'le partenaire': 'the partner',
    'le projet': 'the project',
    'le membre': 'the member',
    'le dossier': 'the folder',
    'le budget': 'the budget',
    # leave confirm dialogs
    'Cette action est irréversible. La demande sera annulée définitivement.':
        'This action is irreversible. The request will be permanently cancelled.',
    'Annuler la demande': 'Cancel the request',
    'Oui, annuler': 'Yes, cancel',
    'ANNULER': 'CANCEL',
    'Cette pièce jointe sera supprimée définitivement.': 'This attachment will be permanently deleted.',
    'Supprimer la pièce jointe': 'Delete attachment',
    'SUPPRIMER': 'DELETE',
    # flash messages from f-string conversion
    'Compte créé pour {name}. Invitation envoyée à {email}.':
        'Account created for {name}. Invitation sent to {email}.',
    "Compte créé (identifiant : {username}) mais l'email n'a pas pu être envoyé : {msg}":
        "Account created (username: {username}) but the email could not be sent: {msg}",
    "L'utilisateur {username} a été modifié avec succès.": 'User {username} has been updated successfully.',
    "L'utilisateur {username} a été supprimé.": 'User {username} has been deleted.',
    "{username} est en attente d'invitation. Renvoyez l'invitation pour qu'il active son compte lui-même.":
        "{username} is waiting for an invitation. Resend the invitation so they can activate their account.",
    "L'utilisateur {username} a été {status}.": 'User {username} has been {status}.',
    'Bienvenue {name} ! Votre compte est activé.': 'Welcome {name}! Your account is activated.',
    'Le compte de {username} est déjà actif.': 'The account of {username} is already active.',
    "Le compte de {username} n'est pas en attente d'invitation (il a déjà un mot de passe).":
        "The account of {username} is not waiting for an invitation (they already have a password).",
    'Invitation renvoyée à {email}.': 'Invitation resent to {email}.',
    "Échec de l'envoi : {msg}": 'Sending failed: {msg}',
    'Sous-étape terminée mais notification email échouée : {msg}':
        'Sub-step completed but email notification failed: {msg}',
    'Sous-étape marquée comme {status}.': 'Sub-step marked as {status}.',
    'Jalon terminé mais notification email échouée : {msg}':
        'Milestone completed but email notification failed: {msg}',
    'Jalon marqué comme {label}.': 'Milestone marked as {label}.',
    'Statut mis à jour : {status}.': 'Status updated: {status}.',
    'Besoin marqué : {status}.': 'Need marked: {status}.',
    'Invitation envoyée à {email} (identifiant : {username}).':
        'Invitation sent to {email} (username: {username}).',
    "{username} est en attente d'invitation. Renvoyez l'invitation pour qu'il active son compte lui-même.":
        "{username} is waiting for an invitation. Resend the invitation so they can activate their account.",
    "Compte '{username}' créé mais l'email n'a pas pu être envoyé : {msg}.":
        "Account '{username}' created but the email could not be sent: {msg}.",
    "Compte non créé : {name} n'a pas d'adresse email.": "Account not created: {name} has no email address.",
    "Personne {label} '{name}' créée et ajoutée au projet.":
        "Person {label} '{name}' created and added to the project.",
    'Erreur : {err}': 'Error: {err}',
    "Document '{title}' signé.": "Document '{title}' signed.",
    "Document '{title}' validé, en attente de signature.": "Document '{title}' validated, awaiting signature.",
    "Demande '{title}' approuvée.": "Request '{title}' approved.",
    "Demande '{title}' rejetée.": "Request '{title}' rejected.",
    'Impossible de supprimer {name} : {count} demande(s) de congé sont liées à cette fiche.':
        'Cannot delete {name}: {count} leave request(s) are linked to this record.',
    'Employé « {name} » supprimé.': 'Employee "{name}" deleted.',
    'Suppression impossible : {err}': 'Deletion failed: {err}',
}

po_path = os.path.join(ROOT, 'locale', 'en', 'LC_MESSAGES', 'django.po')
po = polib.pofile(po_path, encoding='utf-8')

updated = 0
for entry in po:
    if entry.msgstr == '' and not entry.obsolete:
        if entry.msgid in TRANSLATIONS:
            entry.msgstr = TRANSLATIONS[entry.msgid]
            updated += 1

po.save(po_path)
po.save_as_mofile(po_path.replace('.po', '.mo'))

remaining = [e for e in po if not e.msgstr and not e.obsolete]
print(f'Updated: {updated}  |  Remaining: {len(remaining)}')
for e in remaining:
    print(f'  MISS: {repr(e.msgid[:90])}')
