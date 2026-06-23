from datetime import timedelta

from django.utils import timezone

from apps.ordo.organizations.models import Department
from apps.ordo.workspaces.models import Project, Workspace

from .models import (
    Task,
    TaskAssignee,
    TaskBoard,
    TaskColumn,
    TaskComment,
    TaskDiscussion,
    TaskDiscussionMessage,
    TaskObserver,
)
from .selectors import task_board_user_queryset


DEFAULT_TASK_COLUMNS = (
    {
        "key": "todo",
        "name": "To do",
        "semantic_type": TaskColumn.SemanticType.TODO,
        "position": 0,
        "is_done": False,
    },
    {
        "key": "in-progress",
        "name": "In progress",
        "semantic_type": TaskColumn.SemanticType.ACTIVE,
        "position": 1,
        "is_done": False,
    },
    {
        "key": "review",
        "name": "Review",
        "semantic_type": TaskColumn.SemanticType.REVIEW,
        "position": 2,
        "is_done": False,
    },
    {
        "key": "awaiting-approval",
        "name": "Awaiting approval",
        "semantic_type": TaskColumn.SemanticType.REVIEW,
        "position": 3,
        "is_done": False,
    },
    {
        "key": "done",
        "name": "Done",
        "semantic_type": TaskColumn.SemanticType.DONE,
        "position": 4,
        "is_done": True,
    },
)

DEMO_TASK_BLUEPRINTS = (
    {
        "column_key": "todo",
        "title": "Prepare source data",
        "description": "Collect initial documents, prices, volumes, and responsible contacts before work starts.",
        "priority": Task.Priority.NORMAL,
        "due_offset_days": 5,
    },
    {
        "column_key": "in-progress",
        "title": "Compare supplier and internal options",
        "description": "Check cost, timing, risks, and operational impact for the current workstream.",
        "priority": Task.Priority.HIGH,
        "due_offset_days": 3,
    },
    {
        "column_key": "review",
        "title": "Review assumptions with stakeholders",
        "description": "Validate calculations, scope, and ownership with the involved department or project team.",
        "priority": Task.Priority.NORMAL,
        "due_offset_days": 7,
    },
    {
        "column_key": "awaiting-approval",
        "title": "Approve next-step recommendation",
        "description": "Confirm the recommended decision, budget impact, and follow-up actions.",
        "priority": Task.Priority.URGENT,
        "due_offset_days": 2,
    },
    {
        "column_key": "done",
        "title": "Archive completed decision package",
        "description": "Store the final package and make sure the status is visible for reporting.",
        "priority": Task.Priority.LOW,
        "due_offset_days": -1,
    },
)

DEMO_TASK_COMMENTS = (
    "Please include delivery, insurance, and service costs in the comparison.",
    "I updated the calculation with the latest assumptions for review.",
)

DEMO_DISCUSSION_MESSAGES = (
    "The initial supplier proposal is ready. We are waiting for the remaining quotes.",
    "Please compare the options using total cost, not only the upfront payment.",
    "I am preparing a consolidated table with the final cost difference.",
    "Once the last quote arrives, send the recommendation for approval.",
)


def ensure_default_task_columns(board):
    columns = []
    for column_data in DEFAULT_TASK_COLUMNS:
        column, _created = TaskColumn.objects.update_or_create(
            board=board,
            key=column_data["key"],
            defaults={
                "name": column_data["name"],
                "semantic_type": column_data["semantic_type"],
                "position": column_data["position"],
                "is_done": column_data["is_done"],
                "is_system": True,
            },
        )
        columns.append(column)
    return columns


def ensure_workspace_inbox_board(workspace):
    board, _created = TaskBoard.objects.update_or_create(
        workspace=workspace,
        board_type=TaskBoard.BoardType.INBOX,
        defaults={
            "name": "Inbox",
            "department": None,
            "project": None,
            "is_system": True,
        },
    )
    ensure_default_task_columns(board)
    return board


def ensure_workspace_general_board(workspace):
    board, _created = TaskBoard.objects.update_or_create(
        workspace=workspace,
        board_type=TaskBoard.BoardType.WORKSPACE,
        defaults={
            "name": "Workspace",
            "department": None,
            "project": None,
            "is_system": True,
        },
    )
    ensure_default_task_columns(board)
    return board


def ensure_department_task_board(workspace, department):
    if workspace.company_id != department.company_id:
        return None

    board, _created = TaskBoard.objects.update_or_create(
        workspace=workspace,
        department=department,
        board_type=TaskBoard.BoardType.DEPARTMENT,
        defaults={
            "name": department.name,
            "project": None,
            "is_system": True,
        },
    )
    ensure_default_task_columns(board)
    return board


def ensure_company_department_task_boards(workspace):
    if not workspace.company_id:
        return []

    boards = []
    departments = Department.objects.filter(company=workspace.company).order_by("name")
    for department in departments:
        board = ensure_department_task_board(workspace, department)
        if board:
            boards.append(board)
    return boards


def ensure_workspace_task_boards(workspace):
    boards = [
        ensure_workspace_inbox_board(workspace),
        ensure_workspace_general_board(workspace),
    ]
    boards.extend(ensure_company_department_task_boards(workspace))
    return boards


def ensure_project_task_board(project):
    board, _created = TaskBoard.objects.update_or_create(
        workspace=project.workspace,
        project=project,
        board_type=TaskBoard.BoardType.PROJECT,
        defaults={
            "name": project.name,
            "department": None,
            "is_system": True,
        },
    )
    ensure_default_task_columns(board)
    return board


