from apps.ordo.organizations.slugs import ascii_slugify, unreserved_root_slug

from .models import Project, Workspace


# Project slugs live under /<workspace>/projects/, so the only collision to avoid
# is the literal "new" create route — not the workspace-level reserved roots.
_RESERVED_PROJECT_SLUGS = frozenset({"new"})


def unique_workspace_slug(value):
    base_slug = unreserved_root_slug(value, fallback="workspace")
    slug = base_slug
    suffix = 2
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def unique_project_slug(value, workspace, *, exclude_pk=None):
    """Transliterated, URL-safe project slug, unique within the workspace.

    Mirrors :func:`unique_workspace_slug`: the same ASCII slugify is used and
    collisions are resolved with a numeric suffix instead of rejecting the name.
    """
    base_slug = ascii_slugify(value, fallback="project")
    if base_slug in _RESERVED_PROJECT_SLUGS:
        base_slug = f"{base_slug}-project"

    queryset = Project.objects.filter(workspace=workspace)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    slug = base_slug
    suffix = 2
    while queryset.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug
