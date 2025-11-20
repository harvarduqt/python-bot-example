from huqt_oracle_pysdk import OracleClient, Side, Tif
from dotenv import load_dotenv
import numpy as np
import requests, asyncio, os

# class contract:
#     def __init__(self, name: str, frequency: float):
#         self.name = name
#         self.fair = None
#         self.frequency = frequency
    
#     async def trade(self, prices):
#         # wait time is inverse frequency
#         wait_time = np.random.exponential(scale=1.0 / self.frequency)
#         await asyncio.sleep(wait_time)
#         if not self.fair: return

#         # flip a coin to decide side
#         side = np.random.choice([Side.Buy, Side.Sell])
#         price = prices[side]
#         print(f'attempt to trade on contract {self.name} wait time = {wait_time} with fair = {self.fair} at price = {price}')
#         if price and side == Side.Buy:
#             if price <= self.fair + 5:
#                 await haorzhe.place_limit_order(market = self.name, side=Side.Buy, price=price, size=1, tif=Tif.Ioc)
#                 print(f'Bought {self.name} for price {price}')
#         if price and side == Side.Sell:
#             if price >= self.fair - 5:
#                 await haorzhe.place_limit_order(market = self.name, side=Side.Sell, price=price, size=1, tif=Tif.Ioc)
#                 print(f'Sold {self.name} for price {price}')

## Update the markets list to keep track of those markets.
haorzhe = OracleClient()
markets = ['HRVD', 'YALE', 'TIME', 'RAIN', 'TDS', 'PTS']

async def trade_handler():
    while True:
        # snap = requests.get(f"https://api.polygon.io/v3/snapshot/indices", params={"ticker": "I:VIX", "apiKey": 'g4OC2SA8TmEm9RBrD2UfAXnClXwdlHxf'}).json()
        # vix_meta = snap['results'][0]
        # tVIX.fair = int(vix_meta['value'] * 5.0)
        # tCMP.fair = 300 - tVIX.fair

        book = haorzhe.get_book()
        contract = np.random.choice(markets)
        contract_book = book[contract]
        buys = contract_book['bids']
        sells = contract_book['asks']

        best_buy = buys[0]['price'] if buys else None
        best_sell = sells[0]['price'] if sells else None

        side = np.random.choice([Side.Buy, Side.Sell])
        if side == Side.Buy:
            x = max(int(np.random.normal(3, 1)), 1)
            print(f'buying {contract} at price {best_sell} for {x} quantity')
            await haorzhe.place_limit_order(contract, side, best_sell, x, Tif.Ioc)
        if side == Side.Sell:
            x = max(int(np.random.normal(3, 1)), 1)
            print(f'selling {contract} at price {best_buy} for {x} quantity')
            await haorzhe.place_limit_order(contract, side, best_buy, x, Tif.Ioc)

        await asyncio.sleep(0.5)

## ------------ DO NOT CHANGE BELOW THIS LINE ------------
async def main():
    load_dotenv()
    account_address = os.getenv("ACCOUNT_ADDRESS")
    api_key = os.getenv("API_KEY")

    await haorzhe.start_client(
        account=account_address,
        api_key=api_key,
        domain="HarvardYale"
    )
    
    for market in markets:
        await haorzhe.subscribe_market(market)
    
    task = asyncio.create_task(trade_handler())
    try:
        # CTRL-C to stop
        await asyncio.Event().wait()
    except:
        pass
    finally:
        task.cancel()
        await haorzhe.stop_client()
        print("\033[1;31mOracleClient stopped. See ya next time...\033[0m\n")

if __name__ == "__main__":
    asyncio.run(main())