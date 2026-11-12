import datetime

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from rest_framework import viewsets

from .forms import (
    AssessmentForm, BatchForm, BatchesStepForm, CourseForm, CourseStepForm, DetailsStepForm, LiveClassForm,
    PdfUploadForm, ProfileForm, QuestionForm, QuestionsStepForm, StudentForm, SubjectForm, SubjectStepForm,
    TagForm, TagsCompositionForm, TaskForm, my_courses, visible_tags,
)
from .models import (
    Assessment, AssessmentTag, Attachment, Attendance, Batch, Course, LiveClass, Question, Result, Student,
    Subject, Tag, Task,
)
from .serializers import (
    AssessmentSerializer, BatchSerializer, CourseSerializer, LiveClassSerializer,
    QuestionSerializer, StudentSerializer, SubjectSerializer, TaskSerializer,
)

KINDS_RU = {
    "quiz": {"plural": "Тесты", "one": "Тест", "gen": "теста", "acc": "тест",
             "saved": "Тест сохранён.", "deleted": "Тест удалён.", "created": "Тест создан"},
    "exam": {"plural": "Экзамены", "one": "Экзамен", "gen": "экзамена", "acc": "экзамен",
             "saved": "Экзамен сохранён.", "deleted": "Экзамен удалён.", "created": "Экзамен создан"},
    "assignment": {"plural": "Задания", "one": "Задание", "gen": "задания", "acc": "задание",
                   "saved": "Задание сохранено.", "deleted": "Задание удалено.", "created": "Задание создано"},
}


def paginate(request, queryset, per_page=9):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def search_filter(queryset, q, *fields):
    if not q:
        return queryset
    needle = q.casefold()
    ids = [row[0] for row in queryset.order_by().values_list("pk", *fields)
           if any(needle in str(value or "").casefold() for value in row[1:])]
    return queryset.filter(pk__in=ids)


def confirm_delete(request, section, title, what, name, cancel_url, cancel_args=None, warning=""):
    return render(request, "main/confirm_delete.html", {
        "section": section, "title": title, "what": what, "name": name, "warning": warning,
        "cancel_url": cancel_url, "cancel_args": cancel_args or []})


@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()
    task_filter = request.GET.get("task", "all")
    tasks = Task.objects.filter(teacher=user)
    if task_filter in dict(Task.STATUSES):
        tasks = tasks.filter(status=task_filter)

    batches = Batch.objects.filter(teacher=user).annotate(
        subject_count=Count("subjects", distinct=True),
        student_count=Count("students", distinct=True),
        quiz_count=Count("assessments", filter=Q(assessments__kind="quiz"), distinct=True),
        exam_count=Count("assessments", filter=Q(assessments__kind="exam"), distinct=True),
        assignment_count=Count("assessments", filter=Q(assessments__kind="assignment"), distinct=True),
    )
    stats = [
        ("Курсы", my_courses(user).count(), "course_list"),
        ("Студенты", Student.objects.filter(batch__teacher=user).count(), "student_list"),
        ("Предстоящие занятия",
         LiveClass.objects.filter(teacher=user, date__gte=today).exclude(status="completed").count(),
         "live_class_list"),
        ("Открытые задачи", Task.objects.filter(teacher=user).exclude(status="completed").count(), "schedule"),
    ]
    context = {
        "section": "dashboard",
        "stats": stats,
        "live_classes": LiveClass.objects.filter(teacher=user).exclude(status="completed")[:3],
        "tasks": tasks[:5],
        "task_filter": task_filter,
        "task_tabs": [("all", "Все")] + Task.STATUSES,
        "batches": batches[:4],
    }
    return render(request, "main/dashboard.html", context)


@login_required
def live_class_list(request):
    tab = request.GET.get("tab", "scheduled")
    classes = LiveClass.objects.filter(teacher=request.user).select_related("batch")
    if tab == "history":
        classes = classes.filter(status="completed").order_by("-date", "-time")
    else:
        tab = "scheduled"
        classes = classes.exclude(status="completed")
    q = request.GET.get("q", "").strip()
    classes = search_filter(classes, q, "title", "batch__name")
    context = {
        "section": "live_classes", "tab": tab, "q": q,
        "page": paginate(request, classes),
        "attended_ids": set(Attendance.objects.filter(live_class__teacher=request.user)
                            .values_list("live_class_id", flat=True)),
    }
    return render(request, "main/live_classes/list.html", context)


