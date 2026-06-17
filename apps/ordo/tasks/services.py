from apps.ordo.organizations.models import Department
from apps.ordo.workspaces.models import Project, Workspace

from .models import TaskBoard, TaskColumn


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
