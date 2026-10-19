from django.contrib import admin, messages
from django.http import HttpResponseRedirect

from .models import Company, DigestLog, Task


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        "title", "company", "responsible_email", "cycle_days", "last_done", "next_due", "status",
    ]
    list_filter = ["status", "company"]
    search_fields = ["title", "responsible_email"]
    readonly_fields = ["next_due"]
    actions = ["mark_done"]
    change_form_template = "admin/maintenance/task/change_form.html"

    @admin.action(description="Отметить выполненным")
    def mark_done(self, request, queryset):
        count = 0
        for task in queryset:
            task.mark_done()
            count += 1
        self.message_user(request, f"Отмечено выполненным: {count}.", messages.SUCCESS)

    def response_change(self, request, obj):
        if "_mark_done" in request.POST:
            obj.mark_done()
            self.message_user(
                request, f"Задача отмечена выполненной, следующий срок {obj.next_due:%d.%m.%Y}.",
                messages.SUCCESS,
            )
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)


@admin.register(DigestLog)
class DigestLogAdmin(admin.ModelAdmin):
    list_display = ["email", "sent_on"]
    list_filter = ["sent_on"]
