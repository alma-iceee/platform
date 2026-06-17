from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from apps.ordo.organizations.models import Company, Department
from apps.ordo.workspaces.models import Project, Workspace

from .models import Task, TaskBoard, TaskColumn
from .services import DEFAULT_TASK_COLUMNS


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
        department = Department.objects.create(company=other_company, name="Finance")

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

    def test_task_accepts_responsible_user_and_assignees_separately(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(email="employee@example.com", password="pass")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        board = TaskBoard.objects.get(
            workspace=workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        column = board.columns.get(key="todo")

        task = Task(
            workspace=workspace,
            board=board,
            column=column,
            title="Prepare drilling equipment tender",
            responsible=user,
        )

        task.full_clean()


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
        finance = Department.objects.create(company=company, name="Finance")
        logistics = Department.objects.create(company=company, name="Logistics")

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
        Department.objects.create(company=company, name="Finance")

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

        department = Department.objects.create(company=company, name="Finance")

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
        Department.objects.create(company=company, name="Finance")
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
