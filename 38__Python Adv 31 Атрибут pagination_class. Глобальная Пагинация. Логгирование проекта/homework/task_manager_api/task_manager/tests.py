from datetime import timedelta
import logging
from urllib.parse import urlsplit
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APITestCase
from .models import Category, Task, SubTask


class PaginationLoggingTests(APITestCase):
    def setUp(self):
        self.deadline = timezone.now()+timedelta(days=20)
        self.categories = [Category.objects.create(name=f"Category {i}") for i in range(13)]
        self.tasks = [Task.objects.create(title=f"Task {i}", description="Example", deadline=self.deadline) for i in range(13)]
        SubTask.objects.bulk_create([SubTask(task=self.tasks[0],title=f"Subtask {i}",description="Example",deadline=self.deadline) for i in range(13)])
        self.tasks[0].categories.add(self.categories[0])

    def local(self,url):
        parts=urlsplit(url)
        return parts.path+"?"+parts.query

    def test_all_collections_use_cursor_and_fixed_size(self):
        for path in ["tasks", "subtasks", "categories", "categories/count-tasks"]:
            with self.subTest(path=path):
                response=self.client.get(f"/api/{path}/?page_size=100&limit=100")
                self.assertEqual(response.status_code,200)
                self.assertEqual(len(response.data["results"]),6)
                self.assertNotIn("count",response.data)
                first=response
                ids=[]
                while True:
                    ids += [x["id"] for x in response.data["results"]]
                    self.assertLessEqual(len(response.data["results"]),6)
                    if not response.data["next"]: break
                    response=self.client.get(self.local(response.data["next"]))
                self.assertEqual(len(ids),13)
                self.assertEqual(len(set(ids)),13)
                second=self.client.get(self.local(first.data["next"]))
                back=self.client.get(self.local(second.data["previous"]))
                self.assertEqual(back.data["results"],first.data["results"])

    def test_invalid_cursor_and_empty_result(self):
        self.assertEqual(self.client.get("/api/tasks/?cursor=invalid").status_code,404)
        self.assertEqual(self.client.get("/api/tasks/?search=missing").data["results"],[])

    def test_filters_and_ordering(self):
        self.tasks[0].status="done"
        self.tasks[0].save(update_fields=["status"])
        response=self.client.get("/api/tasks/",{"status":"done","search":"Task 0","deadline":self.deadline.isoformat()})
        self.assertEqual([x["id"] for x in response.data["results"]],[self.tasks[0].pk])
        asc=self.client.get("/api/tasks/?ordering=created_at").data["results"]
        desc=self.client.get("/api/tasks/?ordering=-created_at").data["results"]
        self.assertEqual(asc[0]["id"],self.tasks[0].pk)
        self.assertEqual(desc[0]["id"],self.tasks[-1].pk)

    def test_category_soft_delete_and_count(self):
        category=self.categories[0]
        self.assertEqual(self.client.get(f"/api/categories/{category.pk}/count-tasks/").data["tasks_count"],1)
        self.assertEqual(self.client.delete(f"/api/categories/{category.pk}/").status_code,204)
        self.assertTrue(Category.all_objects.get(pk=category.pk).is_deleted)
        self.assertEqual(self.client.get(f"/api/categories/{category.pk}/").status_code,404)
        self.assertTrue(Task.objects.filter(pk=self.tasks[0].pk).exists())

    def test_crud_and_statistics(self):
        data={"title":"Created task","description":"Text","deadline":self.deadline.isoformat()}
        response=self.client.post("/api/tasks/",data,format="json")
        self.assertEqual(response.status_code,201)
        url=f"/api/tasks/{response.data['id']}/"
        self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(self.client.patch(url,{"status":"done"},format="json").status_code,200)
        self.assertEqual(self.client.put(url,data,format="json").status_code,200)
        self.assertEqual(self.client.delete(url).status_code,204)
        self.assertEqual(self.client.get("/api/tasks/statistics/").data["total_tasks"],13)

    def test_http_sql_and_console_configuration(self):
        with self.settings(DEBUG=True):
            self.client.get("/api/tasks/")
            self.client.get("/api/missing/")
        for name in ["task_manager.http","django.db.backends"]:
            for handler in logging.getLogger(name).handlers: handler.flush()
        http=(settings.LOGS_DIR/"http_logs.log").read_text()
        sql=(settings.LOGS_DIR/"db_logs.log").read_text()
        self.assertIn("GET /api/tasks/ 200",http)
        self.assertIn("GET /api/missing/ 404",http)
        self.assertIn("SELECT",sql)
        self.assertNotIn("SELECT",http)
        self.assertNotIn("GET /api/tasks/",sql)
        self.assertTrue(any(type(h) is logging.StreamHandler for h in logging.getLogger("django.server").handlers))
