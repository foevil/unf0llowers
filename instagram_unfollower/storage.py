from contextlib import contextmanager
from typing import Optional

from sqlalchemy import Column, Integer, create_engine, ForeignKey, Boolean, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
Session = sessionmaker()


class Unfollower(Base):
    __tablename__ = 'unfollowers'

    id = Column(Integer, primary_key=True)
    instagram_author_id = Column(Integer, nullable=False)
    telegram_author_id = Column(Integer, unique=False, nullable=False)
    instagram_unfollower_id = Column(Integer, nullable=False)


class TelegramUser(Base):
    __tablename__ = 'telegram_users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, ForeignKey(Unfollower.telegram_author_id), unique=False, nullable=False)
    instagram_id = Column(Integer, ForeignKey(Unfollower.instagram_author_id), unique=False, nullable=True)
    is_notified = Column(Boolean, default=False, nullable=False)
    language = Column(String, default=None, nullable=True)


class UnfollowersStorage:

    def __init__(self, db_url):
        # logger.info(f'Using database path: {db_url}')
        engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(engine)
        Session.configure(bind=engine)

    def get_known_unfollowers(self, telegram_id: int):
        with self.session_scope() as session:
            unfollowers_query = session.query(Unfollower).filter_by(telegram_author_id=telegram_id)
            unfollowers = unfollowers_query.all()
            return {unfollower.instagram_unfollower_id for unfollower in unfollowers}

    def update_known_unfollowers(self, telegram_id: int, instagram_id: int, unfollower_ids: set):
        with self.session_scope() as session:
            session.query(Unfollower).filter_by(telegram_author_id=telegram_id,
                                                instagram_author_id=instagram_id).delete()

            unfollowers = [Unfollower(telegram_author_id=telegram_id,
                                      instagram_author_id=instagram_id,
                                      instagram_unfollower_id=unfollower_id) for unfollower_id in unfollower_ids]
            session.bulk_save_objects(unfollowers)

    def get_instagram_id(self, telegram_id: int) -> Optional[int]:
        with self.session_scope() as session:
            try:
                return session.query(TelegramUser).filter_by(telegram_id=telegram_id).first().instagram_id
            except AttributeError:
                return None

    def update_instagram_id(self, telegram_id: int, instagram_id: int):
        with self.session_scope() as session:
            tg_user = session.query(TelegramUser).filter_by(telegram_id=telegram_id).first()
            if tg_user is None:
                tg_user = TelegramUser(telegram_id=telegram_id, instagram_id=instagram_id)
                session.add(tg_user)
            else:
                tg_user.instagram_id = instagram_id

    def start_notifying(self, telegram_id: int) -> bool:
        with self.session_scope() as session:
            tg_user = session.query(TelegramUser).filter_by(telegram_id=telegram_id).first()
            if tg_user is None:
                return False
            tg_user.is_notified = True
            return True

    def stop_notifying(self, telegram_id: int) -> bool:
        with self.session_scope() as session:
            tg_user = session.query(TelegramUser).filter_by(telegram_id=telegram_id).first()
            if tg_user is None:
                return False
            tg_user.is_notified = False
            return True

    def get_notified_telegram_ids(self) -> set:
        with self.session_scope() as session:
            return {user.telegram_id for user in session.query(TelegramUser).filter_by(is_notified=True).all()}

    def get_language(self, telegram_id: int) -> Optional[str]:
        with self.session_scope() as session:
            user = session.query(TelegramUser).filter_by(telegram_id=telegram_id).first()
            if user is not None:
                return user.language
            else:
                return None

    def set_language(self, telegram_id: int, language: Optional[str]):
        with self.session_scope() as session:
            user = session.query(TelegramUser).filter_by(telegram_id=telegram_id).first()
            if user is None:
                user = TelegramUser(telegram_id=telegram_id)
                session.add(user)
            user.language = language

    @contextmanager
    def session_scope(self):
        session = Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
