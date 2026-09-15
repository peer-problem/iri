from api.tests.test_api import configuration as api_configuration
from runpod.settings import Settings


def configuration(**updates):
    return Settings(_env_file=None, **api_configuration(**updates).model_dump())
