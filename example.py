from huqt_oracle_pysdk import OracleClient, Side, Tif
from dotenv import load_dotenv
import asyncio
import os

## Update the markets list to keep track of those markets.
haorzhe = OracleClient()
markets = ["110"]

async def trade_handler():
    print("\n\033[1;32m-------- Below are the logs for user algorithm --------\033[0m")
    print(haorzhe.get_self_positions())
    await haorzhe.place_limit_order("110", Side.Buy, 200, 1, Tif.Gtc)

## ------------ DO NOT CHANGE BELOW THIS LINE ------------
async def main():
    load_dotenv()
    account_address = os.getenv("ACCOUNT_ADDRESS")
    api_key = os.getenv("API_KEY")

    await haorzhe.start_client(
        account=account_address,
        api_key=api_key,
        domain="Oracle"
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