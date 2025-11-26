from huqt_oracle_pysdk import OracleClient, Side, Tif
import asyncio
from datetime import datetime, timedelta
import os

## Update the markets list to keep track of those markets.
jwu = OracleClient()
markets = ['TIME', 'SUM', 'TDS', 'DIFF', 'HRVD', 'YALE']
min_sell = {'YALE': 500}                    # Long positions
min_spread = {'YALE': 4, 'HRVD': 4}         # Minimum spread to place orders
starting_bal = 77000                        # Balance to not go below
end_time = datetime(2025, 11, 22, 16, 54, 0)

async def trade_handler():
    last_tick = datetime.now()
    index = -1
    
    while datetime.now() < end_time:
        index = (index + 1) % len(markets)
        if datetime.now() - last_tick > timedelta(milliseconds=15000):
            last_tick = datetime.now()

        
        book: dict[str, dict[str, list[dict[str, int]]]] = jwu.get_book()
        contract = markets[index]
        contract_book = book[contract]
        bids = contract_book['bids']
        asks = contract_book['asks']
        dominant_bid = max(x['price'] for x in bids) if bids else None
        dominant_ask = min(x['price'] for x in asks) if asks else None
        
        if not dominant_bid or not dominant_ask:
            await asyncio.sleep(1/100)
            continue
        
        our_total_orders = jwu.get_self_open_orders()
        our_orders = our_total_orders.get(contract, [])
        our_total_open_contracts = jwu.get_self_positions()
        our_open_contracts = our_total_open_contracts.get(contract + ":main", 0)  - min_sell.get(contract, 0)
        spread = dominant_ask - dominant_bid
        budget = min(3600, our_total_open_contracts["QTC:main"] - starting_bal)
        
        n_at_dominant_bid = sum([o['size'] for o in bids if o['price'] == dominant_bid])
        n_at_dominant_ask = sum([o['size'] for o in asks if o['price'] == dominant_ask])

        if our_orders:
            # See if we need to adjust
            submitted_orders = 0
            for order in our_orders:
                if order['side'] == Side.Buy and order['price'] < dominant_bid:
                    if n_at_dominant_bid >= 8:
                        # Cancel and replace
                        budget += order['size'] * order['price']
                        await jwu.cancel_order(contract, order['oid'])
                        if spread >= min_spread.get(contract, 2):
                            new_size = order['size'] if spread >= 4 else min(order['size'], 3)
                            budget -= new_size * dominant_bid
                            await jwu.place_limit_order(contract, Side.Buy, dominant_bid, new_size, Tif.Gtc)
                            submitted_orders += 1
                
                elif order['side'] == Side.Buy:
                    # Check if we are alone at our price based on size of our orders vs size in the book
                    our_size = sum([o['size'] for o in our_orders if o['price'] == order['price']])
                    same_price_orders = sum([o['size'] for o in bids if o['price'] == order['price']])
                    next_highest_bid = max([o['price'] for o in bids if o['price'] < order['price']], default=0)
                    if same_price_orders <= our_size + 4 and order['price'] - next_highest_bid >= 2:
                        n_at_next_highest_bid = sum([o['size'] for o in bids if o['price'] == next_highest_bid])
                        # We are alone at this price, adjust to be more competitive
                        budget += order['size'] * order['price']
                        await jwu.cancel_order(contract, order['oid'])
                        new_price = next_highest_bid + 1 if n_at_next_highest_bid >= 20 else next_highest_bid
                        assert new_price < order['price']
                        new_size = order['size'] if spread >= 4 else min(order['size'], 3)
                        budget -= new_size * new_price
                        await jwu.place_limit_order(contract, Side.Buy, new_price, new_size, Tif.Gtc)
                        submitted_orders += 1
                
                elif order['side'] == Side.Sell and order['price'] > dominant_ask:
                    if n_at_dominant_ask >= 4:
                        # Cancel and replace
                        await jwu.cancel_order(contract, order['oid'])
                        await jwu.place_limit_order(contract, Side.Sell, dominant_ask, order['size'], Tif.Gtc)
                        submitted_orders += 1
                
                elif order['side'] == Side.Sell:
                    # Check if we are alone at our price based on size of our orders vs size in the book
                    our_size = sum([o['size'] for o in our_orders if o['price'] == order['price']]) # order['size']
                    same_price_orders = sum([o['size'] for o in asks if o['price'] == order['price']])
                    next_lowest_ask = min([o['price'] for o in asks if o['price'] > order['price']], default=999999)
                    if same_price_orders <= our_size + 3 and next_lowest_ask - order['price'] >= 2:
                        n_at_next_lowest_ask = sum([o['size'] for o in asks if o['price'] == next_lowest_ask])
                        # We are alone at this price, adjust to be more competitive
                        await jwu.cancel_order(contract, order['oid'])
                        new_price = next_lowest_ask - 1 if n_at_next_lowest_ask >= 20 else next_lowest_ask
                        assert new_price > order['price']
                        await jwu.place_limit_order(contract, Side.Sell, new_price, order['size'], Tif.Gtc)
                        submitted_orders += 1
            
            # END FOR
            if submitted_orders > 0:
                await asyncio.sleep(min(1, submitted_orders / 50))
                continue
        
        if our_open_contracts > 0:
            await create_sell(dominant_ask, n_at_dominant_ask, our_open_contracts, our_orders, contract, dominant_bid)
        
        if spread >= min_spread.get(contract, 3):
            pending_size = our_open_contracts + sum([o["size"] for o in our_orders if o['side'] == Side.Buy])
            buy_price = dominant_bid + 1 if spread > 3 and n_at_dominant_bid >= 20 else dominant_bid
            sell_price = dominant_ask - 1
            quantity = 3
            if spread >= 4:
                quantity = 5
            if budget >= quantity * buy_price and pending_size < 6:
                budget -= quantity * buy_price
                await jwu.place_limit_order(contract, Side.Buy, buy_price, quantity, Tif.Gtc)
                await asyncio.sleep(1 / 50)  # Can only place 50 orders per second
        
        # Spread too tight, whatever
        await asyncio.sleep(1 / 100)

