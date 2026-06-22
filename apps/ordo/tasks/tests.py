from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import models
from django.test import TestCase
from django.urls import reverse
from django.utils.text import slugify

from apps.ordo.organizations.models import Company, Department, DepartmentType
from apps.ordo.workspaces.models import Project, Workspace, WorkspaceAccessGrant

from .models import Task, TaskAssignee, TaskBoard, TaskColumn, TaskObserver
from .services import DEFAULT_TASK_COLUMNS


def _create_department(company, name):
    department_type, _ = DepartmentType.objects.get_or_create(
        code=slugify(name, allow_unicode=True),
        defaults={"name": name},
    )
    return Department.objects.create(company=company, type=department_type, name=name)


class TaskBoardModelTests(TestCase):
    def test_inbox_board_does_not_require_department_or_project(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        board = TaskBoard.objects.get(
            workspace=workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )

        board.full_clean()

    def test_department_board_must_belong_to_workspace_company(self):
        workspace_company = Company.objects.create(name="Altyn Group")
        other_company = Company.objects.create(name="Other Company")
        workspace = Workspace.objects.create(
            company=workspace_company,
            name="Altyn Group",
            slug="altyn-group",
        )
        department = _create_department(company=other_company, name="Finance")

        board = TaskBoard(
            workspace=workspace,
            department=department,
            board_type=TaskBoard.BoardType.DEPARTMENT,
            name="Finance",
        )

        with self.assertRaises(ValidationError):
            board.full_clean()

    def test_project_board_must_belong_to_project_workspace(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        other_workspace = Workspace.objects.create(name="North Metals", slug="north-metals")
        project = Project.objects.create(
            workspace=other_workspace,
            name="Pump Procurement",
            slug="pump-procurement",
        )

        board = TaskBoard(
            workspace=workspace,
            project=project,
            board_type=TaskBoard.BoardType.PROJECT,
            name="Pump Procurement",
        )

        with self.assertRaises(ValidationError):
            board.full_clean()


class TaskModelTests(TestCase):
    def test_task_must_use_column_from_its_board(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        board = TaskBoard.objects.get(
            workspace=workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        other_board = TaskBoard.objects.get(
            workspace=workspace,
            board_type=TaskBoard.BoardType.WORKSPACE,
        )
        column = other_board.columns.get(key="todo")

        task = Task(
            workspace=workspace,
            board=board,
            column=column,
            title="Review supplier pricing",
        )

        with self.assertRaises(ValidationError):
            task.full_clean()

    def test_task_accepts_multiple_assignees(self):
        user_model = get_user_model()
        first_user = user_model.objects.create_user(email="first@example.com", password="pass")
        second_user = user_model.objects.create_user(email="second@example.com", password="pass")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        board = TaskBoard.objects.get(
            workspace=workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        column = board.columns.get(key="todo")

        task = Task.objects.create(
            workspace=workspace,
            board=board,
            column=column,
            title="Prepare drilling equipment tender",
        )
        TaskAssignee.objects.create(task=task, user=first_user)
        TaskAssignee.objects.create(task=task, user=second_user)

        self.assertCountEqual(
            task.assignees.values_list("user_id", flat=True),
            [first_user.id, second_user.id],
        )


class TaskBoardAutomationTests(TestCase):
    def test_workspace_create_creates_inbox_and_workspace_boards(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        boards = TaskBoard.objects.filter(workspace=workspace)

        self.assertEqual(boards.count(), 2)
        self.assertTrue(
            boards.filter(board_type=TaskBoard.BoardType.INBOX, name="Inbox").exists()
        )
        self.assertTrue(
            boards.filter(board_type=TaskBoard.BoardType.WORKSPACE, name="Workspace").exists()
        )
        self.assertEqual(
            TaskColumn.objects.filter(board__workspace=workspace).count(),
            2 * len(DEFAULT_TASK_COLUMNS),
        )

    def test_company_workspace_create_creates_department_boards(self):
        company = Company.objects.create(name="Altyn Group")
        finance = _create_department(company=company, name="Finance")
        logistics = _create_department(company=company, name="Logistics")

        workspace = Workspace.objects.create(
            company=company,
            name="Altyn Group",
            slug="altyn-group",
        )

        self.assertTrue(
            TaskBoard.objects.filter(
                workspace=workspace,
                department=finance,
                board_type=TaskBoard.BoardType.DEPARTMENT,
                name="Finance",
            ).exists()
        )
        self.assertTrue(
            TaskBoard.objects.filter(
                workspace=workspace,
                department=logistics,
                board_type=TaskBoard.BoardType.DEPARTMENT,
                name="Logistics",
            ).exists()
        )
        self.assertEqual(TaskBoard.objects.filter(workspace=workspace).count(), 4)

    def test_custom_workspace_does_not_create_department_boards(self):
        company = Company.objects.create(name="Altyn Group")
        _create_department(company=company, name="Finance")

        workspace = Workspace.objects.create(name="Cross Company Project", slug="cross-company")

        self.assertFalse(
            TaskBoard.objects.filter(
                workspace=workspace,
                board_type=TaskBoard.BoardType.DEPARTMENT,
            ).exists()
        )

    def test_project_create_creates_project_board(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        project = Project.objects.create(
            workspace=workspace,
            name="Pump Procurement",
            slug="pump-procurement",
        )

        board = TaskBoard.objects.get(
            workspace=workspace,
            project=project,
            board_type=TaskBoard.BoardType.PROJECT,
        )
        self.assertEqual(board.name, "Pump Procurement")
        self.assertEqual(board.columns.count(), len(DEFAULT_TASK_COLUMNS))

    def test_department_create_creates_board_only_in_company_workspace(self):
        company = Company.objects.create(name="Altyn Group")
        company_workspace = Workspace.objects.create(
            company=company,
            name="Altyn Group",
            slug="altyn-group",
        )
        custom_workspace = Workspace.objects.create(name="Custom Workspace", slug="custom")

        department = _create_department(company=company, name="Finance")

        self.assertTrue(
            TaskBoard.objects.filter(
                workspace=company_workspace,
                department=department,
                board_type=TaskBoard.BoardType.DEPARTMENT,
            ).exists()
        )
        self.assertFalse(
            TaskBoard.objects.filter(
                workspace=custom_workspace,
                department=department,
                board_type=TaskBoard.BoardType.DEPARTMENT,
            ).exists()
        )

    def test_sync_task_boards_is_idempotent(self):
        company = Company.objects.create(name="Altyn Group")
        _create_department(company=company, name="Finance")
        company_workspace = Workspace.objects.create(
            company=company,
            name="Altyn Group",
            slug="altyn-group",
        )
        custom_workspace = Workspace.objects.create(name="Custom Workspace", slug="custom")
        Project.objects.create(
            workspace=company_workspace,
            name="Tax Review",
            slug="tax-review",
        )
        Project.objects.create(
            workspace=custom_workspace,
            name="Drilling Equipment Tender",
            slug="drilling-equipment-tender",
        )
        TaskBoard.objects.all().delete()

        output = StringIO()
        call_command("sync_task_boards", stdout=output)
        call_command("sync_task_boards", stdout=output)

        self.assertEqual(TaskBoard.objects.count(), 7)
        self.assertEqual(TaskColumn.objects.count(), 7 * len(DEFAULT_TASK_COLUMNS))

    def test_seed_task_demo_creates_tasks_for_every_board_idempotently(self):
        user_model = get_user_model()
        user_model.objects.create_user(email="first@example.com", password="pass")
        user_model.objects.create_user(email="second@example.com", password="pass")
        user_model.objects.create_user(email="third@example.com", password="pass")
        company = Company.objects.create(name="Altyn Group")
        _create_department(company=company, name="Finance")
        company_workspace = Workspace.objects.create(
            company=company,
            name="Altyn Group",
            slug="altyn-group",
        )
        custom_workspace = Workspace.objects.create(name="Custom Workspace", slug="custom")
        Project.objects.create(
            workspace=company_workspace,
            name="Tax Review",
            slug="tax-review",
        )
        Project.objects.create(
            workspace=custom_workspace,
            name="Drilling Equipment Tender",
            slug="drilling-equipment-tender",
        )

        output = StringIO()
        call_command("seed_task_demo", stdout=output)
        call_command("seed_task_demo", stdout=output)

        expected_boards = 7
        expected_tasks = expected_boards * len(DEFAULT_TASK_COLUMNS)
        self.assertEqual(TaskBoard.objects.count(), expected_boards)
        self.assertEqual(Task.objects.count(), expected_tasks)
        self.assertEqual(TaskAssignee.objects.count(), expected_tasks)
        self.assertGreater(TaskObserver.objects.count(), 0)
        self.assertFalse(
            Task.objects.exclude(workspace_id=models.F("board__workspace_id")).exists()
        )


class TaskBackendActionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(email="member@example.com", password="pass")
        self.assignee = user_model.objects.create_user(
            email="assignee@example.com",
            password="pass",
        )
        self.observer = user_model.objects.create_user(email="observer@example.com", password="pass")
        self.workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        WorkspaceAccessGrant.objects.create(workspace=self.workspace, user=self.user)
        self.client.force_login(self.user)
        self.inbox_board = TaskBoard.objects.get(
            workspace=self.workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        self.workspace_board = TaskBoard.objects.get(
            workspace=self.workspace,
            board_type=TaskBoard.BoardType.WORKSPACE,
        )

    def test_create_task_uses_selected_board_and_default_todo_column(self):
        response = self.client.post(
            f"{reverse('workspaces:task-create')}?workspace={self.workspace.slug}&board={self.inbox_board.id}",
            {
                "title": "Review reagent pricing",
                "description": "Compare supplier offers.",
                "board": self.inbox_board.id,
                "priority": Task.Priority.HIGH,
                "due_date": "2026-07-01",
                "assignees": [self.assignee.id],
                "observers": [self.observer.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"board={self.inbox_board.id}", response["Location"])

        task = Task.objects.get(title="Review reagent pricing")
        self.assertEqual(task.workspace, self.workspace)
        self.assertEqual(task.board, self.inbox_board)
        self.assertEqual(task.column.key, "todo")
        self.assertEqual(task.created_by, self.user)
        self.assertTrue(task.assignees.filter(user=self.assignee).exists())
        self.assertTrue(task.observers.filter(user=self.observer).exists())

    def test_edit_task_can_move_board_column_and_people(self):
        todo_column = self.inbox_board.columns.get(key="todo")
        review_column = self.workspace_board.columns.get(key="review")
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.inbox_board,
            column=todo_column,
            title="Prepare tender package",
            created_by=self.user,
        )

        response = self.client.post(
            f"{reverse('workspaces:task-edit', args=[task.id])}?workspace={self.workspace.slug}",
            {
                "title": "Prepare updated tender package",
                "description": "Move to workspace review.",
                "board": self.workspace_board.id,
                "column": review_column.id,
                "priority": Task.Priority.URGENT,
                "due_date": "2026-07-02",
                "assignees": [self.assignee.id],
                "observers": [self.observer.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"board={self.workspace_board.id}", response["Location"])

        task.refresh_from_db()
        self.assertEqual(task.title, "Prepare updated tender package")
        self.assertEqual(task.board, self.workspace_board)
        self.assertEqual(task.column, review_column)
        self.assertEqual(task.priority, Task.Priority.URGENT)
        self.assertTrue(task.assignees.filter(user=self.assignee).exists())
        self.assertTrue(task.observers.filter(user=self.observer).exists())

    def test_edit_task_without_people_fields_keeps_existing_people(self):
        todo_column = self.inbox_board.columns.get(key="todo")
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.inbox_board,
            column=todo_column,
            title="Prepare tender package",
            created_by=self.user,
        )
        TaskAssignee.objects.create(
            task=task,
            user=self.assignee,
            assigned_by=self.user,
        )
        TaskObserver.objects.create(
            task=task,
            user=self.observer,
            added_by=self.user,
        )

        response = self.client.post(
            f"{reverse('workspaces:task-edit', args=[task.id])}?workspace={self.workspace.slug}",
            {
                "title": "Prepare updated tender package",
                "description": "Keep people untouched.",
                "board": self.inbox_board.id,
                "column": todo_column.id,
                "priority": Task.Priority.HIGH,
                "due_date": "2026-07-02",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(task.assignees.filter(user=self.assignee).exists())
        self.assertTrue(task.observers.filter(user=self.observer).exists())

    def test_edit_task_with_empty_people_fields_clears_existing_people(self):
        todo_column = self.inbox_board.columns.get(key="todo")
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.inbox_board,
            column=todo_column,
            title="Prepare tender package",
            created_by=self.user,
        )
        TaskAssignee.objects.create(
            task=task,
            user=self.assignee,
            assigned_by=self.user,
        )
        TaskObserver.objects.create(
            task=task,
            user=self.observer,
            added_by=self.user,
        )

        response = self.client.post(
            f"{reverse('workspaces:task-edit', args=[task.id])}?workspace={self.workspace.slug}",
            {
                "title": "Prepare updated tender package",
                "description": "Clear people.",
                "board": self.inbox_board.id,
                "column": todo_column.id,
                "priority": Task.Priority.HIGH,
                "due_date": "2026-07-02",
                "assignees__present": "1",
                "observers__present": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(task.assignees.exists())
        self.assertFalse(task.observers.exists())

    def test_move_task_updates_column_and_position(self):
        todo_column = self.inbox_board.columns.get(key="todo")
        review_column = self.inbox_board.columns.get(key="review")
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.inbox_board,
            column=todo_column,
            title="Prepare tender package",
            created_by=self.user,
            position=0,
        )

        response = self.client.post(
            f"{reverse('workspaces:task-move', args=[task.id])}?workspace={self.workspace.slug}",
            {
                "column": review_column.id,
                "position": "4",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        task.refresh_from_db()
        self.assertEqual(task.column, review_column)
        self.assertEqual(task.position, 4)

    def test_move_task_rejects_column_from_other_board(self):
        todo_column = self.inbox_board.columns.get(key="todo")
        other_column = self.workspace_board.columns.get(key="review")
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.inbox_board,
            column=todo_column,
            title="Prepare tender package",
            created_by=self.user,
            position=0,
        )

        response = self.client.post(
            f"{reverse('workspaces:task-move', args=[task.id])}?workspace={self.workspace.slug}",
            {
                "column": other_column.id,
                "position": "4",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["ok"], False)
        task.refresh_from_db()
        self.assertEqual(task.column, todo_column)
        self.assertEqual(task.position, 0)
