from app import models  # noqa: F401  (import so the table is registered)
from app.db import Base, engine

Base.metadata.create_all(engine)
print("Tables created.")