from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from persistence.models.bot_config import BotConfig


class BotConfigRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_name_and_exchange(self, name: str, exchange: str) -> BotConfig | None:
        return (
            self.session.query(BotConfig)
            .filter_by(name=name, exchange=exchange)
            .first()
        )

    def create_if_not_exists(
        self, name: str, exchange: str, mode: str = "TESTNET"
    ) -> BotConfig:
        bot = self.get_by_name_and_exchange(name, exchange)
        if bot:
            return bot

        new_bot = BotConfig(name=name, exchange=exchange, mode=mode)
        try:
            self.session.add(new_bot)
            self.session.commit()
            self.session.refresh(new_bot)
            return new_bot
        except IntegrityError:
            self.session.rollback()
            return self.get_by_name_and_exchange(name, exchange)

    def update_status(self, bot_id: int, status: str) -> BotConfig | None:
        bot = self.session.query(BotConfig).filter_by(id=bot_id).first()
        if bot:
            bot.status = status
            bot.updated_at = datetime.utcnow()
            self.session.commit()
        return bot