async def finalize_orders():
    # Cancel all open orders, create sell orders for all open contracts
    book: dict[str, dict[str, list[dict[str, int]]]] = jwu.get_book()
    our_total_orders = jwu.get_self_open_orders()
    
    for contract in markets:
        our_orders = our_total_orders.get(contract, [])
        our_open_contracts = jwu.get_self_positions().get(contract + ":main", 0) - min_sell.get(contract, 0)
        
        # contract = markets[index]
        contract_book = book[contract]
        bids = contract_book['bids']
        asks = contract_book['asks']
        dominant_bid = max(x['price'] for x in bids) if bids else None
        dominant_ask = min(x['price'] for x in asks) if asks else None

        if not dominant_bid or not dominant_ask:
            await asyncio.sleep(1/100)
            continue

        if our_orders:  # See if we need to adjust
            for order in our_orders:
                if order['side'] == Side.Buy:
                    # Cancel
                    await jwu.cancel_order(contract, order['oid'])
                elif order['side'] == Side.Sell and order['price'] < dominant_ask:
                    # Cancel and replace
                    await jwu.cancel_order(contract, order['oid'])
                    await jwu.place_limit_order(contract, Side.Sell, dominant_ask, order['size'], Tif.Gtc)
                elif order['side'] == Side.Sell:
                    # Check if we are alone at our price based on size of our orders vs size in the book
                    our_size = order['size']
                    same_price_orders = sum([o['size'] for o in asks if o['price'] == order['price']])
                    next_lowest_ask = min([o['price'] for o in asks if o['price'] > order['price']], default=999999)
                    if same_price_orders == our_size and next_lowest_ask - order['price'] >= 2:
                        # We are alone at this price, adjust to be more competitive
                        await jwu.cancel_order(contract, order['oid'])
                        new_price = next_lowest_ask - 1
                        assert new_price > order['price']
                        await jwu.place_limit_order(contract, Side.Sell, new_price, order['size'], Tif.Gtc)
            # END FOR
        if our_open_contracts > 0:
            n_at_dominant_ask = sum([o['size'] for o in asks if o['price'] == dominant_ask])
            await create_sell(dominant_ask, n_at_dominant_ask, our_open_contracts, our_orders, contract, dominant_bid)

        await asyncio.sleep(1 / 100)

async def create_sell(dominant_ask, n_at_dominant_ask, our_open_contracts, our_orders, contract, dominant_bid):
    # Submit limit sell order if we don't already have one
    sell_price = dominant_ask - 1 if n_at_dominant_ask >= 20 and dominant_ask - 1 > dominant_bid else dominant_ask
    quantity = our_open_contracts - sum([o["size"] for o in our_orders if o['side'] == Side.Sell])
    if quantity > 0:
        await jwu.place_limit_order(contract, Side.Sell, sell_price, quantity, Tif.Gtc)

## ------------ DO NOT CHANGE BELOW THIS LINE ------------
async def main():    
    await jwu.start_client(
        account = os.getenv("ACCOUNT_ID"),
        api_key = os.getenv("API_KEY"),
        domain="HarvardYale"
    )
    
    for market in markets:
        await jwu.subscribe_market(market)

    try:
        # CTRL-C to stop
        await trade_handler()
        await finalize_orders()
    except:
        import traceback
        traceback.print_exc()
    finally:
        await jwu.stop_client()
        print("\033[1;31mOracleClient stopped. See ya next time...\033[0m\n")

if __name__ == "__main__":
    asyncio.run(main())