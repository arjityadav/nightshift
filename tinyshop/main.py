from tinyshop.api import create_app
from tinyshop.repository import InMemoryRepository

app = create_app(InMemoryRepository())