@login_required
def live_class_form(request, pk=None):
    live_class = get_object_or_404(LiveClass, pk=pk, teacher=request.user) if pk else None
    form = LiveClassForm(request.POST or None, instance=live_class, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.teacher = request.user
        obj.save()
        messages.success(request, "Занятие сохранено.")
        return redirect("live_class_list")
    return render(request, "main/live_classes/form.html", {"section": "live_classes", "form": form, "obj": live_class})


@login_required
def live_class_delete(request, pk):
    live_class = get_object_or_404(LiveClass, pk=pk, teacher=request.user)
    if request.method == "POST":
        live_class.delete()
        messages.success(request, "Занятие удалено.")
        return redirect("live_class_list")
    return confirm_delete(request, "live_classes", "Удаление занятия", "занятие", live_class.title,
                          "live_class_list")


@login_required
def attendance(request, pk):
    live_class = get_object_or_404(LiveClass, pk=pk, teacher=request.user)
    students = live_class.batch.students.all()
    if request.method == "POST":
        present_ids = set(request.POST.getlist("present"))
        for student in students:
            Attendance.objects.update_or_create(
                live_class=live_class, student=student,
                defaults={"present": str(student.pk) in present_ids})
        messages.success(request, "Посещаемость сохранена.")
        return redirect("attendance", pk=pk)
    marks = {a.student_id: a.present for a in live_class.attendance.all()}
    rows = [(s, marks.get(s.pk)) for s in students]
    context = {"section": "live_classes", "live_class": live_class, "rows": rows, "has_report": bool(marks)}
    return render(request, "main/live_classes/attendance.html", context)


def week_schedule(user, monday):
    """Занятия, тесты, экзамены и задания на 7 дней начиная с понедельника: [(день, [события])]."""
    days = [monday + datetime.timedelta(days=i) for i in range(7)]
    events = {day: [] for day in days}
    for c in LiveClass.objects.filter(teacher=user, date__range=(days[0], days[-1])).select_related("batch__course"):
        events[c.date].append({
            "time": c.time, "title": c.title, "course": c.batch.course.name, "type": "Онлайн-занятие",
            "css": "live", "url": reverse("live_class_edit", args=[c.pk])})
    for a in Assessment.objects.filter(teacher=user, date__range=(days[0], days[-1])).select_related("course"):
        events[a.date].append({
            "time": a.start_time, "title": a.title, "course": a.course.name, "type": a.get_kind_display(),
            "css": a.kind, "url": reverse(f"{a.kind}_detail", args=[a.pk])})
    for day in days:
        events[day].sort(key=lambda e: e["time"])
    return [(day, events[day]) for day in days]


@login_required
def schedule(request):
    today = timezone.localdate()
    tab = "week" if request.GET.get("tab") == "week" else "tasks"
    context = {"section": "schedule", "tab": tab, "today": today}
    if tab == "week":
        try:
            chosen = datetime.date.fromisoformat(request.GET.get("date", ""))
        except ValueError:
            chosen = today
        monday = chosen - datetime.timedelta(days=chosen.weekday())
        context.update({
            "week": week_schedule(request.user, monday),
            "monday": monday, "sunday": monday + datetime.timedelta(days=6),
            "prev_week": monday - datetime.timedelta(days=7),
            "next_week": monday + datetime.timedelta(days=7),
        })
    else:
        tasks = Task.objects.filter(teacher=request.user)
        context["columns"] = [(value, label, tasks.filter(status=value)) for value, label in Task.STATUSES]
    return render(request, "main/schedule.html", context)


@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task, pk=pk, teacher=request.user)
    if request.method == "POST":
        status = request.POST.get("status")
        if status in dict(Task.STATUSES):
            task.status = status
            task.save(update_fields=["status"])
            messages.success(request, "Статус задачи обновлён.")
            return redirect("schedule")
        messages.error(request, "Выберите статус из списка.")
    return render(request, "main/task_detail.html", {
        "section": "schedule", "task": task, "statuses": Task.STATUSES})


@login_required
def task_form(request, pk=None):
    task = get_object_or_404(Task, pk=pk, teacher=request.user) if pk else None
    initial = {"assigned_at": timezone.localtime().replace(second=0, microsecond=0)} if not task else None
    form = TaskForm(request.POST or None, instance=task, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.teacher = request.user
        obj.save()
        messages.success(request, "Задача сохранена.")
        return redirect("task_detail", pk=obj.pk)
    return render(request, "main/simple_form.html", {
        "section": "schedule", "form": form, "back": "schedule",
        "title": "Редактирование задачи" if task else "Новая задача"})


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, teacher=request.user)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Задача удалена.")
        return redirect("schedule")
    return confirm_delete(request, "schedule", "Удаление задачи", "задачу", task.title,
                          "task_detail", [task.pk])


def get_kind(kind):
    if kind not in KINDS_RU:
        raise Http404
    return kind


