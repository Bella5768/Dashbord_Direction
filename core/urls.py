from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Main pages
    path('', views.dashboard, name='dashboard'),
    path('projets/', views.projects, name='projects'),
    path('ressources/', views.resources, name='resources'),
    path('demandes/', views.requests_view, name='requests'),
    path('calendrier/', views.calendar, name='calendar'),
    
    # Event CRUD
    path('evenements/nouveau/', views.event_create, name='event_create'),
    path('evenements/<int:event_id>/modifier/', views.event_edit, name='event_edit'),
    path('evenements/<int:event_id>/supprimer/', views.event_delete, name='event_delete'),
    
    # Reports
    path('rapports/', views.reports, name='reports'),
    path('rapports/export/pdf/', views.export_reports_pdf, name='export_reports_pdf'),
    path('partenaires/', views.partners, name='partners'),
    
    # User Management
    path('utilisateurs/', views.users_list, name='users_list'),
    path('utilisateurs/nouveau/', views.user_create, name='user_create'),
    path('utilisateurs/<int:user_id>/modifier/', views.user_edit, name='user_edit'),
    path('utilisateurs/<int:user_id>/supprimer/', views.user_delete, name='user_delete'),
    path('utilisateurs/<int:user_id>/toggle/', views.user_toggle_status, name='user_toggle_status'),
    path('utilisateurs/<int:user_id>/password/', views.user_change_password, name='user_change_password'),
    path('utilisateurs/activites/', views.user_activities, name='user_activities'),
    
    # Project CRUD
    path('projets/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projets/<int:project_id>/besoins/nouveau/', views.project_need_create, name='project_need_create'),
    path('projets/<int:project_id>/commentaires/nouveau/', views.project_comment_create, name='project_comment_create'),
    path('projets/nouveau/', views.project_create, name='project_create'),
    path('projets/<int:project_id>/modifier/', views.project_edit, name='project_edit'),
    path('projets/<int:project_id>/supprimer/', views.project_delete, name='project_delete'),
    
    # Milestone CRUD
    path('projets/<int:project_id>/jalons/nouveau/', views.milestone_create, name='milestone_create'),
    path('jalons/<int:milestone_id>/modifier/', views.milestone_edit, name='milestone_edit'),
    path('jalons/<int:milestone_id>/supprimer/', views.milestone_delete, name='milestone_delete'),
    
    # Project Folder & Document CRUD
    path('projets/<int:project_id>/dossiers/nouveau/', views.project_folder_create, name='project_folder_create'),
    path('dossiers/<int:folder_id>/', views.project_folder_detail, name='project_folder_detail'),
    path('dossiers/<int:folder_id>/modifier/', views.project_folder_edit, name='project_folder_edit'),
    path('dossiers/<int:folder_id>/supprimer/', views.project_folder_delete, name='project_folder_delete'),
    path('projets/<int:project_id>/documents/nouveau/', views.project_document_create, name='project_document_create'),
    path('projets/documents/<int:doc_id>/modifier/', views.project_document_edit, name='project_document_edit'),
    path('projets/documents/<int:doc_id>/supprimer/', views.project_document_delete, name='project_document_delete'),
    
    # Project Member CRUD
    path('projets/<int:project_id>/membres/ajouter/', views.project_member_add, name='project_member_add'),
    path('projets/membres/<int:member_id>/modifier/', views.project_member_edit, name='project_member_edit'),
    path('projets/membres/<int:member_id>/supprimer/', views.project_member_delete, name='project_member_delete'),
    
    
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
    
    # API endpoints
    path('api/budget/', views.api_budget_data, name='api_budget'),
    path('api/projects/', views.api_projects_data, name='api_projects'),
]
