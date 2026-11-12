from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("courses", views.CourseViewSet, basename="api-course")
router.register("subjects", views.SubjectViewSet, basename="api-subject")
router.register("batches", views.BatchViewSet)
router.register("students", views.StudentViewSet)
router.register("live-classes", views.LiveClassViewSet)
router.register("tasks", views.TaskViewSet)
router.register("assessments", views.AssessmentViewSet)
router.register("questions", views.QuestionViewSet)

ASSESSMENT_URLS = []
for kind, plural in [("quiz", "quizzes"), ("exam", "exams"), ("assignment", "assignments")]:
    ASSESSMENT_URLS += [
        path(f"{plural}/", views.assessment_list, {"kind": kind}, name=f"{kind}_list"),
        path(f"{plural}/add/", views.wizard_start, {"kind": kind}, name=f"{kind}_add"),
        path(f"{plural}/add/<str:step>/", views.assessment_wizard, {"kind": kind}, name=f"{kind}_wizard"),
        path(f"{plural}/<int:pk>/created/", views.assessment_created, {"kind": kind}, name=f"{kind}_created"),
        path(f"{plural}/<int:pk>/", views.assessment_detail, {"kind": kind}, name=f"{kind}_detail"),
        path(f"{plural}/<int:pk>/edit/", views.assessment_form, {"kind": kind}, name=f"{kind}_edit"),
        path(f"{plural}/<int:pk>/results/", views.assessment_results, {"kind": kind}, name=f"{kind}_results"),
        path(f"{plural}/<int:pk>/delete/", views.assessment_delete, {"kind": kind}, name=f"{kind}_delete"),
    ]

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="main/login.html",redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/", include(router.urls)),

    path("", views.dashboard, name="dashboard"),

    path("live-classes/", views.live_class_list, name="live_class_list"),
    path("live-classes/add/", views.live_class_form, name="live_class_add"),
    path("live-classes/<int:pk>/edit/", views.live_class_form, name="live_class_edit"),
    path("live-classes/<int:pk>/delete/", views.live_class_delete, name="live_class_delete"),
    path("live-classes/<int:pk>/attendance/", views.attendance, name="attendance"),

    path("schedule/", views.schedule, name="schedule"),
    path("tasks/add/", views.task_form, name="task_add"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_form, name="task_edit"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),

    path("quizzes/question-bank/", views.assessment_list, {"kind": "quiz", "tab": "bank"}, name="question_bank"),
    path("quizzes/tags/add/", views.tag_create, name="tag_add"),
    path("tags/<int:pk>/", views.tag_detail, name="tag_detail"),
    path("tags/<int:pk>/edit/", views.tag_edit, name="tag_edit"),
    path("tags/<int:pk>/delete/", views.tag_delete, name="tag_delete"),
    path("quizzes/questions/add/", views.question_create, name="question_add"),
    path("quizzes/questions/<int:pk>/delete/", views.question_delete, name="question_delete"),

    path("quizzes/<int:pk>/tags/", views.quiz_tags, name="quiz_tags"),
    path("assignments/<int:pk>/attach/", views.attachment_add, name="attachment_add"),
    path("attachments/<int:pk>/", views.attachment_download, name="attachment_download"),
    path("attachments/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),

    *ASSESSMENT_URLS,

    path("batches/", views.batch_list, name="batch_list"),
    path("batches/add/", views.batch_form, name="batch_add"),
    path("batches/<int:pk>/", views.batch_detail, name="batch_detail"),
    path("batches/<int:pk>/edit/", views.batch_form, name="batch_edit"),
    path("batches/<int:pk>/delete/", views.batch_delete, name="batch_delete"),

    path("courses/", views.course_list, name="course_list"),
    path("courses/add/", views.course_form, name="course_add"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("courses/<int:pk>/edit/", views.course_form, name="course_edit"),
    path("courses/<int:pk>/delete/", views.course_delete, name="course_delete"),
    path("courses/<int:pk>/subjects/add/", views.subject_add, name="subject_add"),
    path("subjects/<int:pk>/delete/", views.subject_delete, name="subject_delete"),

    path("students/", views.student_list, name="student_list"),
    path("students/add/", views.student_form, name="student_add"),
    path("students/<int:pk>/", views.student_profile, name="student_profile"),
    path("students/<int:pk>/edit/", views.student_form, name="student_edit"),
    path("students/<int:pk>/delete/", views.student_delete, name="student_delete"),

    path("profile/", views.profile, name="profile"),
    path("settings/", views.settings_page, name="settings"),
]
