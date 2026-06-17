from django.urls import path
from . import views
from . import views_leave
from . import views_roles

app_name = 'core'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('mot-de-passe-oublie/', views.password_reset_request, name='password_reset_info'),
    path('reinitialiser/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('mon-compte/', views.profile, name='profile'),
    path('mon-compte/mot-de-passe/', views.password_change, name='password_change'),
    
    # Main pages
    path('', views.dashboard, name='dashboard'),
    path('recherche/', views.global_search, name='global_search'),
    path('projets/', views.projects, name='projects'),
    path('ressources/', views.resources, name='resources'),
    path('demandes/', views.requests_view, name='requests'),
    path('calendrier/', views.calendar, name='calendar'),
    
    # Event CRUD
    path('evenements/nouveau/', views.event_create, name='event_create'),
    path('evenements/<int:event_id>/', views.event_detail, name='event_detail'),
    path('evenements/<int:event_id>/modifier/', views.event_edit, name='event_edit'),
    path('evenements/<int:event_id>/supprimer/', views.event_delete, name='event_delete'),
    
    # Document CRUD (module Documents global)
    path('documents/', views.documents, name='documents'),
    path('documents/nouveau/', views.document_create, name='document_create'),
    path('documents/<int:doc_id>/modifier/', views.document_edit, name='document_edit'),
    path('documents/<int:doc_id>/supprimer/', views.document_delete, name='document_delete'),
    path('documents/<int:doc_id>/signer/', views.document_sign, name='document_sign'),
    path('documents/<int:doc_id>/valider/', views.document_validate, name='document_validate'),
    path('documents/<int:doc_id>/telecharger/', views.document_download, name='document_download'),

    # Reports
    path('rapports/', views.reports, name='reports'),
    path('rapports/export/pdf/', views.export_reports_pdf, name='export_reports_pdf'),
    path('ressources/employes/export/pdf/', views.export_employees_pdf, name='export_employees_pdf'),
    path('partenaires/', views.partners, name='partners'),
    
    # User Management
    path('utilisateurs/', views.users_list, name='users_list'),
    path('utilisateurs/nouveau/', views.user_create, name='user_create'),
    path('utilisateurs/activer/<uidb64>/<token>/', views.account_activate, name='account_activate'),
    path('utilisateurs/nouveau-lien/', views.request_new_activation, name='request_new_activation'),
    path('utilisateurs/<int:user_id>/modifier/', views.user_edit, name='user_edit'),
    path('utilisateurs/<int:user_id>/supprimer/', views.user_delete, name='user_delete'),
    path('utilisateurs/<int:user_id>/toggle/', views.user_toggle_status, name='user_toggle_status'),
    path('utilisateurs/<int:user_id>/password/', views.user_change_password, name='user_change_password'),
    path('utilisateurs/<int:user_id>/renvoyer-invitation/', views.resend_invitation, name='resend_invitation'),
    path('utilisateurs/activites/', views.user_activities, name='user_activities'),
    
    # Project CRUD
    path('projets/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projets/<int:project_id>/activites/export/', views.export_project_activities, name='export_project_activities'),
    path('projets/<int:project_id>/besoins/nouveau/', views.project_need_create, name='project_need_create'),
    path('projets/<int:project_id>/commentaires/nouveau/', views.project_comment_create, name='project_comment_create'),
    path('projets/nouveau/', views.project_create, name='project_create'),
    path('projets/<int:project_id>/modifier/', views.project_edit, name='project_edit'),
    path('projets/<int:project_id>/supprimer/', views.project_delete, name='project_delete'),
    
    # Milestone CRUD
    path('projets/<int:project_id>/jalons/nouveau/', views.milestone_create, name='milestone_create'),
    path('jalons/<int:milestone_id>/', views.milestone_detail, name='milestone_detail'),
    path('jalons/<int:milestone_id>/modifier/', views.milestone_edit, name='milestone_edit'),
    path('jalons/<int:milestone_id>/supprimer/', views.milestone_delete, name='milestone_delete'),
    path('jalons/<int:milestone_id>/toggle/', views.milestone_toggle, name='milestone_toggle'),
    path('jalons/<int:milestone_id>/statut/', views.milestone_update_status, name='milestone_update_status'),
    path('jalons/<int:milestone_id>/assigner/', views.milestone_quick_assign, name='milestone_quick_assign'),

    # SubMilestone CRUD
    path('jalons/<int:milestone_id>/sous-etapes/nouveau/', views.sub_milestone_create, name='sub_milestone_create'),
    path('sous-etapes/<int:sub_milestone_id>/modifier/', views.sub_milestone_edit, name='sub_milestone_edit'),
    path('sous-etapes/<int:sub_milestone_id>/supprimer/', views.sub_milestone_delete, name='sub_milestone_delete'),
    path('sous-etapes/<int:sub_milestone_id>/toggle/', views.sub_milestone_toggle, name='sub_milestone_toggle'),
    path('sous-etapes/<int:sub_milestone_id>/assigner/', views.sub_milestone_quick_assign, name='sub_milestone_quick_assign'),
    
    # Project Folder & Document CRUD
    path('projets/<int:project_id>/dossiers/nouveau/', views.project_folder_create, name='project_folder_create'),
    path('dossiers/<int:folder_id>/', views.project_folder_detail, name='project_folder_detail'),
    path('dossiers/<int:folder_id>/modifier/', views.project_folder_edit, name='project_folder_edit'),
    path('dossiers/<int:folder_id>/supprimer/', views.project_folder_delete, name='project_folder_delete'),
    path('projets/<int:project_id>/documents/nouveau/', views.project_document_create, name='project_document_create'),
    path('projets/documents/<int:doc_id>/modifier/', views.project_document_edit, name='project_document_edit'),
    path('projets/documents/<int:doc_id>/supprimer/', views.project_document_delete, name='project_document_delete'),
    path('projets/documents/<int:doc_id>/telecharger/', views.project_document_download, name='project_document_download'),
    
    # Project Need status
    path('besoins/<int:need_id>/statut/', views.project_need_update_status, name='project_need_update_status'),

    # Project Member CRUD
    path('projets/<int:project_id>/membres/ajouter/', views.project_member_add, name='project_member_add'),
    path('projets/membres/<int:member_id>/modifier/', views.project_member_edit, name='project_member_edit'),
    path('projets/membres/<int:member_id>/supprimer/', views.project_member_delete, name='project_member_delete'),
    
    
    # My tasks
    path('mes-taches/', views.my_tasks, name='my_tasks'),

    # Request CRUD
    path('demandes/nouveau/', views.request_create, name='request_create'),
    path('demandes/<int:req_id>/approuver/', views.request_approve, name='request_approve'),
    path('demandes/<int:req_id>/rejeter/', views.request_reject, name='request_reject'),
    
    # Partner CRUD
    path('partenaires/nouveau/', views.partner_create, name='partner_create'),
    path('partenaires/<int:partner_id>/modifier/', views.partner_edit, name='partner_edit'),
    path('partenaires/<int:partner_id>/supprimer/', views.partner_delete, name='partner_delete'),
    
    # Budget CRUD
    path('budgets/nouveau/', views.budget_create, name='budget_create'),
    path('budgets/<int:budget_id>/modifier/', views.budget_edit, name='budget_edit'),
    path('budgets/<int:budget_id>/supprimer/', views.budget_delete, name='budget_delete'),
    
    # Employee CRUD
    path('employes/nouveau/', views.employee_create, name='employee_create'),
    path('employes/<int:employee_id>/modifier/', views.employee_edit, name='employee_edit'),
    path('employes/<int:employee_id>/supprimer/', views.employee_delete, name='employee_delete'),
    
    # Rôles RBAC
    path('roles/', views_roles.roles_list, name='roles_list'),
    path('roles/nouveau/', views_roles.role_create, name='role_create'),
    path('roles/<int:role_id>/', views_roles.role_detail, name='role_detail'),
    path('roles/<int:role_id>/modifier/', views_roles.role_edit, name='role_edit'),
    path('roles/<int:role_id>/dupliquer/', views_roles.role_duplicate, name='role_duplicate'),
    path('roles/<int:role_id>/supprimer/', views_roles.role_delete, name='role_delete'),
    # Rôles projet
    path('roles-projet/', views_roles.project_roles_list, name='project_roles_list'),
    path('roles-projet/nouveau/', views_roles.project_role_create, name='project_role_create'),
    path('roles-projet/<int:role_id>/modifier/', views_roles.project_role_edit, name='project_role_edit'),
    path('roles-projet/<int:role_id>/dupliquer/', views_roles.project_role_duplicate, name='project_role_duplicate'),
    path('roles-projet/<int:role_id>/supprimer/', views_roles.project_role_delete, name='project_role_delete'),

    # Direction CRUD
    path('directions/', views.directions_list, name='directions_list'),
    path('directions/nouveau/', views.direction_create, name='direction_create'),
    path('directions/<int:direction_id>/modifier/', views.direction_edit, name='direction_edit'),
    path('directions/<int:direction_id>/supprimer/', views.direction_delete, name='direction_delete'),
    
    # API endpoints
    path('api/budget/', views.api_budget_data, name='api_budget'),
    path('api/projects/', views.api_projects_data, name='api_projects'),
    path('api/projets/<int:project_id>/jalons/reorder/', views.milestone_reorder, name='milestone_reorder'),
    path('api/jalons/<int:milestone_id>/sous-etapes/reorder/', views.sub_milestone_reorder, name='sub_milestone_reorder'),
    path('api/projets/<int:project_id>/status/', views.api_project_update_status, name='api_project_update_status'),
    path('api/projets/<int:project_id>/tasks/create/', views.api_project_task_create, name='api_project_task_create'),
    path('api/tasks/<int:milestone_id>/update/', views.api_project_task_update, name='api_project_task_update'),

    # Conges
    path('conges/', views_leave.leave_list, name='leave_list'),
    path('conges/nouveau/', views_leave.leave_create, name='leave_create'),
    path('conges/<int:leave_id>/', views_leave.leave_detail, name='leave_detail'),
    path('conges/<int:leave_id>/modifier/', views_leave.leave_edit, name='leave_edit'),
    path('conges/<int:leave_id>/annuler/', views_leave.leave_cancel, name='leave_cancel'),
    path('conges/<int:leave_id>/document/<int:doc_id>/supprimer/', views_leave.leave_document_delete, name='leave_document_delete'),
    path('conges/<int:leave_id>/decision-hierarchique/', views_leave.leave_decide_manager, name='leave_decide_manager'),
    path('conges/<int:leave_id>/verification-rh/', views_leave.leave_decide_hr, name='leave_decide_hr'),
    path('conges/<int:leave_id>/decision-finale/', views_leave.leave_decide_final, name='leave_decide_final'),
    path('conges/<int:leave_id>/attestation.pdf', views_leave.leave_pdf_download, name='leave_pdf_download'),
]