@login_required
def assessment_list(request, kind, tab=None):
    get_kind(kind)
    tab = tab or request.GET.get("tab", "scheduled")
    q = request.GET.get("q", "").strip()
    today = timezone.localdate()
    context = {"section": kind, "kind": kind, "ru": KINDS_RU[kind], "tab": tab, "q": q}

    if kind == "quiz" and tab == "bank":
        questions = Question.objects.filter(teacher=request.user).select_related("subject", "tag")
        questions = search_filter(questions, q, "text")
        context["page"] = paginate(request, questions, 10)
        context["tags"] = visible_tags(request.user).select_related("subject")
        return render(request, "main/assessments/question_bank.html", context)

    items = Assessment.objects.filter(teacher=request.user, kind=kind).select_related("course", "subject")
    if tab == "history":
        items = items.filter(date__lt=today).order_by("-date")
    else:
        context["tab"] = "scheduled"
        items = items.filter(date__gte=today)
    items = search_filter(items, q, "title", "subject__name")
    context["page"] = paginate(request, items)
    return render(request, "main/assessments/list.html", context)


@login_required
def assessment_detail(request, kind, pk):
    assessment = get_object_or_404(Assessment, pk=pk, teacher=request.user, kind=get_kind(kind))
    template = "main/assessments/assignment_detail.html" if kind == "assignment" else "main/assessments/detail.html"
    return render(request, template, {
        "section": kind, "kind": kind, "ru": KINDS_RU[kind], "a": assessment,
        "results_count": assessment.results.exclude(status="unattempted").count()})


@login_required
def assessment_form(request, kind, pk=None):
    get_kind(kind)
    assessment = get_object_or_404(Assessment, pk=pk, teacher=request.user, kind=kind) if pk else None
    form = AssessmentForm(request.POST or None, instance=assessment, user=request.user, kind=kind)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.teacher = request.user
        obj.kind = kind
        obj.save()
        form.save_m2m()
        messages.success(request, KINDS_RU[kind]["saved"])
        return redirect(f"{kind}_detail", pk=obj.pk)
    return render(request, "main/assessments/form.html", {
        "section": kind, "kind": kind, "ru": KINDS_RU[kind], "form": form, "a": assessment})


@login_required
def assessment_delete(request, kind, pk):
    assessment = get_object_or_404(Assessment, pk=pk, teacher=request.user, kind=get_kind(kind))
    ru = KINDS_RU[kind]
    if request.method == "POST":
        assessment.delete()
        messages.success(request, ru["deleted"])
        return redirect(f"{kind}_list")
    return confirm_delete(request, kind, f"Удаление {ru['gen']}", ru["acc"], assessment.title,
                          f"{kind}_detail", [assessment.pk],
                          warning="Вместе с ним будут удалены результаты студентов.")


@login_required
def assessment_results(request, kind, pk):
    assessment = get_object_or_404(Assessment, pk=pk, teacher=request.user, kind=get_kind(kind))
    students = Student.objects.filter(batch__in=assessment.batches.filter(teacher=request.user)).distinct()
    total = assessment.total_marks
    saved = {r.student_id: r for r in assessment.results.all()}

    rows, all_valid = [], True
    for student in students:
        result = saved.get(student.pk)
        if request.method == "POST":
            raw = request.POST.get(f"score_{student.pk}", "").strip()
        else:
            raw = str(result.score) if result and result.status != "unattempted" else ""
        error = ""
        if raw and (not raw.isdigit() or int(raw) > total):
            error = f"Введите число от 0 до {total}."
            all_valid = False
        rows.append({"student": student, "value": raw, "error": error, "result": result})

    if request.method == "POST" and all_valid:
        for row in rows:
            if row["value"] == "":
                status, score = "unattempted", 0
            else:
                score = int(row["value"])
                status = "passed" if score * 100 >= assessment.passing_percentage * total else "failed"
            Result.objects.update_or_create(
                student=row["student"], assessment=assessment, defaults={"status": status, "score": score})
        messages.success(request, "Результаты сохранены.")
        return redirect(f"{kind}_results", pk=pk)
    return render(request, "main/assessments/results.html", {
        "section": kind, "kind": kind, "ru": KINDS_RU[kind], "a": assessment, "rows": rows, "total": total})


MULTI_FIELDS = ("batches", "questions")


def wizard_steps(kind):
    steps = ["course", "subject", "batches", "details"]
    if kind == "assignment":
        steps.append("files")
    else:
        steps.append("questions")
    if kind == "quiz":
        steps.append("tags")
    return steps + ["preview"]


def get_draft(request, kind):
    return request.session.get(f"draft_{kind}", {})


def save_draft(request, kind, draft):
    request.session[f"draft_{kind}"] = draft


def drop_draft(request, kind):
    draft = request.session.pop(f"draft_{kind}", {})
    for item in draft.get("files", []):
        default_storage.delete(item["path"])


