from apps.ordo.organizations.slugs import unreserved_root_slug

from .models import Workspace


def unique_workspace_slug(value):
    base_slug = unreserved_root_slug(value, fallback="workspace")
    slug = base_slug
    suffix = 2
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug
