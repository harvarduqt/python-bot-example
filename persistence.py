from typing import Optional, Awaitable, Callable
from dotenv import load_dotenv
import asyncio, time
import websockets
import ssl
import os
import json

def make_client_ssl_context(ca_bundle: Optional[str] = None) -> ssl.SSLContext:
    """
    Create a strict SSL context:
    - Defaults to system trust store (best).
    - Falls back to certifi bundle if system store isn't usable.
    - If ca_bundle is provided, load that (PEM file) in addition to system roots.
    - Honors SSL_CERT_FILE / SSL_CERT_DIR if user sets them.
    """
    # Start with a secure default context (cert validation + hostname checking on)
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

    # If caller provided an explicit bundle, add it
    if ca_bundle:
        ctx.load_verify_locations(cafile=ca_bundle)
        return ctx

    # If user provided env overrides, default context already respects them.
    # But in minimal images (e.g., some containers) system roots may be missing.
    # In that case, try certifi as a fallback.
    try:
        # Test that we have any CA loaded (OpenSSL doesn't expose a direct check;
        # we'll attempt to add certifi only if explicitly requested or if desired).
        pass
    except Exception:
        pass

    # Optional fallback to certifi if you want guaranteed roots:
    try:
        import certifi  # add as a dependency if you want this fallback
        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        # If certifi not installed or load fails, we still have default context.
        # Let the connection error surface rather than silently disabling verify.
        pass

    return ctx


OnMessage = Callable[[bytes], Awaitable[None]]

class WSClient:
    def __init__(self, url: str, api_key: str, ctx):
        self.url = url
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._lock = asyncio.Lock()
        self._open_event = asyncio.Event()
        self._connecting_task: Optional[asyncio.Task] = None
        self.ready = asyncio.Event()
        self.api_key = api_key
        self.ctx = ctx

    async def connect(self) -> None:
        """
        Ensure there's an open connection. If already connecting, wait for it.
        Mirrors the TS logic (OPEN / CONNECTING checks).
        """
        async with self._lock:
            if self._ws and self._ws.open:
                self._open_event.set()
                return
            if self._connecting_task and not self._connecting_task.done():
                # Someone else is connecting; wait outside the lock
                pass
            else:
                self._open_event.clear()
                self._connecting_task = asyncio.create_task(self._do_connect())

        # Wait (outside the lock) for open or failure
        await self._open_event.wait()
        # If connection failed, propagate the exception from the task
        if self._connecting_task and self._connecting_task.done() and self._ws is None:
            self._connecting_task.result()  # raises

    async def _do_connect(self) -> None:
        try:
            # If your SDK needs attaching, do it here after connect.
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            self._ws = await websockets.connect(self.url, extra_headers=headers, ssl=self.ctx)
            # Example: oracle_py_sdk.attach(self._ws)  # if required
        except Exception:
            # Signal waiters that we won't open; leave ws as None
            self._ws = None
            self._open_event.set()
            raise
        else:
            self._open_event.set()

    async def send(self, data: bytes) -> None:
        await self.connect()
        if not self._ws or not self._ws.open:
            print("WebSocket not open — message dropped")
            return
        await self._ws.send(data)
    
        """Coroutine (not a generator): receive frames and call on_message(msg)."""
    async def listen(self, on_message, *, reconnect=True, retry_base=1, retry_max=30):
        backoff = retry_base
        try:
            while True:
                try:
                    await self.connect()
                    self.ready.set()  # signal connected
                    async for msg in self._ws:
                        await on_message(msg)
                    if not reconnect:
                        return
                except asyncio.CancelledError:
                    raise
                except websockets.InvalidStatusCode as e:
                    # This is raised if server rejects handshake (e.g. 401 Unauthorized)
                    if e.status_code == 401:
                        print("❌ Authentication failed (401 Unauthorized) — exiting listen loop")
                        return
                    else:
                        print(f"❌ Server rejected WebSocket connection with status {e.status_code}")
                        return
                except (OSError, websockets.ConnectionClosed) as e:
                    # transient errors: retry with backoff
                    print(f"⚠️ Connection error: {e}, retrying in {backoff}s")
                    await self.close()
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, retry_max)
                else:
                    backoff = retry_base
        finally:
            await self.close()

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

from huqt_oracle_pysdk.fbs_gen.gateway.ServerResponseUnion import ServerResponseUnion
from huqt_oracle_pysdk.fbs_gen.gateway.ServerResponse import ServerResponse
from huqt_oracle_pysdk.fbs_gen.gateway.TradesStream import TradesStream
from huqt_oracle_pysdk.request import ClientSetSessionRequest
from huqt_oracle_pysdk.subscribe import ClientTradeSubscription
from huqt_oracle_pysdk.fbs_gen.gateway import Side

def b2s(b):
    return b.decode("utf-8") if b is not None else None

async def message_handler(msg: bytes):
    buf = bytearray(msg)
    root = ServerResponse.GetRootAs(buf, 0)
    msg_type = root.ResponseType()

    if msg_type == ServerResponseUnion.TradesStream:
        ts = TradesStream()
        ts.Init(root.Response().Bytes, root.Response().Pos)
        market = b2s(ts.Market())
        trades = [
            {
                "market": market,
                "price": t.Px(),
                "size": t.Sz(),
                "taker_side": "buy" if t.TakerSide() == 0 else "sell",
                "time": t.Time(),
            }
            for t in (ts.Trades(i) for i in range(ts.TradesLength()))
        ]

        os.makedirs("logs", exist_ok=True)
        filepath = f"logs/{market}.json"

        with open(filepath, "a") as f:
            for trade in trades:
                json.dump(trade, f)
                f.write("\n")
        return
    
    else:
        return

async def main():
    load_dotenv()
    ctx = make_client_ssl_context()
    account_address = os.getenv("ACCOUNT_ADDRESS")
    api_key = os.getenv("API_KEY")
    ws_client = WSClient("wss://api.oracle.huqt.xyz/ws", api_key, ctx)
    await ws_client.connect()

    # set session
    _, raw_msg = ClientSetSessionRequest(
        domain = 'HarvardYale',
    ).to_bytes(account = account_address)
    await ws_client.send(raw_msg)

    await asyncio.sleep(3)

    # trade stream
    markets = ['HRVD', 'YALE', 'TIME', 'RAIN', 'PTS', 'TDS']
    for market in markets:
        _, raw_msg = ClientTradeSubscription(
            domain = 'HarvardYale',
            subscribe=True,
            market=market
        ).to_bytes()
        await ws_client.send(raw_msg)
    
    await asyncio.sleep(3)

    listen_task = asyncio.create_task(ws_client.listen(message_handler))

    try:
        await asyncio.Event().wait()
    except:
        pass
    finally:
        listen_task.cancel()
        await ws_client.close()

asyncio.run(main())