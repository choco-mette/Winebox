"""Application service for managing Security Profiles."""

from typing import List, Optional
from winebox.common.exceptions import WineboxError
from winebox.domain.models import SecurityProfile
from winebox.infrastructure.sqlite_repository import SqliteRepository


class ProfileService:
    """Manages creation, inspection, and modification of security profiles."""

    def __init__(self, repo: Optional[SqliteRepository] = None) -> None:
        self.repo = repo or SqliteRepository()

    def list_profiles(self) -> List[SecurityProfile]:
        return self.repo.list_profiles()

    def get_profile(self, profile_id: str) -> SecurityProfile:
        return self.repo.load_profile(profile_id)

    def create_profile(
        self,
        profile_id: str,
        name: str,
        display: bool = True,
        audio: bool = True,
        network: bool = True,
        gpu: bool = True,
        description: str = "",
    ) -> SecurityProfile:
        cleaned_id = profile_id.strip().lower().replace(" ", "-")
        # Check if exists
        try:
            self.repo.load_profile(cleaned_id)
            raise WineboxError(f"Security Profile '{cleaned_id}' already exists")
        except Exception:
            pass

        profile = SecurityProfile(
            id=cleaned_id,
            name=name,
            is_builtin=False,
            display=display,
            audio=audio,
            network=network,
            gpu=gpu,
            description=description,
        )
        self.repo.save_profile(profile)
        return profile

    def update_profile(
        self,
        profile_id: str,
        name: Optional[str] = None,
        display: Optional[bool] = None,
        audio: Optional[bool] = None,
        network: Optional[bool] = None,
        gpu: Optional[bool] = None,
        description: Optional[str] = None,
    ) -> SecurityProfile:
        profile = self.repo.load_profile(profile_id)

        if name is not None:
            profile.name = name
        if display is not None:
            profile.display = display
        if audio is not None:
            profile.audio = audio
        if network is not None:
            profile.network = network
        if gpu is not None:
            profile.gpu = gpu
        if description is not None:
            profile.description = description

        self.repo.save_profile(profile)
        return profile

    def delete_profile(self, profile_id: str) -> None:
        self.repo.delete_profile(profile_id)
