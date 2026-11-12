
from django.contrib.auth.models import User
from django.db import models


class Course(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name="own_courses", verbose_name="Владелец курса")
    name = models.CharField(max_length=200, verbose_name="Название курса")
    description = models.TextField(blank=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Subject(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="subjects", verbose_name="Курс")
    name = models.CharField(max_length=100, verbose_name="Название предмета")
    semester = models.PositiveSmallIntegerField(default=1, verbose_name="Семестр")

    class Meta:
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"
        ordering = ["semester", "name"]

    def __str__(self):
        return f"{self.name} (семестр {self.semester})"


class Tag(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="tags", verbose_name="Преподаватель")
    name = models.CharField(max_length=100, verbose_name="Название тега")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="tags", null=True, blank=True, verbose_name="Предмет")

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"

    def __str__(self):
        return self.name


class Batch(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="batches", verbose_name="Преподаватель")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="batches", verbose_name="Курс")
    name = models.CharField(max_length=100, verbose_name="Название группы")
    end_date = models.DateField(verbose_name="Дата окончания")
    subjects = models.ManyToManyField(Subject, blank=True, related_name="teaching_batches", verbose_name="Предметы")

    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "Группы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Student(models.Model):
    GENDERS = [("Female", "Женский"), ("Male", "Мужской")]

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="students", verbose_name="Группа")
    full_name = models.CharField(max_length=100, verbose_name="ФИО студента")
    student_code = models.CharField(max_length=20, unique=True, verbose_name="Код студента")
    gender = models.CharField(max_length=10, choices=GENDERS, verbose_name="Пол")
    mother_name = models.CharField(max_length=100, blank=True, verbose_name="Имя матери")
    father_name = models.CharField(max_length=100, blank=True, verbose_name="Имя отца")
    course_start = models.DateField(verbose_name="Дата начала курса")
    course_end = models.DateField(verbose_name="Дата окончания курса")
    center_pincode = models.CharField(max_length=10, blank=True, verbose_name="Почтовый индекс центра")
    center_district = models.CharField(max_length=50, blank=True, verbose_name="Район центра")
    center_state = models.CharField(max_length=50, blank=True, verbose_name="Область центра")
    center_address = models.TextField(blank=True, verbose_name="Адрес центра")
    center_phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон центра")
    center_email = models.EmailField(blank=True, verbose_name="Электронная почта центра")

    class Meta:
        verbose_name = "Студент"
        verbose_name_plural = "Студенты"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class LiveClass(models.Model):
    STATUSES = [
        ("ongoing", "Идёт"),
        ("starting", "Начнётся через 60 минут"),
        ("not_started", "Не началось"),
        ("completed", "Завершено"),
    ]

    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="live_classes", verbose_name="Преподаватель")
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="live_classes", verbose_name="Группа")
    title = models.CharField(max_length=200, verbose_name="Название занятия")
    date = models.DateField(verbose_name="Дата занятия")
    time = models.TimeField(verbose_name="Время занятия")
    status = models.CharField(max_length=20, choices=STATUSES, default="not_started", verbose_name="Статус")
    meeting_link = models.URLField(blank=True, verbose_name="Ссылка на занятие")

    class Meta:
        verbose_name = "Онлайн-занятие"
        verbose_name_plural = "Онлайн-занятия"
        ordering = ["date", "time"]

    def __str__(self):
        return self.title


class Attendance(models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name="attendance", verbose_name="Онлайн-занятие")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance", verbose_name="Студент")
    present = models.BooleanField(default=True, verbose_name="Присутствовал")

    class Meta:
        verbose_name = "Посещаемость"
        verbose_name_plural = "Посещаемость"
        unique_together = ["live_class", "student"]

    def __str__(self):
        return f"{self.student} - {self.live_class}"


