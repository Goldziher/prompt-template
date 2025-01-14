import pytest
from faker import Faker


@pytest.fixture(scope="session")
def faker() -> Faker:
    return Faker()
