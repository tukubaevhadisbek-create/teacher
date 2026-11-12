from django.contrib import admin

from .models import (
    Assessment, AssessmentTag, Attachment, Attendance, Batch, Course, LiveClass,
    Question, Result, Student, Subject, Tag, Task,
)


class AssessmentTagInline(admin.TabularInline):
    model = AssessmentTag
    extra = 1


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "course", "subject", "date", "teacher"]
    list_filter = ["kind", "teacher"]
    search_fields = ["title"]
    inlines = [AssessmentTagInline]


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ["name", "course", "teacher", "end_date"]
    list_filter = ["teacher"]


@admin.register(LiveClass)
class LiveClassAdmin(admin.ModelAdmin):
    list_display = ["title", "batch", "date", "time", "status", "teacher"]
    list_filter = ["status", "teacher"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["full_name", "student_code", "batch"]
    search_fields = ["full_name", "student_code"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "due_at", "teacher"]
    list_filter = ["status", "teacher"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name", "course", "semester"]
    list_filter = ["course"]


admin.site.register(Attachment)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["name", "teacher"]
    search_fields = ["name"]


admin.site.register(Tag)
admin.site.register(Question)
admin.site.register(Attendance)
admin.site.register(Result)
