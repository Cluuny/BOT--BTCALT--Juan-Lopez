from sqlalchemy.orm import Session
from typing import Optional, List
from persistence.models.symbol_info import SymbolInfo


class SymbolInfoRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, **kwargs) -> SymbolInfo:
        symbol = kwargs.get("symbol")
        if not symbol:
            raise ValueError("symbol is required")
        existing = self.session.query(SymbolInfo).filter_by(symbol=symbol).first()
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            self.session.commit()
            self.session.refresh(existing)
            return existing
        inst = SymbolInfo(**kwargs)
        self.session.add(inst)
        self.session.commit()
        self.session.refresh(inst)
        return inst

    def bulk_upsert(self, items: List[dict]) -> List[SymbolInfo]:
        results: List[SymbolInfo] = []
        for item in items:
            results.append(self.upsert(**item))
        return results

    def get(self, symbol: str) -> Optional[SymbolInfo]:
        return self.session.query(SymbolInfo).filter_by(symbol=symbol).first()

    def list_all(self) -> List[SymbolInfo]:
        return self.session.query(SymbolInfo).all()
