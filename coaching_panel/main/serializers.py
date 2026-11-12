import datetime

from django.utils import timezone
from rest_framework import serializers

from .models import Assessment, Batch, Course, LiveClass, Question, Student, Subject, Task


class CheckOwnBatchMixin:
    def _check_batch(self, batch):
        if batch.teacher != self.context["request"].user:
            raise serializers.ValidationError("Эта группа вам не принадлежит.")
        return batch

    def validate_batch(self, batch):
        return self._check_batch(batch)

    def validate_batches(self, batches):
        for batch in batches:
            self._check_batch(batch)
        return batches


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "name", "description"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "course", "name", "semester"]


class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = ["id", "name", "course", "end_date", "subjects"]


class StudentSerializer(CheckOwnBatchMixin, serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "id", "batch", "full_name", "student_code", "gender", "mother_name", "father_name",
            "course_start", "course_end", "center_pincode", "center_district", "center_state",
            "center_address", "center_phone", "center_email",
        ]


class LiveClassSerializer(CheckOwnBatchMixin, serializers.ModelSerializer):
    class Meta:
        model = LiveClass
        fields = ["id", "batch", "title", "date", "time", "status", "meeting_link"]


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "description", "assigned_by", "assigned_at", "due_at", "status"]


class AssessmentSerializer(CheckOwnBatchMixin, serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = [
            "id", "kind", "title", "course", "subject", "batches", "questions_count",
            "passing_percentage", "date", "start_time", "end_time", "max_marks", "due_at", "total_marks",
        ]
        read_only_fields = ["total_marks"]

    def validate(self, data):
        course = data.get("course", getattr(self.instance, "course", None))
        subject = data.get("subject", getattr(self.instance, "subject", None))
        if course and subject and subject.course_id != course.id:
            raise serializers.ValidationError("Предмет не относится к выбранному курсу.")
        if (self.instance and self.instance.kind == "assignment") or data.get("kind") == "assignment":
            due, start = data.get("due_at", getattr(self.instance, "due_at", None)), None
            day = data.get("date", getattr(self.instance, "date", None))
            start = data.get("start_time", getattr(self.instance, "start_time", None))
            if due and day and start and timezone.localtime(due).replace(tzinfo=None) <= datetime.datetime.combine(day, start):
                raise serializers.ValidationError("Срок сдачи должен быть позже начала задания.")
        return data


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "subject", "tag", "text", "marks"]