def sync_task_boards():
    counts = {
        "workspaces": 0,
        "projects": 0,
        "departments": 0,
    }

    for workspace in Workspace.objects.select_related("company").order_by("name"):
        ensure_workspace_task_boards(workspace)
        counts["workspaces"] += 1

    for project in Project.objects.select_related("workspace").order_by("workspace__name", "name"):
        ensure_project_task_board(project)
        counts["projects"] += 1

    counts["departments"] = TaskBoard.objects.filter(
        board_type=TaskBoard.BoardType.DEPARTMENT,
    ).count()
    return counts


def _board_context_label(board):
    if board.board_type == TaskBoard.BoardType.INBOX:
        return f"{board.workspace.name} intake"
    if board.board_type == TaskBoard.BoardType.WORKSPACE:
        return f"{board.workspace.name} workspace"
    if board.board_type == TaskBoard.BoardType.DEPARTMENT and board.department_id:
        return f"{board.department.name} department"
    if board.board_type == TaskBoard.BoardType.PROJECT and board.project_id:
        return f"{board.project.name} project"
    return board.name


def _board_task_subject(board, index):
    subjects_by_type = {
        TaskBoard.BoardType.INBOX: (
            "incoming request",
            "leadership assignment",
            "cross-functional question",
            "urgent clarification",
            "triage summary",
        ),
        TaskBoard.BoardType.WORKSPACE: (
            "monthly operating plan",
            "budget checkpoint",
            "risk register",
            "management report",
            "coordination note",
        ),
        TaskBoard.BoardType.DEPARTMENT: (
            "department workload",
            "internal process",
            "resource request",
            "reporting package",
            "handover checklist",
        ),
        TaskBoard.BoardType.PROJECT: (
            "project scope",
            "supplier comparison",
            "technical review",
            "approval package",
            "closeout notes",
        ),
    }
    subjects = subjects_by_type.get(board.board_type, subjects_by_type[TaskBoard.BoardType.WORKSPACE])
    return subjects[index % len(subjects)]


def _select_demo_user(users, offset):
    if not users:
        return None
    return users[offset % len(users)]


def _ensure_demo_task_collaboration(task, users, offset):
    for index, body in enumerate(DEMO_TASK_COMMENTS):
        TaskComment.objects.get_or_create(
            task=task,
            body=body,
            defaults={"author": _select_demo_user(users, offset + index)},
        )

    discussion, _created = TaskDiscussion.objects.get_or_create(task=task)
    for index, body in enumerate(DEMO_DISCUSSION_MESSAGES):
        TaskDiscussionMessage.objects.get_or_create(
            discussion=discussion,
            body=body,
            defaults={"author": _select_demo_user(users, offset + index + 1)},
        )


def ensure_demo_tasks_for_board(board):
    ensure_default_task_columns(board)
    columns_by_key = {column.key: column for column in board.columns.all()}
    users = list(task_board_user_queryset(board))

    today = timezone.localdate()
    now = timezone.now()
    context_label = _board_context_label(board)
    tasks = []

    for index, blueprint in enumerate(DEMO_TASK_BLUEPRINTS):
        column = columns_by_key.get(blueprint["column_key"])
        if column is None:
            continue

        title = f"{context_label}: {blueprint['title']}"
        assignee = _select_demo_user(users, board.id + index)
        creator = _select_demo_user(users, board.id + index + 1)
        due_date = today + timedelta(days=blueprint["due_offset_days"])
        completed_at = now if column.is_done else None

        task, _created = Task.objects.update_or_create(
            board=board,
            title=title,
            defaults={
                "workspace": board.workspace,
                "column": column,
                "description": (
                    f"{blueprint['description']} "
                    f"Context: {_board_task_subject(board, index)}."
                ),
                "priority": blueprint["priority"],
                "due_date": due_date,
                "position": index,
                "created_by": creator,
                "completed_at": completed_at,
            },
        )

        TaskAssignee.objects.filter(task=task).exclude(user=assignee).delete()
        if assignee:
            TaskAssignee.objects.update_or_create(
                task=task,
                user=assignee,
                defaults={"assigned_by": creator},
            )

        observer = _select_demo_user(users, board.id + index + 2)
        TaskObserver.objects.filter(task=task).exclude(user=observer).delete()
        if observer and (not assignee or observer.id != assignee.id):
            TaskObserver.objects.update_or_create(
                task=task,
                user=observer,
                defaults={"added_by": creator},
            )
        elif observer and assignee and observer.id == assignee.id:
            TaskObserver.objects.filter(task=task, user=observer).delete()

        _ensure_demo_task_collaboration(task, users, board.id + index)

        tasks.append(task)

    return tasks


def seed_demo_tasks():
    sync_task_boards()
    boards = TaskBoard.objects.select_related(
        "workspace",
        "department",
        "project",
    ).prefetch_related("columns").order_by(
        "workspace__name",
        "board_type",
        "name",
    )

    task_count = 0
    board_count = 0
    for board in boards:
        task_count += len(ensure_demo_tasks_for_board(board))
        board_count += 1

    return {
        "boards": board_count,
        "tasks": task_count,
        "comments": TaskComment.objects.count(),
        "messages": TaskDiscussionMessage.objects.count(),
    }
