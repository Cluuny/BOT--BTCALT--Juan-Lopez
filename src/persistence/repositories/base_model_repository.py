from typing import Generic, TypeVar, Type
from sqlalchemy.orm import Session
from persistence.db_connection import db

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class

    def create(self, **kwargs) -> T:
        with db.get_session() as session:
            instance = self.model_class(**kwargs)
            session.add(instance)
            session.commit()
            return instance

    def get_by_id(self, id: int) -> T:
        with db.get_session() as session:
            return session.query(self.model_class).get(id)

    def get_all(self):
        with db.get_session() as session:
            return session.query(self.model_class).all()
