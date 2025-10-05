# trading-bot-example

First, make a virtual environment:
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

## Useful Write States Endpoints (all sync):
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