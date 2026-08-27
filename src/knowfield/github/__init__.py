"""GitHub App：讓場自己去拿別的專案的 `knowledge/`（spec 072，階段 68）。"""
from .app import GitHubApp, GitHubError, app_from_config, layer_of

__all__ = ["GitHubApp", "GitHubError", "app_from_config", "layer_of"]
