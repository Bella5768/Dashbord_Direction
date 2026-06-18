"""
Converts f-string flash messages in views.py to _("...{var}...").format() pattern.
Run from project root: python scripts/fix_fstrings.py
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = os.path.join(ROOT, 'core', 'views.py')

# Each tuple: (exact_old_substring, exact_new_substring)
# Using double quotes for _() whenever the message contains apostrophes.
FIXES = [
    # ── employee create / invite
    (
        'f"Compte créé pour {emp.name}. Invitation envoyée à {emp.email}."',
        '_("Compte créé pour {name}. Invitation envoyée à {email}.").format(name=emp.name, email=emp.email)',
    ),
    (
        'f"Compte créé (identifiant : {username}) mais l\'email n\'a pas pu être envoyé : {email_msg}"',
        '_("Compte créé (identifiant : {username}) mais l\'email n\'a pas pu être envoyé : {msg}").format(username=username, msg=email_msg)',
    ),
    # ── user edit / delete / toggle
    (
        'f"L\'utilisateur {user_obj.username} a été modifié avec succès."',
        '_("L\'utilisateur {username} a été modifié avec succès.").format(username=user_obj.username)',
    ),
    (
        'f"L\'utilisateur {username} a été supprimé."',
        '_("L\'utilisateur {username} a été supprimé.").format(username=username)',
    ),
    (
        'f"{user_obj.username} est en attente d\'invitation. Renvoyez l\'invitation pour qu\'il active son compte lui-même."',
        '_("{username} est en attente d\'invitation. Renvoyez l\'invitation pour qu\'il active son compte lui-même.").format(username=user_obj.username)',
    ),
    (
        'f"L\'utilisateur {user_obj.username} a été {status}."',
        '_("L\'utilisateur {username} a été {status}.").format(username=user_obj.username, status=status)',
    ),
    # ── account activation
    (
        'f"Bienvenue {user.get_full_name() or user.username} ! Votre compte est activé."',
        '_("Bienvenue {name} ! Votre compte est activé.").format(name=user.get_full_name() or user.username)',
    ),
    (
        'f"Le compte de {user_obj.username} est déjà actif."',
        '_("Le compte de {username} est déjà actif.").format(username=user_obj.username)',
    ),
    (
        'f"Le compte de {user_obj.username} n\'est pas en attente d\'invitation (il a déjà un mot de passe)."',
        '_("Le compte de {username} n\'est pas en attente d\'invitation (il a déjà un mot de passe).").format(username=user_obj.username)',
    ),
    (
        'f"Invitation renvoyée à {user_obj.email}."',
        '_("Invitation renvoyée à {email}.").format(email=user_obj.email)',
    ),
    (
        'f"Échec de l\'envoi : {msg}"',
        '_("Échec de l\'envoi : {msg}").format(msg=msg)',
    ),
    # ── milestone sub-step
    (
        'f"Sous-étape terminée mais notification email échouée : {msg}"',
        '_("Sous-étape terminée mais notification email échouée : {msg}").format(msg=msg)',
    ),
    (
        'f"Sous-étape marquée comme {status}."',
        '_("Sous-étape marquée comme {status}.").format(status=status)',
    ),
    (
        'f"Jalon terminé mais notification email échouée : {msg}"',
        '_("Jalon terminé mais notification email échouée : {msg}").format(msg=msg)',
    ),
    (
        'f"Jalon marqué comme {label}."',
        '_("Jalon marqué comme {label}.").format(label=label)',
    ),
    # ── task / need status
    (
        'f"Statut mis à jour : {valid[new_status]}."',
        '_("Statut mis à jour : {status}.").format(status=valid[new_status])',
    ),
    (
        'f"Besoin marqué : {valid[new_status]}."',
        '_("Besoin marqué : {status}.").format(status=valid[new_status])',
    ),
    # ── project member add (new employee)
    (
        'f"Invitation envoyée à {new_employee.email} (identifiant : {new_username})."',
        '_("Invitation envoyée à {email} (identifiant : {username}).").format(email=new_employee.email, username=new_username)',
    ),
    (
        'f"Compte \'{new_username}\' créé mais l\'email n\'a pas pu être envoyé : {msg}."',
        '_("Compte \'{username}\' créé mais l\'email n\'a pas pu être envoyé : {msg}.").format(username=new_username, msg=msg)',
    ),
    (
        'f"Compte non créé : {new_employee.name} n\'a pas d\'adresse email."',
        '_("Compte non créé : {name} n\'a pas d\'adresse email.").format(name=new_employee.name)',
    ),
    (
        'f"Personne {label} \'{new_name}\' créée et ajoutée au projet."',
        '_("Personne {label} \'{name}\' créée et ajoutée au projet.").format(label=label, name=new_name)',
    ),
    (
        'f"Erreur : {exc}"',
        '_("Erreur : {err}").format(err=exc)',
    ),
    # ── document sign / validate
    (
        'f"Document \'{doc.title}\' signé."',
        '_("Document \'{title}\' signé.").format(title=doc.title)',
    ),
    (
        'f"Document \'{doc.title}\' validé, en attente de signature."',
        '_("Document \'{title}\' validé, en attente de signature.").format(title=doc.title)',
    ),
    # ── request approve / reject
    (
        'f"Demande \'{req.title}\' approuvée."',
        '_("Demande \'{title}\' approuvée.").format(title=req.title)',
    ),
    (
        'f"Demande \'{req.title}\' rejetée."',
        '_("Demande \'{title}\' rejetée.").format(title=req.title)',
    ),
    # ── employee delete
    (
        'f"Impossible de supprimer {employee.name} : {leave_count} demande(s) de congé sont liées à cette fiche."',
        '_("Impossible de supprimer {name} : {count} demande(s) de congé sont liées à cette fiche.").format(name=employee.name, count=leave_count)',
    ),
    (
        'f"Employé « {name} » supprimé."',
        '_("Employé « {name} » supprimé.").format(name=name)',
    ),
    (
        'f"Suppression impossible : {e}"',
        '_("Suppression impossible : {err}").format(err=e)',
    ),
]


def run():
    with open(VIEWS, encoding='utf-8') as fh:
        src = fh.read()

    applied, missed = 0, []
    for old, new in FIXES:
        if old in src:
            src = src.replace(old, new, 1)
            applied += 1
        else:
            missed.append(old[:80])

    with open(VIEWS, 'w', encoding='utf-8') as fh:
        fh.write(src)

    print(f'Applied: {applied}  |  Missed: {len(missed)}')
    for m in missed:
        print(f'  MISS: {m}')


if __name__ == '__main__':
    run()
