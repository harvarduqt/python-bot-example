import asyncio
import os
from dotenv import load_dotenv
from dataclasses import dataclass
from aiohttp import web
from huqt_oracle_pysdk import OracleClient, Side, Tif

latest_positions: dict[str, int] = {}

@dataclass
class MarketConfig:
    fair: int
    spread: int
    position_ub: int
    position_lb: int
    quoting: bool


# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
configs: dict[str, MarketConfig] = {}
haorzhe = OracleClient()
meta = None
markets = []
# ----------------------------------------------------
# Ensure correct liquidity depth (only top-up if < 50%)
# ----------------------------------------------------
async def top_up_orders(
    market,
    orders,
    bid_price,
    ask_price,
    target_bid_sz,
    target_ask_sz,
):
    """Maintain exact target size at bid/ask price levels without relying on updated `orders`."""
    def filter_orders(price, side):
        return [o for o in orders if o["side"] == side and o["price"] == price]

    async def handle_side(price, side, target):
        side_str = "BID" if side == Side.Buy else "ASK"
        level_orders = filter_orders(price, side)

        # current total size
        current = sum(o["size"] for o in level_orders)

        # If target < 0 → nuke all
        if target < 0:
            print(f"[{market}] {side_str}: target < 0 → cancelling all orders")
            for o in level_orders:
                await haorzhe.cancel_order(market, o["oid"])
            return

        # ============================
        # Step 1: Reduce excess first
        # ============================

        excess = current - target
        if excess > 0:
            print(f"[{market}] {side_str}: reducing excess={excess}, current={current}, target={target}")

            # cancel highest oid first = worst queue
            for o in sorted(level_orders, key=lambda x: x["oid"], reverse=True):
                if excess <= 0:
                    break

                if o["size"] <= excess:
                    # fully cancel order
                    print(f"    cancel {side_str} {o['oid']} size={o['size']} (worst queue)")
                    await haorzhe.cancel_order(market, o["oid"])
                    excess -= o["size"]
                    current -= o["size"]
                else:
                    # trim by cancelling & replacing smaller
                    new_size = o["size"] - excess
                    print(f"    trim {side_str} {o['oid']} => new_size={new_size}")
                    await haorzhe.cancel_order(market, o["oid"])
                    await haorzhe.place_limit_order(market, side, price, new_size, Tif.Gtc)
                    current -= (o["size"] - new_size)
                    excess = 0

        # ============================
        # Step 2: Top-up if below target
        # ============================

        missing = target - current
        if missing > 0:
            print(f"[{market}] {side_str}: topping up missing={missing}, final_current={current}")
            await haorzhe.place_limit_order(market, side, price, missing, Tif.Gtc)

    # run both sides
    await handle_side(bid_price, Side.Buy,  target_bid_sz)
    await handle_side(ask_price, Side.Sell, target_ask_sz)




# ----------------------------------------------------
# Filter out *my* orders from the public book
# ----------------------------------------------------
def remove_self_orders_from_book(book, my_orders):
    """
    L2 book:
      bids: [{"price": int, "size": int}, ...]
      asks: [{"price": int, "size": int}, ...]

    We subtract my order sizes from the L2 sizes at my price levels.
    """

    # Aggregate my size by price level
    my_buy_sizes  = {}
    my_sell_sizes = {}

    for o in my_orders:
        if o["side"] == Side.Buy:
            my_buy_sizes[o["price"]] = my_buy_sizes.get(o["price"], 0) + o["size"]
        else:
            my_sell_sizes[o["price"]] = my_sell_sizes.get(o["price"], 0) + o["size"]

    # Clean bids
    clean_bids = []
    for lvl in book.get("bids", []):
        price = lvl["price"]
        size  = lvl["size"]

        my_size = my_buy_sizes.get(price, 0)
        new_size = size - my_size

        if new_size > 0:
            clean_bids.append({"price": price, "size": new_size})
        # else remove this level entirely

    # Clean asks
    clean_asks = []
    for lvl in book.get("asks", []):
        price = lvl["price"]
        size  = lvl["size"]

        my_size = my_sell_sizes.get(price, 0)
        new_size = size - my_size

        if new_size > 0:
            clean_asks.append({"price": price, "size": new_size})

    return {
        "bids": clean_bids,
        "asks": clean_asks
    }


