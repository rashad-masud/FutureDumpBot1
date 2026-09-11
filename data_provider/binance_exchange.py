from binance.client import Client
from binance.enums import *

class BinanceExchange:
    def __init__(self, api_key, api_secret, testnet=True):
        self.client = Client(api_key, api_secret)

        if testnet:
            self.client.API_URL = "https://testnet.binancefuture.com"

    def get_price(self, symbol: str) -> float:
        ticker = self.client.futures_mark_price(symbol=symbol)
        return float(ticker["markPrice"])

    def place_market_order(self, symbol, side, quantity):
        return self.client.futures_create_order(
            symbol=symbol,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=quantity,
        )