def raw_initial(draft, step):
    raw = draft.get("raw", {}).get(step, {})
    return {key: (values if key in MULTI_FIELDS else values[0]) for key, values in raw.items() if values}


def keep_raw(draft, step, post):
    draft.setdefault("raw", {})[step] = {k: post.getlist(k) for k in post if k not in ("csrfmiddlewaretoken", "nav")}


def draft_initial(draft, step, defaults):
    initial = dict(defaults)
    initial.update(raw_initial(draft, step))
    return initial


@login_required
def wizard_start(request, kind):
    get_kind(kind)
    drop_draft(request, kind)
    return redirect(f"{kind}_wizard", step="course")


@login_required
def assessment_wizard(request, kind, step):
    get_kind(kind)
    steps = wizard_steps(kind)
    if step not in steps:
        raise Http404
    draft = get_draft(request, kind)

    draft_key = {"course": "course", "subject": "subject", "batches": "batches", "details": "title",
                 "questions": "questions_done", "files": "files_done", "tags": "tags_done"}
    for earlier in steps[:steps.index(step)]:
        if draft_key[earlier] not in draft:
            return redirect(f"{kind}_wizard", step=earlier)

    index = steps.index(step)
    next_step = steps[index + 1] if index + 1 < len(steps) else None
    prev_step = steps[index - 1] if index > 0 else None

    if request.method == "POST" and request.POST.get("nav") == "back" and prev_step:
        keep_raw(draft, step, request.POST)
        save_draft(request, kind, draft)
        return redirect(f"{kind}_wizard", step=prev_step)

    posted = request.POST if request.method == "POST" else None    
    course = my_courses(request.user).filter(pk=draft.get("course")).first()
    subject = Subject.objects.filter(pk=draft.get("subject"), course=course).first() if course else None
    context = {
        "section": kind, "kind": kind, "ru": KINDS_RU[kind], "step": step, "steps": steps[:-1],
        "step_number": index + 1, "total_steps": len(steps) - 1, "prev_step": prev_step,
        "course": course, "subject": subject,
    }

    def go_next():
        draft.get("raw", {}).pop(step, None)
        save_draft(request, kind, draft)
        return redirect(f"{kind}_wizard", step=next_step)

    if step == "course":
        form = CourseStepForm(posted, user=request.user,
                              initial=draft_initial(draft, step, {"course": draft.get("course")}))
        if request.method == "POST" and form.is_valid():
            if draft.get("course") != form.cleaned_data["course"].pk:
                draft = {"course": form.cleaned_data["course"].pk}  
            return go_next()
    elif step == "subject":
        form = SubjectStepForm(posted, course=course,
                               initial=draft_initial(draft, step, {"subject": draft.get("subject")}))
        if request.method == "POST" and form.is_valid():
            chosen = form.cleaned_data["subject"].pk
            if draft.get("subject") != chosen:
                draft = {"course": draft["course"], "subject": chosen}
            return go_next()
    elif step == "batches":
        form = BatchesStepForm(posted, user=request.user, course=course,
                               initial=draft_initial(draft, step, {"batches": draft.get("batches", [])}))
        if request.method == "POST" and form.is_valid():
            draft["batches"] = [b.pk for b in form.cleaned_data["batches"]]
            return go_next()
    elif step == "details":
        defaults = {key: draft.get(key) for key in (
            "title", "questions_count", "passing_percentage", "max_marks", "date", "start_time", "end_time",
            "due_date", "due_time") if draft.get(key) is not None}
        form = DetailsStepForm(posted, kind=kind, initial=draft_initial(draft, step, defaults))
        if request.method == "POST" and form.is_valid():
            for key, value in form.cleaned_data.items():
                draft[key] = value if isinstance(value, (str, int)) else value.isoformat()
            return go_next()
    elif step == "questions":
        form = QuestionsStepForm(posted, user=request.user, subject=subject, initial=draft_initial(
            draft, step, {"questions": draft.get("questions", [])}))
        if request.method == "POST" and form.is_valid():
            draft["questions"] = [q.pk for q in form.cleaned_data["questions"]]
            draft["questions_done"] = True
            return go_next()
    elif step == "files":
        form = PdfUploadForm(posted, request.FILES or None)
        files = draft.setdefault("files", [])
        context["files"] = files
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "upload":
                if form.is_valid():
                    f = form.cleaned_data["file"]
                    path = default_storage.save(f"drafts/{request.user.pk}/{f.name}", f)
                    files.append({"path": path, "name": f.name[:200]})
                    save_draft(request, kind, draft)
                    messages.success(request, f"Файл «{f.name}» добавлен.")
                    return redirect(f"{kind}_wizard", step="files")
            elif action == "remove":
                index_to_remove = int(request.POST.get("index", -1)) if request.POST.get("index", "").isdigit() else -1
                if 0 <= index_to_remove < len(files):
                    default_storage.delete(files.pop(index_to_remove)["path"])
                    save_draft(request, kind, draft)
                return redirect(f"{kind}_wizard", step="files")
            else:
                draft["files_done"] = True
                return go_next()
    elif step == "tags":
        form = TagsCompositionForm(posted, subject=subject, user=request.user, initial_percents={
            int(k): v for k, v in draft.get("tags", {}).items()})
        if not form.tags:                    
            draft["tags"], draft["tags_done"] = {}, True
            return go_next()
        if request.method == "POST" and form.is_valid():
            draft["tags"], draft["tags_done"] = form.percents(), True
            return go_next()
        context["question_total"] = draft.get("questions_count")
    else:  
        form = None
        picked = Question.objects.filter(pk__in=draft.get("questions", []), teacher=request.user)
        context.update({
            "draft": draft, "batches": Batch.objects.filter(pk__in=draft["batches"], teacher=request.user),
            "tag_parts": [(Tag.objects.get(pk=int(k)), v) for k, v in draft.get("tags", {}).items()],
            "picked": picked, "files": draft.get("files", []),
            "question_count": picked.count() or draft.get("questions_count"),
            "total_marks": draft.get("max_marks") if kind == "assignment"
            else (picked.aggregate(total=Sum("marks"))["total"] or draft.get("questions_count")),
        })
        if request.method == "POST":
            return finish_wizard(request, kind, draft, course, subject)

    context["form"] = form
    return render(request, "main/assessments/wizard.html", context)


