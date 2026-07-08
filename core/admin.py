import types
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Direction, Project, Milestone, Document, Partner, Event, EventMember, Request, Employee, Budget, UserProfile, LeaveRequest, LeaveDocument

# Restreindre l'admin Django aux superusers uniquement (pas à tous les is_staff)
admin.site.has_permission = types.MethodType(
    lambda self, request: request.user.is_active and request.user.is_superuser,
    admin.site,
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profil'
    fk_name = 'user'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_role', 'get_direction', 'is_active']
    list_filter = BaseUserAdmin.list_filter + ('profile__role', 'profile__direction')
    
    def get_role(self, obj):
        if hasattr(obj, 'profile') and obj.profile.role:
            return obj.profile.role.name
        return '-'
    get_role.short_description = 'Rôle'
    
    def get_direction(self, obj):
        if hasattr(obj, 'profile') and obj.profile.direction:
            return obj.profile.direction.code
        return '-'
    get_direction.short_description = 'Direction'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'direction', 'phone', 'is_active_profile']
    list_filter = ['role', 'direction', 'is_active_profile']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user']


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'color']
    search_fields = ['name', 'code']


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'direction', 'status', 'priority', 'progress', 'manager', 'end_date']
    list_filter = ['status', 'priority', 'direction']
    search_fields = ['name', 'manager']
    inlines = [MilestoneInline]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'doc_type', 'status', 'priority', 'direction', 'due_date']
    list_filter = ['status', 'doc_type', 'priority', 'direction']
    search_fields = ['title', 'created_by']


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'partner_type', 'status', 'contact_person', 'email']
    list_filter = ['partner_type', 'status']
    search_fields = ['name', 'contact_person']


class EventMemberInline(admin.TabularInline):
    model = EventMember
    extra = 0
    readonly_fields = ['invited_at', 'responded_at']
    fields = ['employee', 'status', 'note', 'invited_at', 'responded_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'date', 'time', 'location', 'created_by']
    list_filter = ['event_type', 'date']
    search_fields = ['title', 'description']
    filter_horizontal = ['participants']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    inlines = [EventMemberInline]


@admin.register(EventMember)
class EventMemberAdmin(admin.ModelAdmin):
    list_display = ['employee', 'event', 'status', 'invited_at', 'responded_at']
    list_filter = ['status', 'event__date']
    search_fields = ['employee__name', 'event__title']
    readonly_fields = ['invited_at', 'responded_at']


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ['title', 'direction', 'priority', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'priority', 'direction']
    search_fields = ['title', 'created_by']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'direction', 'role', 'workload']
    list_filter = ['direction']
    search_fields = ['name', 'role']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['direction', 'allocated', 'consumed', 'consumption_rate']


class LeaveDocumentInline(admin.TabularInline):
    model = LeaveDocument
    extra = 0


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'employee', 'direction', 'leave_type', 'start_date', 'end_date', 'days_count', 'status', 'created_at']
    list_filter = ['status', 'leave_type', 'direction', 'created_at']
    search_fields = ['employee__name', 'reason', 'replacement']
    readonly_fields = ['created_at', 'updated_at', 'days_count']
    inlines = [LeaveDocumentInline]
    fieldsets = (
        ('Demande', {
            'fields': ('employee', 'user', 'direction', 'leave_type', 'start_date', 'end_date', 'days_count', 'reason', 'replacement', 'handover_note', 'justification', 'status')
        }),
        ('Avis hiérarchique', {
            'fields': ('manager_decision', 'manager_comment', 'manager_user', 'manager_decision_at'),
        }),
        ('Vérification RH', {
            'fields': ('hr_decision', 'hr_comment', 'hr_user', 'hr_decision_at'),
        }),
        ('Décision finale', {
            'fields': ('final_decision', 'final_comment', 'final_user', 'final_decision_at'),
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


@admin.register(LeaveDocument)
class LeaveDocumentAdmin(admin.ModelAdmin):
    list_display = ['leave_request', 'label', 'uploaded_at']
    search_fields = ['label']