# ----------------------------------------------------
# Mid-price helper (same as before)
# ----------------------------------------------------
def compute_mid(book):
    bids = book.get("bids", [])
    asks = book.get("asks", [])

    if not bids or not asks:
        return None

    best_bid = bids[0]["price"]
    best_ask = asks[0]["price"]

    return (best_bid + best_ask) // 2


# ----------------------------------------------------
# Cancel all orders not at correct bid/ask
# ----------------------------------------------------
async def prune_orders(market, orders, bid_price, ask_price):
    for o in orders:
        side = o["side"]
        price = o["price"]
        oid = o["oid"]

        if side == Side.Buy and price != bid_price:
            await haorzhe.cancel_order(market, oid)

        elif side == Side.Sell and price != ask_price:
            await haorzhe.cancel_order(market, oid)

# ----------------------------------------------------
# Cancel all orders not at correct bid/ask
# ----------------------------------------------------
async def im_out(market, orders):
    for o in orders:
        oid = o["oid"]
        await haorzhe.cancel_order(market, oid)


# ----------------------------------------------------
# Trading logic
# ----------------------------------------------------
async def trade_handler():
    print("\n\033[1;32m--- MID-PRICE (EXCLUDING SELF ORDERS) STARTED ---\033[0m")
    global latest_positions
    while True:
        # All markets' books
        # All my open orders (keyed by market)
        all_orders = haorzhe.get_self_open_orders()
        raw_positions = haorzhe.get_self_positions()
        
        agg_positions: dict[str, int] = {}
        for k, v in raw_positions.items():
            asset, _acct = k.split(":", 1)
            agg_positions[asset] = agg_positions.get(asset, 0) + v

        latest_positions = agg_positions  # expose to GUI

        for market in markets:
            base = None
            quote = None
            for m_meta in meta['Markets Metadata']:
                if market == m_meta['name']:
                    base = m_meta['base']
                    quote = m_meta['quote']
            if base is None or quote is None:
                continue
            cfg = configs.get(market, None)
            my_orders = all_orders.get(market, [])
            if cfg is None:
                await im_out(market, my_orders)
                continue

            if not cfg.quoting:
                await im_out(market, my_orders)
                continue
            bid_price = cfg.fair - cfg.spread // 2
            ask_price = bid_price + cfg.spread
            print(f"[{market}] bid={bid_price}, ask={ask_price}")

            # Step 1: Cancel wrong-price orders
            await prune_orders(market, my_orders, bid_price, ask_price)

            # Step 2: (optional, you commented out) top-up
            updated_orders = haorzhe.get_self_open_orders().get(market, [])
            positions = haorzhe.get_self_positions()
            pos = positions.get(f"{base}:main", 0) + positions.get(f"{base}:collateral", 0)
            await top_up_orders(market, updated_orders, bid_price, ask_price, target_bid_sz=cfg.position_ub - pos, target_ask_sz =  pos - cfg.position_lb)

        await asyncio.sleep(1.0)