def finish_wizard(request, kind, draft, course, subject):
    allowed = ("title", "questions_count", "passing_percentage", "date", "start_time", "end_time",
               "max_marks", "due_date", "due_time")
    data = {key: draft[key] for key in allowed if key in draft}
    data.update({"course": course.pk, "subject": subject.pk, "batches": draft["batches"],
                 "questions": draft.get("questions", [])})
    form = AssessmentForm(data, user=request.user, kind=kind)
    if not form.is_valid():
        messages.error(request, "Часть данных стала недействительной: " + "; ".join(
            f"{name}: {', '.join(errors)}" for name, errors in form.errors.items()))
        return redirect(f"{kind}_wizard", step="details")
    obj = form.save(commit=False)
    obj.teacher = request.user
    obj.kind = kind
    obj.save()
    form.save_m2m()
    for tag_id, percent in draft.get("tags", {}).items():
        tag = visible_tags(request.user).filter(Q(subject=subject) | Q(subject__isnull=True), pk=int(tag_id)).first()
        if tag:
            AssessmentTag.objects.create(assessment=obj, tag=tag, percent=percent)
    for item in draft.get("files", []):
        Attachment.objects.create(assessment=obj, file=item["path"], name=item["name"])
    request.session.pop(f"draft_{kind}", None)         
    return redirect(f"{kind}_created", pk=obj.pk)


@login_required
def assessment_created(request, kind, pk):
    assessment = get_object_or_404(Assessment, pk=pk, teacher=request.user, kind=get_kind(kind))
    return render(request, "main/assessments/created.html", {
        "section": kind, "kind": kind, "ru": KINDS_RU[kind], "a": assessment})


@login_required
def quiz_tags(request, pk):
    quiz = get_object_or_404(Assessment, pk=pk, teacher=request.user, kind="quiz")
    current = {part.tag_id: part.percent for part in quiz.tag_parts.all()}
    form = TagsCompositionForm(request.POST or None, subject=quiz.subject, user=request.user,initial_percents=current)
    if request.method == "POST" and form.is_valid():
        quiz.tag_parts.all().delete()
        for tag_id, percent in form.percents().items():
            AssessmentTag.objects.create(assessment=quiz, tag_id=tag_id, percent=percent)
        messages.success(request, "Состав тегов сохранён.")
        return redirect("quiz_detail", pk=quiz.pk)
    return render(request, "main/assessments/tags_form.html", {"section": "quiz", "kind": "quiz", "a": quiz, "form": form})


@login_required
def attachment_add(request, pk):
    assignment = get_object_or_404(Assessment, pk=pk, teacher=request.user, kind="assignment")
    form = PdfUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        f = form.cleaned_data["file"]
        Attachment.objects.create(assessment=assignment, file=f, name=f.name[:200])
        messages.success(request, "PDF-файл прикреплён.")
        return redirect("assignment_detail", pk=assignment.pk)
    return render(request, "main/assessments/attachment_form.html", {
        "section": "assignment", "kind": "assignment", "a": assignment, "form": form})


