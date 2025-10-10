# trading-bot-example

First, make sure the python version is greater than 3.10.
You can check this by running one of:
```bash
python --version
python3 --version
``` 
If your python is 3.9 or lower, you can upgrade it by either
```bash
brew upgrade python
```
or simply go to [python.org/downloads](https://python.org/downloads) and download a newer version.

Next, make a virtual environment:
```bash
python -m venv .venv
```
Then, activate the environment: 
```bash 
source .venv/bin/activate
```
Or on Windows (Powershell):
```bash
.venv\Scripts\activate
```

To install the python sdk package, run the following:
```bash
pip install huqt_oracle_pysdk
```
To update the package, run 
```bash
pip install --update huqt_oracle_pysdk
```
The current version should be v0.1.3.

Create an .env file for your account address and API key (no space, no quotation mark)
```
ACCOUNT_ADDRESS=00000000-0000-0000-0000-000000000000
API_KEY=00000000-0000-0000-0000-000000000000

```
To obtain your key go to the oracle website and go to your account page.
Press copy beside your account name. In the same page there should be a API-keys tab,
you can use any of the keys.

Run the file by:
```bash
python example.py
```

## Useful Read States Endpoints (all sync):
```python
def get_self_open_orders(self) -> dict[str, list]:
def get_self_open_auction_orders(self) -> dict[str, list]:
def get_self_positions(self) -> dict[str, int]:
def get_self_recent_fills(self) -> list[dict]:
def get_book(self) -> dict[str, dict[str, int]]:
def get_recent_trades(self) -> dict[str, list]:
def get_oracle_metadata(self) -> dict[str, list]:
def get_domain_metadata(self) -> dict:
def get_self_pending_orders(self) -> dict[str, tuple[int, dict]]:
def get_self_pending_requests(self) -> dict[str, tuple[int, str, dict]]:
def get_issued_options_quantity(self, is_global: bool = False) -> dict[str, int]:
```

## Useful Write States Endpoints (all async):
```python
async def place_limit_order(self, market: str, side: int, price: int, size: int, tif: int):
async def place_market_order(self, market: str, side: int, collateral: int):
async def place_auction_order(self, market: str, price: int):
async def deposit(self, symbol: str, amount: int):
async def withdraw(self, symbol: str, amount: int):
async def convert(self, conversion: str, size: int):
async def issue_option(self, name, size):
async def exercise_option(self, name, size):
```