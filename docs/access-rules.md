# Текущие правила доступа

Документ описывает фактически реализованные backend-проверки. Это текущий источник истины по правам; планируемые изменения вынесены в [user-testing-todo.md](user-testing-todo.md).

## Модель ролей

### Глобальная роль пользователя (`User.system_role`)

- `ceo` — полный просмотр рабочих данных и основные права управления.
- `general_director` — глобальная видимость workspace и управление teams, но не права CEO на projects, tasks и Settings.
- `none` — глобальных привилегий нет.

Флаги Django `is_staff` и `is_superuser` дают глобальную видимость workspace и управление teams, но сами по себе не дают права CEO на projects, tasks и Settings.

### Участие в компании (`CompanyMembership.role`)

- `director` — видит workspace своей компании и может управлять teams и projects в нем.
- `member` — видит workspace своей компании без управленческих прав.

### Участие в департаменте (`DepartmentMembership.role`)

- `chief` — руководитель департамента. Может управлять задачами project, только если именно его департамент входит в team этого project.
- `member` — обычный участник департамента, управленческих прав не получает.

### Доступ к workspace (`WorkspaceAccessGrant.role`)

Grant выдается компании, департаменту или конкретному пользователю.

- `owner`, `admin` — дают управление teams и полную видимость данных внутри этого workspace.
- `member` — дает рабочий доступ и позволяет перемещать tasks на доступных boards.
- `viewer` — дает видимость без task mutation.

Ни `member`, ни `viewer` не дают управление workspace/teams.

## Workspace

### Видимость

Все активные workspace видят:

- `ceo`;
- `general_director`;
- Django `staff` и `superuser`.

Остальные пользователи видят workspace, если выполняется хотя бы одно условие:

- пользователь состоит в компании, к которой напрямую привязан company workspace;
- есть прямой `WorkspaceAccessGrant` на пользователя;
- grant выдан компании пользователя;
- grant выдан департаменту пользователя.

`CompanyMembership` автоматически открывает только company workspace этой компании. Для custom/cross-company workspace нужен подходящий grant.

### Создание и Settings

- Создать custom workspace через рабочий UI может только `ceo`.
- Редактировать Settings и access grants custom workspace может только `ceo`.
- Settings company workspace запрещены через рабочий UI всем, включая `ceo`, `general_director`, `staff` и `superuser`; они управляются через admin/backoffice.
- Создатель custom workspace автоматически получает прямой grant `owner`.

## Teams

Пользователь видит team, если он управляет workspace либо подходит под один из grants, входящих в team: user, company или department.

Создавать и редактировать teams, а также добавлять и удалять их участников могут:

- `ceo`, `general_director`, `staff`, `superuser`;
- `director` компании для ее company workspace;
- пользователь, подходящий под grant `owner` или `admin` этого workspace.

Team состоит из `WorkspaceAccessGrant`; само участие в team не создает доступ к workspace.

Системные department teams автоматически формируются по `DepartmentType`. UI teams сейчас можно скрывать, но backend-модель и права управления остаются.

## Projects

### Видимость

- Пользователь с правом управления workspace видит все projects этого workspace.
- Остальные видят только projects, чья team доступна пользователю через grant на его user, company или department.
- Один только доступ к workspace не открывает все projects.

### Управление

Project могут создавать и редактировать:

- `ceo` — в любом workspace;
- `director` компании — только в company workspace своей компании.

Оба правила включают создание project, редактирование его данных и назначение или смену team. В custom/cross-company workspace право остается только у `ceo`.

`general_director`, `staff`, `superuser`, workspace `owner/admin` и department `chief` не могут изменять project, если у пользователя нет одного из указанных выше прав.

## Tasks

### Видимость досок и задач

- Inbox и workspace board видны всем пользователям, имеющим доступ к workspace.
- Department board видна пользователю в рамках доступного ему департамента; управляющий workspace видит все department boards.
- Project board видна по тем же правилам, что и соответствующий project.
- Доступ к task наследуется от ее board. `author`, `assignee` или `observer` сами по себе не выдают доступ к workspace/project.

### Создание, редактирование и перемещение

- `ceo` может создавать, редактировать и перемещать tasks на любых доступных типах board: inbox, workspace, department и project.
- `director` компании может создавать, редактировать, назначать участников и перемещать tasks на всех boards company workspace своей компании.
- `chief` может полностью управлять tasks на board своего department и на project board, если его точный department добавлен во внутреннюю team этого project.
- Обычный member может перемещать любую task на доступной ему board независимо от assignee, но не может создавать task, редактировать ее поля или менять участников.
- Доступ к workspace компании A сам по себе не открывает boards и tasks компании B; отдельный явно выданный доступ проверяется по обычным workspace/project правилам.
- Task author, assignee и observer сами по себе не расширяют доступ к workspace или board.
- При редактировании task перенос на другую board также проверяется по правам на целевую board.

### Comments и discussion

Любой пользователь, которому видна task, может:

- читать comments и discussion;
- добавлять comments и сообщения discussion;
- прикладывать разрешенные файлы.

Отдельных участников или отдельных прав у discussion нет: доступ полностью наследуется от task.

## Краткая матрица

| Действие | CEO | General director / staff / superuser | Workspace owner/admin или company director | Chief из project team | Обычный доступ |
| --- | --- | --- | --- | --- | --- |
| Видеть доступные workspace | Все | Все | По memberships/grants | По memberships/grants | По memberships/grants |
| Создать workspace | Да | Нет | Нет | Нет | Нет |
| Изменить custom Settings/access | Да | Нет | Нет | Нет | Нет |
| Управлять teams | Да | Да | Да | Только при отдельном праве управления workspace | Нет |
| Создать/изменить project | Да | Нет | Только director в company workspace своей компании | Нет | Нет |
| Создать/редактировать task на inbox/workspace board | Да | Нет | Только director в company workspace своей компании | Нет | Нет |
| Создать/редактировать task на department board | Да | Нет | Только director в company workspace своей компании | Для своего department | Нет |
| Создать/редактировать task на project board | Да | Нет | Только director в company workspace своей компании | Для project своего department | Нет |
| Переместить task на доступной board | Да | Только при отдельном рабочем доступе | Да | Да | Да |
| Читать и писать task collaboration | Да | Для видимой task | Для видимой task | Для видимой task | Для видимой task |

## Известные ограничения

- Frontend еще должен отдельно показывать drag-and-drop обычному member без показа недоступных `New task` и `Edit`.
- Django `superuser` не эквивалентен бизнес-роли `ceo`.

Минимальные изменения перед пользовательским тестированием перечислены в [user-testing-todo.md](user-testing-todo.md).
