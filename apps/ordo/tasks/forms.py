from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Task, TaskAssignee, TaskBoard, TaskColumn, TaskObserver


class TaskForm(forms.ModelForm):
    assignees = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
    )
    observers = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
    )

    class Meta:
        model = Task
        fields = (
            "title",
            "description",
            "board",
            "column",
            "priority",
            "due_date",
            "assignees",
            "observers",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace")
        self.selected_board = kwargs.pop("selected_board", None)
        self._submitted_field_names = set()
        if args:
            data = args[0]
            if data is not None:
                self._submitted_field_names = set(data.keys())
        elif kwargs.get("data") is not None:
            self._submitted_field_names = set(kwargs["data"].keys())
        super().__init__(*args, **kwargs)

        users = get_user_model().objects.filter(is_active=True).order_by("full_name", "email")
        boards = TaskBoard.objects.filter(workspace=self.workspace).order_by(
            "board_type",
            "name",
            "id",
        )
        columns = TaskColumn.objects.filter(board__workspace=self.workspace).order_by(
            "board",
            "position",
            "id",
        )

        self.fields["board"].queryset = boards
        self.fields["column"].queryset = columns
        self.fields["column"].required = False
        self.fields["assignees"].queryset = users
        self.fields["observers"].queryset = users

        for field in self.fields.values():
            field.widget.attrs.update({"class": "shell-input"})

        if self.instance.pk:
            self.fields["assignees"].initial = self.instance.assignees.values_list(
                "user_id",
                flat=True,
            )
            self.fields["observers"].initial = self.instance.observers.values_list(
                "user_id",
                flat=True,
            )
        elif self.selected_board is not None:
            self.fields["board"].initial = self.selected_board

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Task title cannot be empty.")
        return title

    def clean(self):
        cleaned_data = super().clean()
        board = cleaned_data.get("board") or self.selected_board
        column = cleaned_data.get("column")

        if board is None:
            self.add_error("board", "Task board is required.")
            return cleaned_data

        if board.workspace_id != self.workspace.id:
            self.add_error("board", "Task board must belong to the selected workspace.")
            return cleaned_data

        if column is None:
            column = (
                board.columns.filter(key="todo").first()
                or board.columns.order_by("position", "id").first()
            )
            cleaned_data["column"] = column

        if column is None:
            self.add_error("column", "Task board has no columns.")
            return cleaned_data

        if column.board_id != board.id:
            self.add_error("column", "Task column must belong to the selected board.")
            return cleaned_data

        cleaned_data["board"] = board
        return cleaned_data

    def save(self, *, actor=None, commit=True):
        task = super().save(commit=False)
        task.workspace = self.workspace
        if task.pk is None:
            task.created_by = actor

        if task.column_id and task.column.is_done:
            task.completed_at = task.completed_at or timezone.now()
        elif task.completed_at:
            task.completed_at = None

        if commit:
            task.save()
            self.save_m2m()
            self._save_people(task, actor)
        return task

    def _save_people(self, task, actor):
        if self._field_was_submitted("assignees"):
            assignees = list(self.cleaned_data.get("assignees") or [])

            TaskAssignee.objects.filter(task=task).exclude(user__in=assignees).delete()
            for user in assignees:
                TaskAssignee.objects.get_or_create(
                    task=task,
                    user=user,
                    defaults={"assigned_by": actor},
                )

        if self._field_was_submitted("observers"):
            observers = list(self.cleaned_data.get("observers") or [])

            TaskObserver.objects.filter(task=task).exclude(user__in=observers).delete()
            for user in observers:
                TaskObserver.objects.get_or_create(
                    task=task,
                    user=user,
                    defaults={"added_by": actor},
                )

    def _field_was_submitted(self, field_name):
        return (
            field_name in self._submitted_field_names
            or f"{field_name}__present" in self._submitted_field_names
        )
