from rest_framework.pagination import CursorPagination


class ProjectCursorPagination(CursorPagination):
    page_size = 6
    ordering = "-pk"
    page_size_query_param = None
