import datetime

from django import forms
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    Assessment, Batch, Course, LiveClass, Question, Student, Subject, Tag, Task,
)


def date_input():
    return forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})

def time_input():
    return forms.TimeInput(format="%H:%M", attrs={"type": "time"})

def datetime_input():
    return forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})

def make_aware(day, time):
    return timezone.make_aware(datetime.datetime.combine(day, time))

def my_courses(user):
    ids = Course.objects.filter(Q(teacher=user) | Q(batches__teacher=user)).values("pk")
    return Course.objects.filter(pk__in=ids)

def visible_tags(user):
    return Tag.objects.filter(Q(teacher__isnull=True) | Q(teacher=user))


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name", "semester"]
        widgets = {"semester": forms.NumberInput(attrs={"min": 1, "max": 12})}

    def clean_semester(self):
        if not 1 <= self.cleaned_data["semester"] <= 12:
            raise forms.ValidationError("Семестр должен быть от 1 до 12.")
        return self.cleaned_data["semester"]

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["name", "course", "end_date", "subjects"]
        widgets = {"end_date": date_input(), "subjects": forms.CheckboxSelectMultiple}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        courses = my_courses(user)
        self.fields["course"].queryset = courses
        self.fields["subjects"].queryset = Subject.objects.filter(course__in=courses).select_related("course")
        self.fields["subjects"].label = "Предметы, которые вы ведёте в этой группе"

    def clean(self):
        data = super().clean()
        course = data.get("course")
        for subject in data.get("subjects") or []:
            if course and subject.course_id != course.id:
                self.add_error("subjects", "Все предметы должны относиться к выбранному курсу.")
                break
        return data


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "full_name", "student_code", "batch", "gender", "mother_name", "father_name",
            "course_start", "course_end", "center_pincode", "center_district", "center_state",
            "center_address", "center_phone", "center_email",
        ]
        widgets = {
            "course_start": date_input(), "course_end": date_input(),
            "center_address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = Batch.objects.filter(teacher=user)

    def clean(self):
        data = super().clean()
        start, end = data.get("course_start"), data.get("course_end")
        if start and end and end <= start:
            self.add_error("course_end", "Дата окончания должна быть позже даты начала.")
        return data

class LiveClassForm(forms.ModelForm):
    class Meta:
        model = LiveClass
        fields = ["title", "batch", "date", "time", "status", "meeting_link"]
        widgets = {"date": date_input(), "time": time_input()}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = Batch.objects.filter(teacher=user)


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "assigned_by", "assigned_at", "due_at", "status"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "assigned_at": datetime_input(), "due_at": datetime_input(),
        }

    def clean(self):
        data = super().clean()
        assigned, due = data.get("assigned_at"), data.get("due_at")
        if assigned and due and due <= assigned:
            self.add_error("due_at", "Срок выполнения должен быть позже даты назначения.")
        return data


class TaskStatusForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["status"]

