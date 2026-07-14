import ccxt

exchange = ccxt.okx({
    'options': {'defaultType': 'swap'}  # perpetual futures
})

markets = exchange.fetch_tickers()

# Filter USDT pairs, sort by open interest
usdt_markets = {
    k: v for k, v in markets.items() 
    if k.endswith('/USDT:USDT') and v.get('baseVolume')
}




sorted_markets = sorted(
    usdt_markets.items(),
    key=lambda x: x[1].get('baseVolume', 0),
    reverse=True
)[:50]

symbols = [s[0] for s in sorted_markets]
print(symbols)