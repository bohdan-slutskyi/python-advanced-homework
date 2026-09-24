from django.contrib import admin

from .models import Category, SubTask, Task


admin.site.register(Task)
admin.site.register(SubTask)
admin.site.register(Category)
