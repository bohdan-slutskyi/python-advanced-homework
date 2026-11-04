from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Category, SubTask, Task


class SubTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTask
        fields = (
            "id",
            "title",
            "description",
            "task",
            "status",
            "deadline",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class SubTaskCreateSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SubTask
        fields = (
            "id",
            "title",
            "description",
            "task",
            "status",
            "deadline",
            "created_at",
        )
        read_only_fields = ("id",)


class CategorySerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(queryset=Category.all_objects.all())],
    )

    class Meta:
        model = Category
        fields = ("id", "name", "is_deleted", "deleted_at")
        read_only_fields = ("id", "is_deleted", "deleted_at")


CategoryCreateSerializer = CategorySerializer


class TaskCreateSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all(), required=False,
    )
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "deadline", "created_at", "categories")
        read_only_fields = ("id",)

    def validate_deadline(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Срок выполнения должен быть в будущем."
            )
        return value


class TaskDetailSerializer(serializers.ModelSerializer):
    subtasks = SubTaskSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "description",
            "status",
            "deadline",
            "created_at",
            "subtasks",
            "categories",
        )
        read_only_fields = ("id", "created_at", "subtasks")


# Совместимость со списком задач из предыдущей версии проекта.
TaskSerializer = TaskCreateSerializer
