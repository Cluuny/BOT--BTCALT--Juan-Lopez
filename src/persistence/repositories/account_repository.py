from sqlalchemy.orm import Session
from datetime import datetime
from persistence.models.account import Account


class AccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_account_id(self, account_id: str) -> Account | None:
        return self.session.query(Account).filter_by(account_id=account_id).first()

    def create_or_update(
        self,
        exchange: str,
        account_id: str,
        balance_total: float,
        balance_available: float,
        margin_used: float,
    ) -> Account:
        account = self.get_by_account_id(account_id)
        if not account:
            account = Account(
                exchange=exchange,
                account_id=account_id,
                balance_total=balance_total,
                balance_available=balance_available,
                margin_used=margin_used,
            )
            self.session.add(account)
        else:
            account.balance_total = balance_total
            account.balance_available = balance_available
            account.margin_used = margin_used
            account.updated_at = datetime.utcnow()

        self.session.commit()
        self.session.refresh(account)
        return account