class Task(models.Model):
    STATUSES = [
        ("not_started", "Не начато"),
        ("ongoing", "В процессе"),
        ("completed", "Завершено"),
        ("missed", "Просрочено"),
    ]

    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks", verbose_name="Преподаватель")
    title = models.CharField(max_length=255, verbose_name="Название задачи")
    description = models.TextField(blank=True, verbose_name="Описание")
    assigned_by = models.CharField(max_length=100, blank=True, verbose_name="Кем назначено")
    assigned_at = models.DateTimeField(verbose_name="Дата и время назначения")
    due_at = models.DateTimeField(verbose_name="Срок выполнения")
    status = models.CharField(max_length=20, choices=STATUSES, default="not_started", verbose_name="Статус")

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ["due_at"]

    def __str__(self):
        return self.title


class Assessment(models.Model):

    KINDS = [("quiz", "Тест"), ("exam", "Экзамен"), ("assignment", "Задание")]

    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assessments", verbose_name="Преподаватель")
    kind = models.CharField(max_length=20, choices=KINDS, verbose_name="Тип оценивания")
    title = models.CharField(max_length=200, verbose_name="Название")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assessments", verbose_name="Курс")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assessments", verbose_name="Предмет")
    batches = models.ManyToManyField(Batch, blank=True, related_name="assessments", verbose_name="Группы")
    questions_count = models.PositiveIntegerField(default=10, verbose_name="Количество вопросов")
    passing_percentage = models.PositiveSmallIntegerField(default=40, verbose_name="Проходной процент")
    date = models.DateField(verbose_name="Дата проведения")
    start_time = models.TimeField(verbose_name="Время начала")
    end_time = models.TimeField(verbose_name="Время окончания")
    max_marks = models.PositiveIntegerField(default=0, verbose_name="Максимальный балл")
    due_at = models.DateTimeField(null=True, blank=True, verbose_name="Срок сдачи")
    questions = models.ManyToManyField("Question", blank=True, related_name="assessments", verbose_name="Вопросы")

    class Meta:
        verbose_name = "Оценивание"
        verbose_name_plural = "Оценивания"
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    @property
    def total_marks(self):
        if self.kind == "assignment":
            return self.max_marks
        picked = self.questions.aggregate(total=models.Sum("marks"))["total"]
        return picked if picked else self.questions_count


class AssessmentTag(models.Model):

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="tag_parts", verbose_name="Оценивание")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name="Тег")
    percent = models.PositiveSmallIntegerField(verbose_name="Процент")

    class Meta:
        verbose_name = "Тег оценивания"
        verbose_name_plural = "Теги оценивания"

    def __str__(self):
        return f"{self.tag} {self.percent}%"


class Attachment(models.Model):

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="attachments", verbose_name="Оценивание")
    file = models.FileField(upload_to="assignments/%Y/%m/", verbose_name="Файл")
    name = models.CharField(max_length=200, verbose_name="Название файла")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    class Meta:
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.name


class Question(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="questions", verbose_name="Преподаватель")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="questions", verbose_name="Предмет")
    tag = models.ForeignKey(Tag, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Тег")
    text = models.TextField(verbose_name="Текст вопроса")
    marks = models.PositiveSmallIntegerField(default=1, verbose_name="Баллы")

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
        ordering = ["-id"]

    def __str__(self):
        return self.text[:60]


class Result(models.Model):
    STATUSES = [("passed", "Сдано"), ("failed", "Не сдано"), ("unattempted", "Не выполнено")]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="results", verbose_name="Студент")
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="results", verbose_name="Оценивание")
    status = models.CharField(max_length=20, choices=STATUSES, verbose_name="Статус")
    score = models.PositiveSmallIntegerField(default=0, verbose_name="Набранные баллы")

    class Meta:
        verbose_name = "Результат"
        verbose_name_plural = "Результаты"
        unique_together = ["student", "assessment"]

    def __str__(self):
        return f"{self.student} - {self.assessment} ({self.status})"
