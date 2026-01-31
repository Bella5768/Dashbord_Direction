from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Direction, Project, Milestone, Document, Partner, Event, Request, Employee, Budget, UserProfile


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
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
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


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'date', 'time', 'location']
    list_filter = ['event_type', 'date']
    search_fields = ['title']
    filter_horizontal = ['participants']


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
