from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import models
from django.test import TestCase
from django.urls import reverse
from django.utils.text import slugify

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Company, Department, DepartmentType
from apps.ordo.workspaces.models import (
    Project,
    Workspace,
    WorkspaceAccessGrant,
    WorkspaceTeam,
    WorkspaceTeamMember,
)

from .models import (
    Task,
    TaskAssignee,
    TaskBoard,
    TaskColumn,
    TaskComment,
    TaskCommentAttachment,
    TaskDiscussion,
    TaskDiscussionMessage,
    TaskDiscussionMessageAttachment,
    TaskObserver,
)
from .permissions import (
    can_create_task,
    can_edit_task,
    can_manage_task_participants,
    can_move_task,
)
from .services import DEFAULT_TASK_COLUMNS, DEMO_DISCUSSION_MESSAGES, DEMO_TASK_COMMENTS


def _create_department(company, name):
    department_type, _ = DepartmentType.objects.get_or_create(
        code=slugify(name, allow_unicode=True),
        defaults={"name": name},
    )
    return Department.objects.create(company=company, type=department_type, name=name)


class TaskPermissionPolicyTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.ceo = user_model.objects.create_user(
            email="task-policy-ceo@example.com",
            password="pass",
            system_role="ceo",
        )
        self.director = user_model.objects.create_user(
            email="task-policy-director@example.com",
            password="pass",
        )
        self.chief = user_model.objects.create_user(
            email="task-policy-chief@example.com",
            password="pass",
        )
        self.member = user_model.objects.create_user(
            email="task-policy-member@example.com",
            password="pass",
        )

        self.company = Company.objects.create(name="Task Policy Company")
        self.other_company = Company.objects.create(name="Other Task Policy Company")
        self.department = _create_department(self.company, "Policy Finance")
        self.other_department = _create_department(self.company, "Policy Logistics")

        CompanyMembership.objects.create(
            user=self.director,
            company=self.company,
            role=CompanyMembership.Role.DIRECTOR,
        )
        for user in (self.chief, self.member):
            CompanyMembership.objects.create(
                user=user,
                company=self.company,
                role=CompanyMembership.Role.MEMBER,
            )
        DepartmentMembership.objects.create(
            user=self.chief,
            department=self.department,
            role=DepartmentMembership.Role.CHIEF,
        )
        DepartmentMembership.objects.create(
            user=self.member,
            department=self.department,
            role=DepartmentMembership.Role.MEMBER,
        )

        self.workspace = Workspace.objects.create(
            company=self.company,
            name="Task Policy Workspace",
            slug="task-policy-workspace",
        )
        self.other_workspace = Workspace.objects.create(
            company=self.other_company,
            name="Other Task Policy Workspace",
            slug="other-task-policy-workspace",
        )
        self.team = WorkspaceTeam.objects.create(
            workspace=self.workspace,
            name="Policy Project Team",
            slug="policy-project-team",
        )
        department_grant, _ = WorkspaceAccessGrant.objects.get_or_create(
            workspace=self.workspace,
            department=self.department,
            defaults={"role": WorkspaceAccessGrant.Role.MEMBER},
        )
        WorkspaceTeamMember.objects.get_or_create(
            team=self.team,
            access_grant=department_grant,
        )
        self.project = Project.objects.create(
            workspace=self.workspace,
            team=self.team,
            name="Policy Project",
            slug="policy-project",
        )

        self.inbox_board = TaskBoard.objects.get(
            workspace=self.workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        self.department_board = TaskBoard.objects.get(
            workspace=self.workspace,
            department=self.department,
        )
        self.other_department_board = TaskBoard.objects.get(
            workspace=self.workspace,
            department=self.other_department,
        )
        self.project_board = TaskBoard.objects.get(project=self.project)
        self.other_company_board = TaskBoard.objects.get(
            workspace=self.other_workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )

    def _task(self, board, title):
        return Task.objects.create(
            workspace=board.workspace,
            board=board,
            column=board.columns.get(key="todo"),
            title=title,
        )

    def test_ceo_can_fully_manage_tasks_on_every_board(self):
        for board in (self.inbox_board, self.department_board, self.project_board):
            with self.subTest(board=board.id):
                task = self._task(board, f"CEO task {board.id}")
                self.assertTrue(can_create_task(self.ceo, board))
                self.assertTrue(can_edit_task(self.ceo, task))
                self.assertTrue(can_manage_task_participants(self.ceo, task))
                self.assertTrue(can_move_task(self.ceo, task))

    def test_company_director_can_fully_manage_only_own_company_tasks(self):
        own_task = self._task(self.inbox_board, "Director own-company task")
        other_task = self._task(self.other_company_board, "Director other-company task")

        self.assertTrue(can_create_task(self.director, self.inbox_board))
        self.assertTrue(can_edit_task(self.director, own_task))
        self.assertTrue(can_manage_task_participants(self.director, own_task))
        self.assertTrue(can_move_task(self.director, own_task))
        self.assertFalse(can_create_task(self.director, self.other_company_board))
        self.assertFalse(can_edit_task(self.director, other_task))
        self.assertFalse(can_move_task(self.director, other_task))

    def test_chief_fully_manages_own_department_scope_and_moves_other_visible_tasks(self):
        department_task = self._task(self.department_board, "Chief department task")
        project_task = self._task(self.project_board, "Chief project task")
        inbox_task = self._task(self.inbox_board, "Chief inbox task")
        other_department_task = self._task(
            self.other_department_board,
            "Chief other-department task",
        )

        for task in (department_task, project_task):
            with self.subTest(task=task.id):
                self.assertTrue(can_create_task(self.chief, task.board))
                self.assertTrue(can_edit_task(self.chief, task))
                self.assertTrue(can_manage_task_participants(self.chief, task))
                self.assertTrue(can_move_task(self.chief, task))
        self.assertFalse(can_create_task(self.chief, self.inbox_board))
        self.assertFalse(can_edit_task(self.chief, inbox_task))
        self.assertTrue(can_move_task(self.chief, inbox_task))
        self.assertFalse(can_edit_task(self.chief, other_department_task))
        self.assertFalse(can_move_task(self.chief, other_department_task))

    def test_member_can_only_move_tasks_on_accessible_boards(self):
        inbox_task = self._task(self.inbox_board, "Member inbox task")
        department_task = self._task(self.department_board, "Member department task")
        project_task = self._task(self.project_board, "Member project task")
        other_department_task = self._task(
            self.other_department_board,
            "Member other-department task",
        )
        other_company_task = self._task(
            self.other_company_board,
            "Member other-company task",
        )

        for task in (inbox_task, department_task, project_task):
            with self.subTest(task=task.id):
                self.assertFalse(can_create_task(self.member, task.board))
                self.assertFalse(can_edit_task(self.member, task))
                self.assertFalse(can_manage_task_participants(self.member, task))
                self.assertTrue(can_move_task(self.member, task))
        self.assertFalse(can_move_task(self.member, other_department_task))
        self.assertFalse(can_move_task(self.member, other_company_task))


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

    def test_task_creates_discussion_automatically(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        board = TaskBoard.objects.get(
            workspace=workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        task = Task.objects.create(
            workspace=workspace,
            board=board,
            column=board.columns.get(key="todo"),
            title="Compare supplier proposals",
        )

        self.assertTrue(TaskDiscussion.objects.filter(task=task).exists())

    def test_task_comments_and_discussion_messages_support_attachments(self):
        user = get_user_model().objects.create_user(email="author@example.com", password="pass")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        board = TaskBoard.objects.get(
            workspace=workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        task = Task.objects.create(
            workspace=workspace,
            board=board,
            column=board.columns.get(key="todo"),
            title="Compare supplier proposals",
            created_by=user,
        )
        comment = TaskComment.objects.create(task=task, author=user, body="Include insurance.")
        comment_attachment = TaskCommentAttachment.objects.create(
            comment=comment,
            file="tasks/comments/report.pdf",
            original_name="report.pdf",
            uploaded_by=user,
        )
        message = TaskDiscussionMessage.objects.create(
            discussion=task.discussion,
            author=user,
            body="The updated proposal is ready.",
        )
        message_attachment = TaskDiscussionMessageAttachment.objects.create(
            message=message,
            file="tasks/discussions/proposal.pdf",
            original_name="proposal.pdf",
            uploaded_by=user,
        )

        self.assertEqual(task.comments.get(), comment)
        self.assertEqual(comment.attachments.get(), comment_attachment)
        self.assertEqual(task.discussion.messages.get(), message)
        self.assertEqual(message.attachments.get(), message_attachment)


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
        user_model.objects.create_user(
            email="first@example.com",
            password="pass",
            system_role="ceo",
        )
        user_model.objects.create_user(
            email="second@example.com",
            password="pass",
            system_role="ceo",
        )
        user_model.objects.create_user(
            email="third@example.com",
            password="pass",
            system_role="ceo",
        )
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
        self.assertEqual(TaskComment.objects.count(), expected_tasks * len(DEMO_TASK_COMMENTS))
        self.assertEqual(
            TaskDiscussionMessage.objects.count(),
            expected_tasks * len(DEMO_DISCUSSION_MESSAGES),
        )
        self.assertGreater(TaskObserver.objects.count(), 0)
        self.assertFalse(
            Task.objects.exclude(workspace_id=models.F("board__workspace_id")).exists()
        )


class TaskBackendActionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="ceo@example.com",
            password="pass",
            system_role="ceo",
        )
        self.assignee = user_model.objects.create_user(
            email="assignee@example.com",
            password="pass",
        )
        self.observer = user_model.objects.create_user(email="observer@example.com", password="pass")
        self.workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        WorkspaceAccessGrant.objects.create(workspace=self.workspace, user=self.user)
        WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            user=self.assignee,
            role=WorkspaceAccessGrant.Role.MEMBER,
        )
        WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            user=self.observer,
            role=WorkspaceAccessGrant.Role.MEMBER,
        )
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


class TaskMutationPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.chief = user_model.objects.create_user(
            email="chief@example.com",
            password="pass",
        )
        self.member = user_model.objects.create_user(
            email="member@example.com",
            password="pass",
        )
        self.outside_chief = user_model.objects.create_user(
            email="outside-chief@example.com",
            password="pass",
        )
        self.company = Company.objects.create(name="Altyn Group")
        self.team_department = _create_department(self.company, "Finance")
        outside_department = _create_department(self.company, "Logistics")
        DepartmentMembership.objects.create(
            user=self.chief,
            department=self.team_department,
            role=DepartmentMembership.Role.CHIEF,
        )
        DepartmentMembership.objects.create(
            user=self.member,
            department=self.team_department,
            role=DepartmentMembership.Role.MEMBER,
        )
        DepartmentMembership.objects.create(
            user=self.outside_chief,
            department=outside_department,
            role=DepartmentMembership.Role.CHIEF,
        )

        self.workspace = Workspace.objects.create(name="Procurement", slug="procurement")
        self.team = WorkspaceTeam.objects.create(
            workspace=self.workspace,
            name="Finance Team",
            slug="finance-team",
        )
        department_grant = WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            department=self.team_department,
        )
        WorkspaceTeamMember.objects.create(
            team=self.team,
            access_grant=department_grant,
        )
        outside_user_grant = WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            user=self.outside_chief,
        )
        WorkspaceTeamMember.objects.create(
            team=self.team,
            access_grant=outside_user_grant,
        )
        self.project = Project.objects.create(
            workspace=self.workspace,
            team=self.team,
            name="Supplier Selection",
            slug="supplier-selection",
        )
        self.project_board = TaskBoard.objects.get(project=self.project)

    def _task_payload(self, *, title="Review proposals", column=None):
        return {
            "title": title,
            "description": "Compare total cost.",
            "board": self.project_board.id,
            "column": (column or self.project_board.columns.get(key="todo")).id,
            "priority": Task.Priority.HIGH,
            "due_date": "2026-07-10",
        }

    def test_team_department_chief_can_create_and_edit_project_task(self):
        self.client.force_login(self.chief)
        create_response = self.client.post(
            reverse("workspaces:task-create", args=[self.workspace.slug]),
            self._task_payload(),
        )

        self.assertEqual(create_response.status_code, 302)
        task = Task.objects.get(title="Review proposals")

        edit_response = self.client.post(
            reverse("workspaces:task-edit", args=[self.workspace.slug, task.id]),
            self._task_payload(title="Review updated proposals"),
        )

        self.assertEqual(edit_response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "Review updated proposals")

    def test_team_department_chief_can_move_project_task(self):
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.project_board,
            column=self.project_board.columns.get(key="todo"),
            title="Review proposals",
        )
        review_column = self.project_board.columns.get(key="review")
        self.client.force_login(self.chief)

        response = self.client.post(
            reverse("workspaces:task-move", args=[self.workspace.slug, task.id]),
            {"column": review_column.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.column, review_column)

    def test_team_member_without_chief_role_cannot_create_project_task(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("workspaces:task-create", args=[self.workspace.slug]),
            self._task_payload(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(title="Review proposals").exists())

    def test_team_member_can_move_but_cannot_edit_accessible_project_task(self):
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.project_board,
            column=self.project_board.columns.get(key="todo"),
            title="Member-visible task",
        )
        review_column = self.project_board.columns.get(key="review")
        self.client.force_login(self.member)

        move_response = self.client.post(
            reverse("workspaces:task-move", args=[self.workspace.slug, task.id]),
            {"column": review_column.id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        edit_response = self.client.post(
            reverse("workspaces:task-edit", args=[self.workspace.slug, task.id]),
            self._task_payload(title="Unauthorized edit", column=review_column),
        )

        self.assertEqual(move_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 403)
        task.refresh_from_db()
        self.assertEqual(task.column, review_column)
        self.assertEqual(task.title, "Member-visible task")

    def test_user_without_workspace_access_cannot_find_or_move_task(self):
        outsider = get_user_model().objects.create_user(
            email="task-outsider@example.com",
            password="pass",
        )
        task = Task.objects.create(
            workspace=self.workspace,
            board=self.project_board,
            column=self.project_board.columns.get(key="todo"),
            title="Hidden task",
        )
        self.client.force_login(outsider)

        response = self.client.post(
            reverse("workspaces:task-move", args=[self.workspace.slug, task.id]),
            {"column": self.project_board.columns.get(key="review").id},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 404)

    def test_task_people_picker_is_scoped_to_selected_board(self):
        workspace_only_user = get_user_model().objects.create_user(
            email="workspace-only@example.com",
            password="pass",
        )
        outsider = get_user_model().objects.create_user(
            email="people-outsider@example.com",
            password="pass",
        )
        WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            user=workspace_only_user,
            role=WorkspaceAccessGrant.Role.MEMBER,
        )
        self.client.force_login(self.chief)

        project_response = self.client.get(
            reverse("workspaces:tasks", args=[self.workspace.slug]),
            {"board": self.project_board.id},
        )
        inbox_board = TaskBoard.objects.get(
            workspace=self.workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        inbox_response = self.client.get(
            reverse("workspaces:tasks", args=[self.workspace.slug]),
            {"board": inbox_board.id},
        )

        project_user_ids = {user.id for user in project_response.context["task_users"]}
        inbox_user_ids = {user.id for user in inbox_response.context["task_users"]}
        self.assertIn(self.member.id, project_user_ids)
        self.assertNotIn(workspace_only_user.id, project_user_ids)
        self.assertNotIn(outsider.id, project_user_ids)
        self.assertIn(workspace_only_user.id, inbox_user_ids)
        self.assertNotIn(outsider.id, inbox_user_ids)

    def test_task_form_accepts_accessible_people_and_rejects_inaccessible_people(self):
        outsider = get_user_model().objects.create_user(
            email="assignment-outsider@example.com",
            password="pass",
        )
        self.client.force_login(self.chief)
        accessible_payload = {
            **self._task_payload(title="Scoped assignment"),
            "assignees": [self.member.id],
            "assignees__present": "1",
            "observers": [self.outside_chief.id],
            "observers__present": "1",
        }

        allowed_response = self.client.post(
            reverse("workspaces:task-create", args=[self.workspace.slug]),
            accessible_payload,
        )
        denied_response = self.client.post(
            reverse("workspaces:task-create", args=[self.workspace.slug]),
            {
                **self._task_payload(title="Invalid assignment"),
                "assignees": [outsider.id],
                "assignees__present": "1",
            },
        )

        task = Task.objects.get(title="Scoped assignment")
        self.assertEqual(allowed_response.status_code, 302)
        self.assertTrue(task.assignees.filter(user=self.member).exists())
        self.assertTrue(task.observers.filter(user=self.outside_chief).exists())
        self.assertEqual(denied_response.status_code, 302)
        self.assertFalse(Task.objects.filter(title="Invalid assignment").exists())

    def test_task_board_change_rejects_existing_inaccessible_people_when_fields_omitted(self):
        ceo = get_user_model().objects.create_user(
            email="board-change-ceo@example.com",
            password="pass",
            system_role="ceo",
        )
        workspace_only_user = get_user_model().objects.create_user(
            email="board-change-member@example.com",
            password="pass",
        )
        WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            user=workspace_only_user,
            role=WorkspaceAccessGrant.Role.MEMBER,
        )
        inbox_board = TaskBoard.objects.get(
            workspace=self.workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        task = Task.objects.create(
            workspace=self.workspace,
            board=inbox_board,
            column=inbox_board.columns.get(key="todo"),
            title="Move with stale assignee",
        )
        TaskAssignee.objects.create(task=task, user=workspace_only_user, assigned_by=ceo)
        self.client.force_login(ceo)

        response = self.client.post(
            reverse("workspaces:task-edit", args=[self.workspace.slug, task.id]),
            self._task_payload(title="Unauthorized board move"),
        )

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "Move with stale assignee")
        self.assertEqual(task.board, inbox_board)

    def test_chief_whose_department_is_not_in_team_cannot_create_project_task(self):
        self.client.force_login(self.outside_chief)

        response = self.client.post(
            reverse("workspaces:task-create", args=[self.workspace.slug]),
            self._task_payload(),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(title="Review proposals").exists())

    def test_department_chief_cannot_create_inbox_task(self):
        inbox_board = TaskBoard.objects.get(
            workspace=self.workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        self.client.force_login(self.chief)

        response = self.client.post(
            reverse("workspaces:task-create", args=[self.workspace.slug]),
            {
                **self._task_payload(),
                "board": inbox_board.id,
                "column": inbox_board.columns.get(key="todo").id,
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(title="Review proposals").exists())

    def test_workspace_owner_cannot_create_project_but_ceo_can(self):
        workspace_owner = get_user_model().objects.create_user(
            email="owner@example.com",
            password="pass",
        )
        WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            user=workspace_owner,
            role=WorkspaceAccessGrant.Role.OWNER,
        )
        project_data = {
            "name": "New Project",
            "description": "Restricted project creation.",
            "team": self.team.id,
        }
        self.client.force_login(workspace_owner)

        denied_response = self.client.post(
            reverse("workspaces:project-create", args=[self.workspace.slug]),
            project_data,
        )

        self.assertEqual(denied_response.status_code, 403)
        self.assertFalse(Project.objects.filter(name="New Project").exists())

        ceo = get_user_model().objects.create_user(
            email="ceo@example.com",
            password="pass",
            system_role="ceo",
        )
        self.client.force_login(ceo)
        allowed_response = self.client.post(
            reverse("workspaces:project-create", args=[self.workspace.slug]),
            project_data,
        )

        self.assertEqual(allowed_response.status_code, 302)
        self.assertTrue(Project.objects.filter(name="New Project", created_by=ceo).exists())

    def test_company_director_can_create_project_only_in_own_company_workspace(self):
        director = get_user_model().objects.create_user(
            email="director@example.com",
            password="pass",
        )
        CompanyMembership.objects.create(
            user=director,
            company=self.company,
            role=CompanyMembership.Role.DIRECTOR,
        )
        WorkspaceAccessGrant.objects.create(
            workspace=self.workspace,
            user=director,
            role=WorkspaceAccessGrant.Role.MEMBER,
        )
        company_workspace = Workspace.objects.create(
            company=self.company,
            name="Altyn Group Workspace",
            slug="altyn-group-workspace",
        )
        company_team = WorkspaceTeam.objects.create(
            workspace=company_workspace,
            name="Finance Team",
            slug="finance-team",
        )
        project_data = {
            "name": "Company Project",
            "description": "Director-owned company project.",
            "team": company_team.id,
        }
        self.client.force_login(director)

        allowed_response = self.client.post(
            reverse("workspaces:project-create", args=[company_workspace.slug]),
            project_data,
        )
        denied_response = self.client.post(
            reverse("workspaces:project-create", args=[self.workspace.slug]),
            {**project_data, "name": "Cross-company Project", "team": self.team.id},
        )

        self.assertEqual(allowed_response.status_code, 302)
        self.assertTrue(
            Project.objects.filter(
                workspace=company_workspace,
                name="Company Project",
                created_by=director,
            ).exists()
        )
        self.assertEqual(denied_response.status_code, 403)
        self.assertFalse(Project.objects.filter(name="Cross-company Project").exists())

        project = Project.objects.get(workspace=company_workspace, name="Company Project")
        edit_response = self.client.post(
            reverse(
                "workspaces:project-general",
                args=[company_workspace.slug, project.slug],
            ),
            {
                "action": "save_details",
                "name": "Updated Company Project",
                "description": project.description,
            },
        )

        self.assertEqual(edit_response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.name, "Updated Company Project")

    def test_company_director_can_create_and_edit_task_in_own_company_workspace(self):
        director = get_user_model().objects.create_user(
            email="task-director@example.com",
            password="pass",
        )
        CompanyMembership.objects.create(
            user=director,
            company=self.company,
            role=CompanyMembership.Role.DIRECTOR,
        )
        company_workspace = Workspace.objects.create(
            company=self.company,
            name="Director Task Workspace",
            slug="director-task-workspace",
        )
        inbox_board = TaskBoard.objects.get(
            workspace=company_workspace,
            board_type=TaskBoard.BoardType.INBOX,
        )
        payload = {
            "title": "Director task",
            "description": "Company-scoped task.",
            "board": inbox_board.id,
            "column": inbox_board.columns.get(key="todo").id,
            "priority": Task.Priority.NORMAL,
            "due_date": "2026-07-10",
        }
        self.client.force_login(director)

        create_response = self.client.post(
            reverse("workspaces:task-create", args=[company_workspace.slug]),
            payload,
        )
        task = Task.objects.get(workspace=company_workspace, title="Director task")
        edit_response = self.client.post(
            reverse("workspaces:task-edit", args=[company_workspace.slug, task.id]),
            {**payload, "title": "Updated director task"},
        )

        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(edit_response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, "Updated director task")


class TaskCollaborationEndpointTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.media_settings = self.settings(MEDIA_ROOT=self.media_directory.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.addCleanup(self.media_directory.cleanup)

        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="member@example.com",
            password="pass",
            full_name="Workspace Member",
        )
        self.workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        WorkspaceAccessGrant.objects.create(workspace=self.workspace, user=self.user)
        board = TaskBoard.objects.get(
            workspace=self.workspace,
            board_type=TaskBoard.BoardType.WORKSPACE,
        )
        self.task = Task.objects.create(
            workspace=self.workspace,
            board=board,
            column=board.columns.get(key="todo"),
            title="Compare supplier proposals",
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def _url(self, route_name):
        return reverse(
            f"workspaces:{route_name}",
            args=[self.workspace.slug, self.task.id],
        )

    def test_collaboration_returns_comments_and_discussion_messages(self):
        TaskComment.objects.create(
            task=self.task,
            author=self.user,
            body="Include insurance in the comparison.",
        )
        TaskDiscussionMessage.objects.create(
            discussion=self.task.discussion,
            author=self.user,
            body="The updated proposal is ready.",
        )

        response = self.client.get(self._url("task-collaboration"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task"]["id"], self.task.id)
        self.assertEqual(payload["current_user"]["name"], "Workspace Member")
        self.assertEqual(payload["comments"][0]["body"], "Include insurance in the comparison.")
        self.assertTrue(payload["comments"][0]["is_own"])
        self.assertEqual(
            payload["discussion"]["messages"][0]["body"],
            "The updated proposal is ready.",
        )

    def test_comment_create_accepts_multiple_attachments(self):
        response = self.client.post(
            self._url("task-comment-create"),
            {
                "body": "Please review both files.",
                "attachments": [
                    SimpleUploadedFile("quote-a.txt", b"quote a"),
                    SimpleUploadedFile("quote-b.txt", b"quote b"),
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()["comment"]
        self.assertEqual(payload["author"]["id"], self.user.id)
        self.assertCountEqual(
            [attachment["name"] for attachment in payload["attachments"]],
            ["quote-a.txt", "quote-b.txt"],
        )
        comment = TaskComment.objects.get(pk=payload["id"])
        self.assertEqual(comment.attachments.count(), 2)
        self.assertFalse(comment.attachments.exclude(uploaded_by=self.user).exists())

    def test_discussion_message_accepts_attachment_without_body(self):
        response = self.client.post(
            self._url("task-discussion-message-create"),
            {
                "body": "",
                "attachments": [SimpleUploadedFile("comparison.txt", b"comparison")],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()["message"]
        self.assertEqual(payload["body"], "")
        self.assertEqual(payload["attachments"][0]["name"], "comparison.txt")
        self.assertEqual(payload["author"]["id"], self.user.id)

    def test_discussion_message_rejects_empty_payload(self):
        response = self.client.post(
            self._url("task-discussion-message-create"),
            {"body": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertFalse(TaskDiscussionMessage.objects.exists())

    def test_collaboration_hides_task_from_user_without_workspace_access(self):
        outsider = get_user_model().objects.create_user(
            email="outsider@example.com",
            password="pass",
        )
        self.client.force_login(outsider)

        response = self.client.get(self._url("task-collaboration"))

        self.assertEqual(response.status_code, 404)