@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(Attachment, pk=pk, assessment__teacher=request.user)
    return FileResponse(attachment.file.open("rb"), content_type="application/pdf",
                        as_attachment=False, filename=attachment.name)


@login_required
def attachment_delete(request, pk):
    attachment = get_object_or_404(Attachment, pk=pk, assessment__teacher=request.user)
    assignment_pk = attachment.assessment_id
    if request.method == "POST":
        attachment.file.delete(save=False)
        attachment.delete()
        messages.success(request, "PDF-файл удалён.")
        return redirect("assignment_detail", pk=assignment_pk)
    return confirm_delete(request, "assignment", "Удаление файла", "файл", attachment.name,
                          "assignment_detail", [assignment_pk])


@login_required
def tag_create(request):
    form = TagForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        tag = form.save(commit=False)
        tag.teacher = request.user
        tag.save()
        messages.success(request, "Тег добавлен.")
        return redirect("tag_detail", pk=tag.pk)
    return render(request, "main/simple_form.html", {
        "section": "quiz", "form": form, "title": "Новый тег", "back": "question_bank"})


def own_visible_tag(request, pk):
    return get_object_or_404(visible_tags(request.user), pk=pk)


@login_required
def tag_detail(request, pk):
    tag = own_visible_tag(request, pk)
    quizzes = AssessmentTag.objects.filter(tag=tag, assessment__teacher=request.user).select_related("assessment")
    return render(request, "main/assessments/tag_detail.html", {
        "section": "quiz", "tag": tag, "can_edit": tag.teacher_id == request.user.id,
        "questions": Question.objects.filter(teacher=request.user, tag=tag).select_related("subject"),
        "parts": quizzes})


@login_required
def tag_edit(request, pk):
    tag = own_visible_tag(request, pk)
    if tag.teacher_id != request.user.id:
        raise PermissionDenied        
    form = TagForm(request.POST or None, instance=tag, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Тег сохранён.")
        return redirect("tag_detail", pk=tag.pk)
    return render(request, "main/simple_form.html", {
        "section": "quiz", "form": form, "title": "Редактирование тега", "back": "question_bank"})


@login_required
def tag_delete(request, pk):
    tag = own_visible_tag(request, pk)
    if tag.teacher_id != request.user.id:
        raise PermissionDenied
    if request.method == "POST":
        tag.delete()
        messages.success(request, "Тег удалён.")
        return redirect("question_bank")
    return confirm_delete(request, "quiz", "Удаление тега", "тег", tag.name, "tag_detail", [tag.pk])


@login_required
def question_create(request):
    form = QuestionForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.teacher = request.user
        question.save()
        messages.success(request, "Вопрос добавлен.")
        return redirect("question_bank")
    return render(request, "main/simple_form.html", {
        "section": "quiz", "form": form, "title": "Новый вопрос", "back": "question_bank"})


@login_required
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk, teacher=request.user)
    if request.method == "POST":
        question.delete()
        messages.success(request, "Вопрос удалён.")
        return redirect("question_bank")
    return confirm_delete(request, "quiz", "Удаление вопроса", "вопрос", question.text[:80], "question_bank")


@login_required
def batch_list(request):
    q = request.GET.get("q", "").strip()
    batches = search_filter(Batch.objects.filter(teacher=request.user), q, "name", "course__name")
    batches = batches.select_related("course").annotate(student_count=Count("students", distinct=True)).order_by("name")
    return render(request, "main/batches/list.html", {
        "section": "batches", "q": q, "page": paginate(request, batches)})


@login_required
def batch_detail(request, pk):
    batch = get_object_or_404(Batch.objects.select_related("course"), pk=pk, teacher=request.user)
    tab = request.GET.get("tab", "overview")
    context = {"section": "batches", "batch": batch, "tab": tab}
    if tab == "overview":
        all_subjects = {}
        for subject in batch.course.subjects.all():
            all_subjects.setdefault(subject.semester, []).append(subject)
        my_subjects = {}
        for subject in batch.subjects.all():
            my_subjects.setdefault(subject.semester, []).append(subject)
        context["all_subjects"] = sorted(all_subjects.items())
        context["my_subjects"] = sorted(my_subjects.items())
        context["students"] = batch.students.all()
    elif tab == "classes":
        context["items"] = batch.live_classes.all()
    elif tab in ("quizzes", "exams", "assignments"):
        kind = {"quizzes": "quiz", "exams": "exam", "assignments": "assignment"}[tab]
        context["items"] = batch.assessments.filter(kind=kind)
    return render(request, "main/batches/detail.html", context)