def build_web_app():
    app = web.Application()

    async def index(request):
        # minimal HTML; frontend polls /api/status and posts to /api/config & /api/quoting
        return web.Response(
            content_type="text/html",
            text="""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>HUQT Market Maker Control</title>
<style>
  body { font-family: sans-serif; background:#111; color:#eee; }
  h2 { margin-top:30px; }
  table { border-collapse: collapse; width:100%; margin-top:10px; }
  th, td { border:1px solid #333; padding:6px 10px; }
  th { background:#222; }
  input { width:80px; }
  .panel { padding:15px; background:#181818; margin-top:15px; border-radius:8px; }
  .section { margin-bottom:25px; }
  .new-tag { color:#aaa; font-size:12px; margin-left:4px; }
</style>
</head>
<body>

<h1>HUQT Market Maker Dashboard</h1>

<!-- -------------------- LIVE VIEW -------------------- -->
<div class="section">
  <h2>📈 Live Market Status (read-only)</h2>
  <table id="status-table">
    <thead>
      <tr>
        <th>Market</th>
        <th>Pos</th>
        <th>Best Bid</th>
        <th>Best Ask</th>
        <th>Fair</th>
        <th>Spread</th>
        <th>LB</th>
        <th>UB</th>
        <th>Quoting</th>
        <th>Toggle</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</div>


<!-- -------------------- CONFIG EDITOR -------------------- -->
<div class="section panel">
  <h2>⚙️ Add or Edit Config</h2>

  <label>Select Market: </label>
  <select id="market-select"></select>
  <span id="cfg-status" style="margin-left:10px; font-size:14px; opacity:.7;"></span>

  <div id="config-form" style="margin-top:10px;">
    <p id="config-header"></p>

    <label>Fair: <input type="number" id="edit-fair"></label>
    <label>Spread: <input type="number" id="edit-spread"></label>
    <label>Pos LB: <input type="number" id="edit-lb"></label>
    <label>Pos UB: <input type="number" id="edit-ub"></label>
    <br><br>

    <button id="save-btn">💾 Save Config</button>
  </div>
</div>


<script>
// -------------------------------------------
// GLOBAL
// -------------------------------------------
let windowInit = false;
let cachedMarkets = [];


// -------------------------------------------
// POPULATE LIVE STATUS TABLE
// -------------------------------------------
async function fetchStatus() {
  const res = await fetch('/api/status');
  const data = await res.json();
  cachedMarkets = data.markets;

  if (!windowInit) {
    populateDropdown();       // <-- NEW
    loadEditorConfig(cachedMarkets[0].name);
    windowInit = true;
  }

  const tbody = document.querySelector('#status-table tbody');
  tbody.innerHTML = '';

  for (const m of data.markets) {
    const tr = document.createElement('tr');
    const toggleDisabled = m.has_config ? '' : 'disabled';

    tr.innerHTML = `
        <td>${m.name}</td>
        <td>${m.position}</td>
        <td>${m.best_bid ?? '-'}</td>
        <td>${m.best_ask ?? '-'}</td>
        <td>${m.config ? m.config.fair : '-'}</td>
        <td>${m.config ? m.config.spread : '-'}</td>
        <td>${m.config ? m.config.position_lb : '-'}</td>
        <td>${m.config ? m.config.position_ub : '-'}</td>
        <td>${m.config && m.config.quoting ? '🟢 ON' : '🔴 OFF'}</td>
        <td><button data-toggle="${m.name}" ${toggleDisabled}>Toggle</button></td>
    `;
    tbody.appendChild(tr);
    }
}

setInterval(fetchStatus, 1000);
fetchStatus();


// -------------------------------------------
// DROPDOWN + CONFIG EDITOR
// -------------------------------------------
function populateDropdown() {
  const sel = document.getElementById('market-select');
  sel.innerHTML = "";

  cachedMarkets.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.name;
    opt.textContent = m.name + (m.has_config ? "" : " (new)"); // <-- NEW LABEL
    sel.appendChild(opt);
  });
}

async function loadEditorConfig(market) {
  const row = cachedMarkets.find(m => m.name === market);

  document.getElementById("cfg-status").textContent =
      row.has_config ? "Editing existing config" : "Creating new config";

  document.getElementById("config-header").textContent =
      `${market} — Configuration`;

  document.getElementById("edit-fair").value   = row.config.fair;
  document.getElementById("edit-spread").value = row.config.spread;
  document.getElementById("edit-lb").value     = row.config.position_lb;
  document.getElementById("edit-ub").value     = row.config.position_ub;
}

document.getElementById('market-select').addEventListener('change', e => {
  loadEditorConfig(e.target.value);
});

document.getElementById('save-btn').addEventListener('click', async () => {
  const market = document.getElementById('market-select').value;

  const body = {
    market,
    fair: Number(document.getElementById('edit-fair').value),
    spread: Number(document.getElementById('edit-spread').value),
    position_lb: Number(document.getElementById('edit-lb').value),
    position_ub: Number(document.getElementById('edit-ub').value)
  };

  console.log("Sending config update:", body); // debug

  await fetch('/api/config', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });

  cachedMarkets.find(m => m.name === market).has_config = true;
  populateDropdown();
  loadEditorConfig(market);
  fetchStatus();
});



// -------------------------------------------
// QUOTING TOGGLE
// -------------------------------------------
document.addEventListener('click', async e => {
  const m = e.target.getAttribute('data-toggle');
  if (!m) return;

  await fetch('/api/quoting', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({market:m})
  });

  fetchStatus();
});
</script>

</body>
</html>


            """,
        )

    async def api_status(request):
        result = []

        books = haorzhe.get_book()   # {"BTC": {"bids":[...], "asks":[...]}}
        pos_raw = latest_positions   # {"BTC": total_position, ...}

        for m in markets:
            base = None
            quote = None
            for m_meta in meta["Markets Metadata"]:
                if m == m_meta["name"]:
                    base = m_meta["base"]
                    quote = m_meta["quote"]
                    break

            if base is None or quote is None:
                continue

            cfg = configs.get(m, None)
            position = pos_raw.get(base, 0)

            book = books.get(m, {"bids": [], "asks": []})
            bids = book.get("bids", [])
            asks = book.get("asks", [])

            # ---- Best L1 ----
            best_bid = bids[0]["price"] if bids else None
            best_ask = asks[0]["price"] if asks else None

            result.append({
                "name": m,
                "base": base,
                "quote": quote,
                "position": position,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "has_config": cfg is not None,
                "config": None if cfg is None else {
                    "fair": cfg.fair,
                    "spread": cfg.spread,
                    "position_lb": cfg.position_lb,
                    "position_ub": cfg.position_ub,
                    "quoting": cfg.quoting,
                }
            })

        return web.json_response({"markets": result})


        return web.json_response({"markets": result})


    async def api_config(request):
        body = await request.json()
        market = body.get("market")
        if not market or market not in markets:
            return web.json_response({"error": "unknown market"}, status=400)

        cfg = MarketConfig(0, 0, 0, 0, False)
        # update fields if provided
        if "fair" in body:
            cfg.fair = int(body["fair"])
        if "spread" in body:
            cfg.spread = int(body["spread"])
        if "position_lb" in body:
            cfg.position_lb = int(body["position_lb"])
        if "position_ub" in body:
            cfg.position_ub = int(body["position_ub"])
        configs[market] = cfg
        return web.json_response({"ok": True})

    async def api_quoting(request):
        body = await request.json()
        market = body.get("market")
        if not market or market not in configs:
            return web.json_response({"error": "unknown market"}, status=400)

        cfg = configs[market]
        cfg.quoting = not cfg.quoting
        return web.json_response({"ok": True, "quoting": cfg.quoting})

    app.router.add_get("/", index)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/config", api_config)
    app.router.add_post("/api/quoting", api_quoting)

    return app

# ----------------------------------------------------
# Main
# ----------------------------------------------------
async def main():
    load_dotenv()
    account_address = os.getenv("ACCOUNT_ADDRESS")
    api_key = os.getenv("API_KEY")
    global markets
    global meta
    await haorzhe.start_client(
        account=account_address,
        api_key=api_key,
        domain="HarvardYale"
    )

    meta = haorzhe.get_domain_metadata()
    markets = meta['Available Markets']['markets']
    for market in markets:
        await haorzhe.subscribe_market(market)

    trade_task = asyncio.create_task(trade_handler())

    # start web server
    app = build_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8080)
    await site.start()
    print("Web GUI running on http://localhost:8080")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        trade_task.cancel()
        try:
            await trade_task
        except asyncio.CancelledError:
            pass
        await haorzhe.stop_client()
        await runner.cleanup()
        print("\033[1;31mTrading bot stopped.\033[0m")


if __name__ == "__main__":
    asyncio.run(main())