class AssessmentForm(forms.ModelForm):
    due_date = forms.DateField(required=False, label="Срок сдачи: дата", widget=date_input())
    due_time = forms.TimeField(required=False, label="Срок сдачи: время", widget=time_input())

    class Meta:
        model = Assessment
        fields = [
            "title", "course", "subject", "batches", "questions_count", "passing_percentage",
            "date", "start_time", "end_time", "max_marks", "questions",
        ]
        widgets = {
            "batches": forms.CheckboxSelectMultiple,
            "questions": forms.CheckboxSelectMultiple,
            "date": date_input(),
            "start_time": time_input(),
            "end_time": time_input(),
            "passing_percentage": forms.NumberInput(attrs={"min": 0, "max": 100}),
        }

    def __init__(self, *args, user=None, kind="quiz", **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        courses = my_courses(user)
        self.fields["course"].queryset = courses
        self.fields["subject"].queryset = Subject.objects.filter(course__in=courses).select_related("course")
        self.fields["batches"].queryset = Batch.objects.filter(teacher=user)
        self.fields["questions"].queryset = Question.objects.filter(teacher=user)
        self.fields["questions"].required = False
        self.fields["questions"].label = "Вопросы из банка (необязательно)"
        if kind == "assignment":
            for name in ("questions_count", "passing_percentage", "end_time", "questions"):
                del self.fields[name]
            self.fields["max_marks"].min_value = 1
            self.fields["max_marks"].label = "Максимальный балл"
            self.fields["date"].label = "Дата выдачи"
            self.fields["start_time"].label = "Время выдачи"
            self.fields["due_date"].required = True
            self.fields["due_time"].required = True
            if self.instance.pk and self.instance.due_at:
                due = timezone.localtime(self.instance.due_at)
                self.initial.setdefault("due_date", due.date())
                self.initial.setdefault("due_time", due.time().replace(second=0, microsecond=0))
            self.order_fields(["title", "course", "subject", "batches", "max_marks", "date", "start_time",
                               "due_date", "due_time"])
        else:
            del self.fields["max_marks"], self.fields["due_date"], self.fields["due_time"]

    def clean(self):
        data = super().clean()
        course, subject = data.get("course"), data.get("subject")
        if course and subject and subject.course_id != course.id:
            self.add_error("subject", "Этот предмет не относится к выбранному курсу.")
        if self.kind == "assignment":
            if (data.get("max_marks") or 0) < 1:
                self.add_error("max_marks", "Максимальный балл должен быть не меньше 1.")
            start, day = data.get("start_time"), data.get("date")
            due_date, due_time = data.get("due_date"), data.get("due_time")
            if start and day and due_date and due_time and make_aware(due_date, due_time) <= make_aware(day, start):
                self.add_error("due_date", "Срок сдачи должен быть позже начала задания.")
            return data
        if data.get("passing_percentage") is not None and data["passing_percentage"] > 100:
            self.add_error("passing_percentage", "Процент не может быть больше 100.")
        start, end = data.get("start_time"), data.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "Время окончания должно быть позже времени начала.")
        if data.get("subject"):
            for question in data.get("questions") or []:
                if question.subject_id != data["subject"].id:
                    self.add_error("questions", "Все вопросы должны относиться к выбранному предмету.")
                    break
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.kind == "assignment":
            obj.end_time = self.cleaned_data["due_time"]
            obj.due_at = make_aware(self.cleaned_data["due_date"], self.cleaned_data["due_time"])
            obj.questions_count = 0
        elif self.cleaned_data.get("questions"):
            obj.questions_count = len(self.cleaned_data["questions"])  
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name", "subject"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(course__in=my_courses(user))
        self.fields["subject"].empty_label = "Все предметы"


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["subject", "tag", "text", "marks"]
        widgets = {"text": forms.Textarea(attrs={"rows": 4}),
                   "marks": forms.NumberInput(attrs={"min": 1, "max": 100})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tag"].queryset = visible_tags(user)
        self.fields["subject"].queryset = Subject.objects.filter(course__in=my_courses(user))

    def clean_marks(self):
        if self.cleaned_data["marks"] < 1:
            raise forms.ValidationError("Вопрос должен давать не меньше 1 балла.")
        return self.cleaned_data["marks"]

class CourseStepForm(forms.Form):
    course = forms.ModelChoiceField(Course.objects.none(), widget=forms.RadioSelect, empty_label=None,
                                    label="Курс", error_messages={"required": "Выберите курс."})

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = my_courses(user)


class SubjectStepForm(forms.Form):
    subject = forms.ModelChoiceField(Subject.objects.none(), widget=forms.RadioSelect, empty_label=None,
                                     label="Предмет", error_messages={"required": "Выберите предмет."})

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(course=course)


class BatchesStepForm(forms.Form):
    batches = forms.ModelMultipleChoiceField(
        Batch.objects.none(), widget=forms.CheckboxSelectMultiple, label="Группы",
        error_messages={"required": "Выберите хотя бы одну группу."})

    def __init__(self, *args, user=None, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batches"].queryset = Batch.objects.filter(teacher=user, course=course)


class DetailsStepForm(forms.Form):
    title = forms.CharField(max_length=200, label="Название")
    questions_count = forms.IntegerField(min_value=1, max_value=500, initial=10, label="Количество вопросов")
    passing_percentage = forms.IntegerField(min_value=0, max_value=100, initial=70, label="Проходной процент",                                            widget=forms.NumberInput(attrs={"min": 0, "max": 100}))
    max_marks = forms.IntegerField(min_value=1, max_value=10000, initial=50, label="Максимальный балл")
    date = forms.DateField(label="Дата проведения", widget=date_input())
    start_time = forms.TimeField(label="Время начала", widget=time_input())
    end_time = forms.TimeField(label="Время окончания", widget=time_input())
    due_date = forms.DateField(label="Срок сдачи: дата", widget=date_input())
    due_time = forms.TimeField(label="Срок сдачи: время", widget=time_input())

    def __init__(self, *args, kind="quiz", **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        if kind == "assignment":
            for name in ("questions_count", "passing_percentage", "end_time"):
                del self.fields[name]
            self.fields["date"].label = "Дата выдачи"
            self.fields["start_time"].label = "Время выдачи"
            self.order_fields(["title", "max_marks", "date", "start_time", "due_date", "due_time"])
        else:
            for name in ("max_marks", "due_date", "due_time"):
                del self.fields[name]

    def clean(self):
        data = super().clean()
        if self.kind == "assignment":
            start, day = data.get("start_time"), data.get("date")
            due_date, due_time = data.get("due_date"), data.get("due_time")
            if start and day and due_date and due_time and make_aware(due_date, due_time) <= make_aware(day, start):
                self.add_error("due_date", "Срок сдачи должен быть позже начала задания.")
        else:
            start, end = data.get("start_time"), data.get("end_time")
            if start and end and end <= start:
                self.add_error("end_time", "Время окончания должно быть позже времени начала.")
        return data


class QuestionsStepForm(forms.Form):
    questions = forms.ModelMultipleChoiceField(Question.objects.none(), required=False, label="Вопросы",                                               widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, user=None, subject=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["questions"].queryset = Question.objects.filter(teacher=user, subject=subject)
        self.fields["questions"].label_from_instance = lambda q: f"{q.text[:90]} (баллов: {q.marks})"


class TagsCompositionForm(forms.Form):
    def __init__(self, *args, subject=None, user=None, initial_percents=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial_percents = initial_percents or {}
        self.tags = list(visible_tags(user).filter(Q(subject=subject) | Q(subject__isnull=True)))
        counts = dict(Question.objects.filter(subject=subject, tag__in=self.tags)
                      .values_list("tag").annotate(n=Count("id")))
        for tag in self.tags:
            self.fields[f"tag_{tag.pk}"] = forms.IntegerField(
                label=f"{tag.name} (вопросов в банке: {counts.get(tag.pk, 0)})",
                min_value=0, max_value=100, required=False,
                initial=initial_percents.get(tag.pk, 0),
                widget=forms.NumberInput(attrs={"min": 0, "max": 100}))

    def clean(self):
        data = super().clean()
        if not self.errors:
            total = sum(data.get(f"tag_{t.pk}") or 0 for t in self.tags)
            if total != 100:
                raise forms.ValidationError(f"Сумма процентов должна быть равна 100 (сейчас {total}).")
        return data

    def percents(self):
        result = {}
        for tag in self.tags:
            value = self.cleaned_data.get(f"tag_{tag.pk}") or 0
            if value:
                result[tag.pk] = value
        return result


MAX_PDF_MB = 5


class PdfUploadForm(forms.Form):
    file = forms.FileField(label="PDF-файл")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Разрешены только файлы PDF.")
        if f.size > MAX_PDF_MB * 1024 * 1024:
            raise forms.ValidationError(f"Файл слишком большой (максимум {MAX_PDF_MB} МБ).")
        if f.read(5) != b"%PDF-":
            raise forms.ValidationError("Этот файл не является настоящим PDF.")
        f.seek(0)
        return f


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        labels = {"first_name": "Имя", "last_name": "Фамилия", "email": "Электронная почта"}
