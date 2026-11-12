import datetime as dt

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import (
    Assessment, AssessmentTag, Attendance, Batch, Course, LiveClass,
    Question, Result, Student, Subject, Tag, Task,
)

COURSE = "Программная инженерия"
SUBJECTS = ["Основы программирования", "Компьютерные сети", "Язык Python", "Язык C++",
            "Объектно-ориентированное программирование", "Основы веб-вёрстки", "Компьютерная графика"]
CLASS_TITLE = "Как создать массив и какие бывают его типы в C++"
TASK_TITLE = "Добавить тест для студентов группы ПО-21 по предмету «Основы программирования»"


class Command(BaseCommand):
    help = "Создаёт демо-данные: преподаватель 'ainura' (пароль ainura123) и второй преподаватель 'bakyt'."

    def handle(self, *args, **options):
        if User.objects.filter(username="ainura").exists():
            self.stdout.write("Демо-данные уже существуют, ничего не делаю.")
            return

        ainura = User.objects.create_user("ainura", "ainura@example.com", "ainura123",
                                          first_name="Айнура", last_name="Исакова")
        bakyt = User.objects.create_user("bakyt", "bakyt@example.com", "bakyt12345",
                                         first_name="Бакыт", last_name="Сыдыков")

        course = Course.objects.create(teacher=ainura, name=COURSE,
                                       description="Четырёхгодичная программа подготовки разработчиков.")
        subjects = []
        for sem in (1, 2, 3, 4):
            for name in SUBJECTS[:4 + (sem % 3)]:
                subjects.append(Subject.objects.create(course=course, name=name, semester=sem))
        sem1 = [s for s in subjects if s.semester == 1]
        tags = [Tag.objects.create(name=n) for n in
                ["Текущие события", "Логическое мышление", "Основы информатики", "Основы естествознания"]]

        batch1 = Batch.objects.create(teacher=ainura, course=course, name="ПО-21", end_date=dt.date(2027, 1, 2))
        batch2 = Batch.objects.create(teacher=ainura, course=course, name="ПО-22", end_date=dt.date(2027, 1, 2))
        batch1.subjects.set(sem1)
        batch2.subjects.set(sem1[:2])
        other_batch = Batch.objects.create(teacher=bakyt, course=course, name="ИС-31", end_date=dt.date(2027, 6, 1))

        # онлайн-занятия: по одному на каждый статус и история
        today = dt.date.today()
        LiveClass.objects.create(teacher=ainura, batch=batch1, title=CLASS_TITLE, date=today,
                                 time=dt.time(12, 40), status="ongoing", meeting_link="https://meet.example.com/abc")
        LiveClass.objects.create(teacher=ainura, batch=batch2, title=CLASS_TITLE, date=today,
                                 time=dt.time(13, 40), status="starting", meeting_link="https://meet.example.com/def")
        LiveClass.objects.create(teacher=ainura, batch=batch2, title=CLASS_TITLE, date=today + dt.timedelta(days=1),
                                 time=dt.time(13, 40), status="not_started", meeting_link="https://meet.example.com/ghi")
        history = [LiveClass.objects.create(teacher=ainura, batch=batch1, title=CLASS_TITLE,
                                            date=today - dt.timedelta(days=i), time=dt.time(12, 40),
                                            status="completed") for i in range(1, 7)]
        LiveClass.objects.create(teacher=bakyt, batch=other_batch, title="Закрытое занятие Бакыта", date=today,
                                 time=dt.time(9, 0), status="not_started")

        # задачи
        now = timezone.now()
        for status in ["not_started", "not_started", "ongoing", "ongoing", "completed"]:
            Task.objects.create(teacher=ainura, title=TASK_TITLE, assigned_by="Нурлан Асанов", status=status,
                                description="Подготовить вопросы, проверить сложность и назначить дату проведения. " * 3,
                                assigned_at=now - dt.timedelta(days=1), due_at=now + dt.timedelta(days=2))
        Task.objects.create(teacher=bakyt, title="Задача Бакыта", status="ongoing",
                            assigned_at=now, due_at=now + dt.timedelta(days=1))

        # студенты
        first = Student.objects.create(
            batch=batch1, full_name="Адилет Токтогулов", student_code="TIPSG5682", gender="Male",
            mother_name="Гульнара Токтогулова", father_name="Марат Токтогулов",
            course_start=dt.date(2023, 1, 17), course_end=dt.date(2025, 1, 17),
            center_pincode="720001", center_district="Первомайский", center_state="Бишкек",
            center_address="ул. Токтогула, 116, Бишкек",
            center_phone="+996 312 00 00 00", center_email="center.bishkek@example.com")
        students = [first]
        for i, name in enumerate(["Айгерим Бекова", "Эльдар Жумабаев", "Назира Осмонова", "Руслан Ким"]):
            students.append(Student.objects.create(
                batch=batch1 if i < 3 else batch2, full_name=name, student_code=f"TIPSG{5700 + i}",
                gender="Female" if i % 2 == 0 else "Male", course_start=dt.date(2023, 1, 17),
                course_end=dt.date(2025, 1, 17), center_district="Первомайский", center_state="Бишкек"))
        Student.objects.create(batch=other_batch, full_name="Студент Бакыта", student_code="TIPSG9999",
                               gender="Male", course_start=dt.date(2023, 1, 17), course_end=dt.date(2025, 1, 17))

        for i, cls in enumerate(history):
            for j, st in enumerate(students):
                if st.batch_id == batch1.id:
                    Attendance.objects.create(live_class=cls, student=st, present=(i + j) % 5 != 0)

        # тесты, экзамены, задания (предстоящие и из истории)
        def make(kind, title, days, subject):
            a = Assessment.objects.create(
                teacher=ainura, kind=kind, title=title, course=course, subject=subject, questions_count=50,
                passing_percentage=70, date=today + dt.timedelta(days=days),
                start_time=dt.time(9, 30), end_time=dt.time(13, 40))
            a.batches.set([batch1])
            return a

        quiz = make("quiz", "Структура C++ и Java, семестр 1", 3, sem1[1])
        for tag in tags:
            AssessmentTag.objects.create(assessment=quiz, tag=tag, percent=25)
        old_quiz = make("quiz", "Компьютерные сети для начинающих", -10, sem1[1])
        make("exam", "Структура C++ и Java, семестр 1", 5, sem1[1])
        old_exam = make("exam", "Промежуточный экзамен, семестр 1", -12, sem1[0])
        assignment = make("assignment", "Структура C++ и Java, семестр 1", 4, sem1[1])
        old_assignment = make("assignment", "Основы Python: практическая работа", -8, sem1[2])
        for work in (assignment, old_assignment):       # баллы и срок сдачи через 3 дня после выдачи
            work.questions_count = 0
            work.max_marks = 50
            work.due_at = timezone.make_aware(dt.datetime.combine(work.date + dt.timedelta(days=3), dt.time(18, 0)))
            work.save()

        statuses = ["passed", "failed", "unattempted", "passed", "failed"]
        for old in (quiz, old_exam, old_assignment, old_quiz):
            for j, st in enumerate(students):
                if st.batch_id == batch1.id:
                    s = statuses[(j + old.id) % 5]
                    Result.objects.create(student=st, assessment=old, status=s,
                                          score=0 if s == "unattempted" else (40 if s == "passed" else 15))

        for i in range(8):
            Question.objects.create(teacher=ainura, subject=sem1[1], tag=tags[i % 4], marks=[1, 2, 3, 5][i % 4],
                                   text=f"Пример вопроса {i + 1}: какой номер у уровня {i % 7 + 1} модели OSI?")
        Question.objects.create(teacher=bakyt, subject=sem1[0], tag=tags[0], text="Закрытый вопрос Бакыта")

        self.stdout.write(self.style.SUCCESS("Демо-данные созданы. Вход: ainura / ainura123"))
