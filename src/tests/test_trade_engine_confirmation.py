import asyncio
from contracts.signal_contract import ValidatedSignal
from engine.trade_engine import TradeEngine
from position.position_manager import PositionManager
from utils.logger import Logger
import time

logger = Logger.get_logger(__name__)

class RejectedFakeRestClient:
    def __init__(self):
        self._price = 50000.0
    def get_symbol_price(self, symbol):
        return self._price
    def get_exchange_info(self):
        return {"symbols": [{"symbol": "BTCUSDT", "filters": [{"filterType":"MIN_NOTIONAL","minNotional":"10"},{"filterType":"LOT_SIZE","minQty":"0.0001","maxQty":"100","stepSize":"0.0001"}]}]}
    def get_usdt_balance(self):
        return 1000.0
    def get_open_orders(self, symbol=None):
        return []
    def create_order(self, symbol, side, type_, quantity, *args, **kwargs):
        # Simular rechazo (None respuesta)
        return None

class SuccessFakeRestClient:
    def __init__(self):
        self._price = 50000.0
    def get_symbol_price(self, symbol):
        return self._price
    def get_exchange_info(self):
        return {"symbols": [{"symbol": "BTCUSDT", "filters": [{"filterType":"MIN_NOTIONAL","minNotional":"10"},{"filterType":"LOT_SIZE","minQty":"0.0001","maxQty":"100","stepSize":"0.0001"}]}]}
    def get_usdt_balance(self):
        return 1000.0
    def get_open_orders(self, symbol=None):
        return []
    def create_order(self, symbol, side, type_, quantity, *args, **kwargs):
        # Respuesta simulada exitosa con executedQty y cummulativeQuoteQty
        executed_qty = float(quantity)
        price = 50000.0
        cumm_quote = executed_qty * price
        return {'orderId':'ORD1','symbol':symbol,'status':'FILLED','executedQty':str(executed_qty),'origQty':str(quantity),'cummulativeQuoteQty':str(cumm_quote)}

async def run_handle_buy_with_client(rest_client, confirmation_queue):
    # preparar engine con el cliente falso
    signal_queue = asyncio.Queue()
    engine = TradeEngine(signal_queue=signal_queue, bot_id=1, run_db_id=1, rest_client=rest_client, confirmation_queue=confirmation_queue)
    # construir señal válida mínima
    signal = {
        'symbol': 'BTCUSDT',
        'type': 'BUY',
        'price': 50000.0,
        'position_size_usdt': 10.0,
        'risk_params': {},
        'strategy_name': 'BTC_Daily_Open'
    }
    await engine._handle_buy(signal)
    # esperar pequeña pausa
    await asyncio.sleep(0.01)
    return engine

def test_rejected_order_does_not_open_position():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        confirmation_queue = asyncio.Queue()
        engine = loop.run_until_complete(run_handle_buy_with_client(RejectedFakeRestClient(), confirmation_queue))
        # revisar confirmation_queue
        got = None
        try:
            got = loop.run_until_complete(asyncio.wait_for(confirmation_queue.get(), timeout=0.5))
        except Exception:
            got = None
        # en caso de rechazo esperamos un mensaje REJECTED
        assert got is not None and got.get('status') == 'REJECTED'
        # position_manager no debe tener posición abierta
        assert 'BTCUSDT' not in engine.position_manager.open_positions
    finally:
        loop.close()

def test_successful_order_registers_position_and_confirmation():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        confirmation_queue = asyncio.Queue()
        engine = loop.run_until_complete(run_handle_buy_with_client(SuccessFakeRestClient(), confirmation_queue))
        # obtener confirmacion
        got = loop.run_until_complete(asyncio.wait_for(confirmation_queue.get(), timeout=1.0))
        assert got is not None and got.get('status') == 'OPEN'
        # verificar executed_qty y avg_price presentes
        assert 'executed_qty' in got and got['executed_qty'] is not None
        assert 'avg_price' in got and got['avg_price'] is not None
        # position_manager debe tener posición registrada
        assert 'BTCUSDT' in engine.position_manager.open_positions
        pos = engine.position_manager.open_positions['BTCUSDT']
        assert pos.get('executed_qty') is not None
        assert pos.get('avg_price') is not None
    finally:
        loop.close()

