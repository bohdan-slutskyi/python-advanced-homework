from django.utils import timezone
from rest_framework import serializers

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


class CategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")
        read_only_fields = ("id",)

    def create(self, validated_data):
        name = validated_data["name"]
        if Category.objects.filter(name=name).exists():
            raise serializers.ValidationError(
                {"name": "Категория с таким названием уже существует."}
            )
        return Category.objects.create(**validated_data)

    def update(self, instance, validated_data):
        name = validated_data.get("name", instance.name)
        duplicate = Category.objects.filter(name=name).exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"name": "Категория с таким названием уже существует."}
            )
        instance.name = name
        instance.save(update_fields=("name",))
        return instance


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "deadline")
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
        )
        read_only_fields = ("id", "created_at", "subtasks")


# Совместимость со списком задач из предыдущей версии проекта.
TaskSerializer = TaskCreateSerializer
