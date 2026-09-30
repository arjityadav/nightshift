"""M1 · In-memory repository.   make check M=01"""

from tests.repo_contract import RepositoryContract
from tinyshop.repository import InMemoryRepository


class TestInMemoryRepository(RepositoryContract):
    def make_repo(self):
        return InMemoryRepository()