@login_required
def batch_form(request, pk=None):
    batch = get_object_or_404(Batch, pk=pk, teacher=request.user) if pk else None
    form = BatchForm(request.POST or None, instance=batch, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.teacher = request.user
        obj.save()
        form.save_m2m()
        messages.success(request, "Группа сохранена.")
        return redirect("batch_detail", pk=obj.pk)
    return render(request, "main/simple_form.html", {
        "section": "batches", "form": form, "back": "batch_list",
        "title": "Редактирование группы" if batch else "Новая группа"})


@login_required
def batch_delete(request, pk):
    batch = get_object_or_404(Batch, pk=pk, teacher=request.user)
    if request.method == "POST":
        batch.delete()
        messages.success(request, "Группа удалена.")
        return redirect("batch_list")
    return confirm_delete(request, "batches", "Удаление группы", "группу", batch.name, "batch_detail", [batch.pk],
                          warning="Вместе с группой будут удалены её студенты, занятия и результаты.")


@login_required
def course_list(request):
    q = request.GET.get("q", "").strip()
    courses = search_filter(my_courses(request.user), q, "name").annotate(
        subject_count=Count("subjects", distinct=True),
        student_count=Count("batches__students", filter=Q(batches__teacher=request.user), distinct=True),
    ).order_by("name")
    return render(request, "main/courses/list.html", {
        "section": "courses", "q": q, "page": paginate(request, courses)})


@login_required
def course_detail(request, pk):
    course = get_object_or_404(my_courses(request.user), pk=pk)
    semesters = {}
    for subject in course.subjects.all():
        semesters.setdefault(subject.semester, []).append(subject)
    batches = course.batches.filter(teacher=request.user).annotate(student_count=Count("students"))
    return render(request, "main/courses/detail.html", {
        "section": "courses", "course": course, "semesters": sorted(semesters.items()),
        "batches": batches, "can_edit": course.teacher_id == request.user.id})


@login_required
def course_form(request, pk=None):
    course = None
    if pk:
        course = get_object_or_404(my_courses(request.user), pk=pk)
        if course.teacher_id != request.user.id:
            raise PermissionDenied        # чужой или общий курс менять нельзя
    form = CourseForm(request.POST or None, instance=course)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not course:
            obj.teacher = request.user
        obj.save()
        messages.success(request, "Курс сохранён.")
        return redirect("course_detail", pk=obj.pk)
    return render(request, "main/simple_form.html", {
        "section": "courses", "form": form, "back": "course_list",
        "title": "Редактирование курса" if course else "Новый курс"})


@login_required
def course_delete(request, pk):
    course = get_object_or_404(my_courses(request.user), pk=pk)
    if course.teacher_id != request.user.id:
        raise PermissionDenied
    if course.batches.exclude(teacher=request.user).exists():
        messages.error(request, "Курс нельзя удалить: на нём есть группы других преподавателей.")
        return redirect("course_detail", pk=pk)
    if request.method == "POST":
        course.delete()
        messages.success(request, "Курс удалён.")
        return redirect("course_list")
    return confirm_delete(request, "courses", "Удаление курса", "курс", course.name, "course_detail", [pk],
                          warning="Вместе с курсом будут удалены его предметы, ваши группы со студентами, "
                                  "тесты, экзамены и задания.")


@login_required
def subject_add(request, pk):
    course = get_object_or_404(my_courses(request.user), pk=pk)
    if course.teacher_id != request.user.id:
        raise PermissionDenied
    form = SubjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        subject = form.save(commit=False)
        subject.course = course
        subject.save()
        messages.success(request, "Предмет добавлен.")
        return redirect("course_detail", pk=course.pk)
    return render(request, "main/simple_form.html", {
        "section": "courses", "form": form, "back": "course_detail", "back_args": [course.pk],
        "title": f"Новый предмет: {course.name}"})


@login_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject.objects.select_related("course"), pk=pk,
                                course__in=my_courses(request.user))
    if subject.course.teacher_id != request.user.id:
        raise PermissionDenied
    course_pk = subject.course_id
    if request.method == "POST":
        subject.delete()
        messages.success(request, "Предмет удалён.")
        return redirect("course_detail", pk=course_pk)
    return confirm_delete(request, "courses", "Удаление предмета", "предмет", subject.name,
                          "course_detail", [course_pk],
                          warning="Вместе с предметом будут удалены его вопросы, теги и работы по нему.")


@login_required
def student_list(request):
    q = request.GET.get("q", "").strip()
    students = Student.objects.filter(batch__teacher=request.user).select_related("batch__course")
    my_batches = Batch.objects.filter(teacher=request.user)
    course_id, batch_id = request.GET.get("course", ""), request.GET.get("batch", "")
    students = search_filter(students, q, "full_name", "student_code")
    if course_id.isdigit():
        students = students.filter(batch__course_id=int(course_id))
    if batch_id.isdigit():
        students = students.filter(batch_id=int(batch_id))
    return render(request, "main/students/list.html", {
        "section": "students", "q": q, "course_id": course_id, "batch_id": batch_id,
        "courses": my_courses(request.user), "batches": my_batches,
        "page": paginate(request, students, 10)})


