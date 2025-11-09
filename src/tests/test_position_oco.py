import asyncio


def test_create_oco_orders(position_manager, fake_rest_client):
    # Simular que ya hubo una entrada ejecutada con quantity en open_positions
    symbol = 'BTCUSDT'
    position_manager.open_positions[symbol] = {
        'order_params': {'quantity': 0.01}
    }

    signal = {
        'symbol': symbol,
        'type': 'BUY',
        'take_profit': 70000.0,
        'stop_loss': 30000.0
    }

    # Ejecutar la corutina create_oco_orders
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(position_manager.create_oco_orders({'orderId': 'ORD1', 'executedQty': '0.01'}, signal))
    finally:
        loop.close()

    # Verificar que se creó la entrada en open_positions
    assert 'oco' in position_manager.open_positions[symbol] or 'take_profit' in position_manager.open_positions[symbol] or 'stop_limit' in position_manager.open_positions[symbol]

