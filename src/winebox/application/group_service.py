"""Application group service for organizing library apps into multi-tag groups."""

import re
from typing import List, Optional
from winebox.common.exceptions import ResourceNotFoundError, WineboxError
from winebox.domain.models import AppGroup
from winebox.infrastructure.sqlite_repository import SqliteRepository


def slugify_group(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "-", cleaned).strip("-")


class GroupService:
    """Manages master groups and many-to-many application group assignments."""

    def __init__(self, repo: Optional[SqliteRepository] = None) -> None:
        self.repo = repo or SqliteRepository()

    def create_group(
        self,
        name: str,
        group_id: Optional[str] = None,
        icon: str = "",
        sort_order: int = 0,
    ) -> AppGroup:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise WineboxError("Group name cannot be empty")

        final_id = (group_id.strip() if group_id else slugify_group(cleaned_name)) or "group"
        try:
            self.repo.load_group(final_id)
            exists = True
        except ResourceNotFoundError:
            exists = False

        if exists:
            raise WineboxError(f"Group with ID '{final_id}' already exists")

        grp = AppGroup(
            id=final_id,
            name=cleaned_name,
            icon=icon.strip(),
            sort_order=sort_order,
        )
        self.repo.save_group(grp)
        return grp

    def list_groups(self) -> List[AppGroup]:
        return self.repo.list_groups()

    def get_group(self, group_id: str) -> AppGroup:
        return self.repo.load_group(group_id)

    def rename_group(self, group_id: str, new_name: str, icon: Optional[str] = None) -> AppGroup:
        cleaned_name = new_name.strip()
        if not cleaned_name:
            raise WineboxError("Group name cannot be empty")
        grp = self.repo.load_group(group_id)
        grp.name = cleaned_name
        if icon is not None:
            grp.icon = icon.strip()
        self.repo.save_group(grp)
        return grp

    def delete_group(self, group_id: str) -> None:
        self.repo.delete_group(group_id)

    def assign_groups(self, app_id: str, group_ids: List[str]) -> None:
        # Validate that application exists
        self.repo.load_app(app_id)
        # Validate that each group exists
        for gid in group_ids:
            self.repo.load_group(gid)
        self.repo.set_app_groups(app_id, group_ids)

    def get_app_groups(self, app_id: str) -> List[AppGroup]:
        gids = self.repo.get_app_group_ids(app_id)
        result: List[AppGroup] = []
        for gid in gids:
            try:
                result.append(self.repo.load_group(gid))
            except Exception:
                pass
        return result
