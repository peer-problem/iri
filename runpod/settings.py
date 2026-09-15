import json
from pathlib import Path

from api.app.settings import ENV_FILE as ENV_FILE
from api.app.settings import REPO_ROOT as REPO_ROOT
from api.app.settings import Settings as APISettings

ROOT = Path(__file__).resolve().parent


class Settings(APISettings):
    @property
    def profile(self) -> dict:
        return json.loads((ROOT / "configs/models.json").read_text())[self.model_profile]
