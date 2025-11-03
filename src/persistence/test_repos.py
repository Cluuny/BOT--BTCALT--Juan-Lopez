import unittest
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from persistence.db_connection import db

from persistence.repositories.bot_config_repository import BotConfigRepository
from persistence.repositories.account_repository import AccountRepository
from persistence.repositories.log_repository import LogRepository
from persistence.repositories.order_repository import OrderRepository
from persistence.repositories.signal_repository import SignalRepository
from persistence.repositories.trade_repository import TradeRepository
from persistence.repositories.performance_stats_repository import (
    PerformanceStatsRepository,
)
from utils.logger import Logger


logger = Logger.get_logger(__name__)


def run_repository_tests():
    class TestRepositories(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.session: Session = db.get_session()
            cls.session.begin()
            logger.info("\n🔍 Iniciando pruebas de repositories...")

        @classmethod
        def tearDownClass(cls):
            cls.session.rollback()
            cls.session.close()
            logger.info("\n✅ Pruebas de repositories finalizadas.\n")

        def test_repositories(self):
            try:
                # Crear bot base para las relaciones
                bot_repo = BotConfigRepository(self.session)
                bot = bot_repo.create_if_not_exists("test_bot", "BINANCE", "TESTNET")
                bot_id = bot.id

                # Account
                acc_repo = AccountRepository(self.session)
                acc_repo.create_or_update("BINANCE", "acc_test_1", 1000, 800, 200)
                logger.info("✅ AccountRepository OK")

                # Log
                log_repo = LogRepository(self.session)
                log_repo.add_log(bot_id=bot_id, level="INFO", message="Test log")
                logger.info("✅ LogRepository OK")

                # Order
                order_repo = OrderRepository(self.session)
                order = order_repo.create(
                    bot_id=bot_id,
                    signal_id=None,
                    exchange_order_id="ORD123",
                    symbol="BTCUSDT",
                    side="BUY",
                    type="LIMIT",
                    price=68000.5,
                    quantity=0.01,
                )
                logger.info("✅ OrderRepository OK")

                # Signal
                sig_repo = SignalRepository(self.session)
                sig_repo.create(
                    bot_id=bot_id,
                    strategy_name="EMA_Cross",
                    symbol="BTCUSDT",
                    direction="BUY",
                    price=68000.5,
                )
                logger.info("✅ SignalRepository OK")

                # Trade
                trade_repo = TradeRepository(self.session)
                trade_repo.create(
                    bot_id=bot_id,
                    order_id=order.id,
                    entry_price=68000,
                    position_size=0.01,
                )
                logger.info("✅ TradeRepository OK")

                # Performance
                perf_repo = PerformanceStatsRepository(self.session)
                perf_repo.create_or_update_daily(
                    bot_id,
                    pnl_total=150.5,
                    win_rate=75.0,
                    max_drawdown=10.0,
                    profit_factor=1.8,
                    total_trades=10,
                )
                logger.info("✅ PerformanceStatsRepository OK")

            except Exception as e:
                self.fail(f"❌ Error durante pruebas de repositories: {e}")

    unittest.TextTestRunner().run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestRepositories)
    )
