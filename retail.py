from huqt_oracle_pysdk import OracleClient, Side, Tif
from dotenv import load_dotenv
import numpy as np
import requests, asyncio, os

polygon_key = os.getenv("POLYGON_KEY")

class contract:
    def __init__(self, name: str, frequency: float):
        self.name = name
        self.fair = None
        self.frequency = frequency
    
    async def trade(self, prices):
        # wait time is inverse frequency
        wait_time = np.random.exponential(scale=1.0 / self.frequency, size=100)
        await asyncio.sleep(wait_time)
        if not self.fair: return

        # flip a coin to decide side
        side = np.random.choice([Side.Buy, Side.Sell])
        price = prices[side]
        if price and side == Side.Buy:
            if price <= self.fair + 5:
                await haorzhe.place_limit_order(market = self.name, side=Side.Buy, price=price, size=1, tif=Tif.Ioc)
                print(f'Bought {self.name} for price {price}')
        if price and side == Side.Sell:
            if price >= self.fair - 5:
                await haorzhe.place_limit_order(market = self.name, side=Side.Sell, price=price, size=1, tif=Tif.Ioc)
                print(f'Sold {self.name} for price {price}')

## Update the markets list to keep track of those markets.
haorzhe = OracleClient()
markets = ['tVIX5', 'tCMP']
tVIX = contract(name='tVIX5', frequency=0.1)
tCMP = contract(name='tCMP', frequency=0.1)
contracts = [tVIX, tCMP]

async def trade_handler():
    while True:
        snap = requests.get(f"https://api.polygon.io/v3/snapshot/indices", params={"ticker": "I:VIX", "apiKey": polygon_key}).json()
        vix_meta = snap['results'][0]
        tVIX.fair = int(vix_meta['value'] * 5.0)
        tCMP.fair = 300 - tVIX.fair

        book = haorzhe.get_book()
        for contract in contracts:
            contract_book = book[contract.name]
            buys = contract_book['bids']
            sells = contract_book['asks']

            best_buy = buys[0]['price'] if buys else None
            best_sell = sells[0]['price'] if sells else None

            # needs to flip them so that it's the other way
            await contract.trade([best_sell, best_buy])        

## ------------ DO NOT CHANGE BELOW THIS LINE ------------
async def main():
    load_dotenv()
    account_address = os.getenv("ACCOUNT_ADDRESS")
    api_key = os.getenv("API_KEY")

    await haorzhe.start_client(
        account=account_address,
        api_key=api_key,
        domain="test"
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