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
        margin_used: float = 0.0,
        account_type: str = "SPOT",
        can_trade: bool = True,
        maker_commission: float | None = None,
        taker_commission: float | None = None,
        permissions: dict | None = None,
        last_synced_at: datetime | None = None,
    ) -> Account:
        account = self.get_by_account_id(account_id)
        if not account:
            account = Account(
                exchange=exchange,
                account_id=account_id,
                balance_total=balance_total,
                balance_available=balance_available,
                margin_used=margin_used,
                account_type=account_type,
                can_trade=can_trade,
                maker_commission=maker_commission or 0.0,
                taker_commission=taker_commission or 0.0,
                permissions=permissions,
                last_synced_at=last_synced_at or datetime.utcnow(),
            )
            self.session.add(account)
        else:
            account.exchange = exchange
            account.balance_total = balance_total
            account.balance_available = balance_available
            account.margin_used = margin_used
            account.account_type = account_type
            account.can_trade = can_trade
            if maker_commission is not None:
                account.maker_commission = maker_commission
            if taker_commission is not None:
                account.taker_commission = taker_commission
            if permissions is not None:
                account.permissions = permissions
            account.last_synced_at = last_synced_at or datetime.utcnow()
            account.updated_at = datetime.utcnow()

        self.session.commit()
        self.session.refresh(account)
        return account