@login_required
def student_form(request, pk=None):
    student = get_object_or_404(Student, pk=pk, batch__teacher=request.user) if pk else None
    form = StudentForm(request.POST or None, instance=student, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, "Студент сохранён.")
        return redirect("student_profile", pk=obj.pk)
    return render(request, "main/simple_form.html", {
        "section": "students", "form": form, "back": "student_list",
        "title": "Редактирование студента" if student else "Новый студент"})


@login_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk, batch__teacher=request.user)
    if request.method == "POST":
        student.delete()
        messages.success(request, "Студент удалён.")
        return redirect("student_list")
    return confirm_delete(request, "students", "Удаление студента", "студента", student.full_name,
                          "student_profile", [student.pk],
                          warning="Вместе со студентом будут удалены его посещаемость и результаты.")


@login_required
def student_profile(request, pk):
    student = get_object_or_404(Student.objects.select_related("batch__course"), pk=pk, batch__teacher=request.user)
    tab = request.GET.get("tab", "general")
    classes = student.attendance.all()
    results = student.results.select_related("assessment")

    def stats(kind):
        rows = results.filter(assessment__kind=kind)
        return {
            "total": rows.count(),
            "attempted": rows.exclude(status="unattempted").count(),
            "unattempted": rows.filter(status="unattempted").count(),
            "passed": rows.filter(status="passed").count(),
            "failed": rows.filter(status="failed").count(),
        }

    attended = classes.filter(present=True).count()
    total = classes.count()
    context = {
        "section": "students", "student": student, "tab": tab,
        "attended": attended, "missed": total - attended, "total_classes": total,
        "attendance_percent": round(attended * 100 / total) if total else 0,
        "quiz_stats": stats("quiz"), "exam_stats": stats("exam"), "assignment_stats": stats("assignment"),
        "initials": "".join(w[0] for w in student.full_name.split()[:2]).upper(),
    }
    if tab in ("quiz", "exams", "assignment"):
        kind = {"quiz": "quiz", "exams": "exam", "assignment": "assignment"}[tab]
        context["rows"] = results.filter(assessment__kind=kind)
    elif tab == "classes":
        context["rows"] = classes.select_related("live_class")
    return render(request, "main/students/profile.html", context)


@login_required
def profile(request):
    user = request.user
    form = ProfileForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профиль сохранён.")
        return redirect("profile")
    summary = [
        ("Группы", Batch.objects.filter(teacher=user).count()),
        ("Студенты", Student.objects.filter(batch__teacher=user).count()),
        ("Онлайн-занятия", LiveClass.objects.filter(teacher=user).count()),
        ("Тесты", Assessment.objects.filter(teacher=user, kind="quiz").count()),
        ("Экзамены", Assessment.objects.filter(teacher=user, kind="exam").count()),
        ("Задания", Assessment.objects.filter(teacher=user, kind="assignment").count()),
    ]
    return render(request, "main/profile.html", {"section": "profile", "form": form, "summary": summary})


@login_required
def settings_page(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)      
        messages.success(request, "Пароль изменён.")
        return redirect("settings")
    return render(request, "main/settings.html", {"section": "settings", "form": form})



def error_403(request, exception=None):
    return render(request, "main/error.html", {"code": 403, "text": "У вас нет доступа к этой странице."}, status=403)


def error_404(request, exception=None):
    return render(request, "main/error.html", {"code": 404, "text": "Страница не найдена."}, status=404)


class TeacherViewSet(viewsets.ModelViewSet):
    owner_field = "teacher"

    def get_queryset(self):
        return super().get_queryset().filter(**{self.owner_field: self.request.user})

    def perform_create(self, serializer):
        if self.owner_field == "teacher":
            serializer.save(teacher=self.request.user)
        else:
            serializer.save()


class BatchViewSet(TeacherViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer


class StudentViewSet(TeacherViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    owner_field = "batch__teacher"


class LiveClassViewSet(TeacherViewSet):
    queryset = LiveClass.objects.all()
    serializer_class = LiveClassSerializer


class TaskViewSet(TeacherViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer


class AssessmentViewSet(TeacherViewSet):
    queryset = Assessment.objects.all()
    serializer_class = AssessmentSerializer


class QuestionViewSet(TeacherViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseSerializer

    def get_queryset(self):
        return my_courses(self.request.user)


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubjectSerializer

    def get_queryset(self):
        return Subject.objects.filter(course__in=my_courses(self.request.user))
