"""HL-MASTER1 G4 static snapshots (run on the laptop, internet needed): Hyperliquid meta traits and CoinGecko sectors. ONE snapshot, date recorded, flagged static/hindsight.

    python -u research/dataset/master_static.py > research/dataset/logs/master_static.log

HL META (POST https://api.hyperliquid.xyz/info {"type":"meta"}): per coin maxLeverage, marginTableId, szDecimals, and the margin table's FIRST tier max leverage and number of tiers.
These are TODAY's values and may have changed over time.
COINGECKO MAPPING (api.coingecko.com/api/v3): the Hyperliquid name is stripped of a leading 'k' when the rest is an upper-case symbol and the name starts with k + 2 or more capitals
(kPEPE, kBONK, kSHIB, kFLOKI, kLUNC, kDOGS, kNEIRO are 1000x units of the base coin); the symbol is matched case-insensitively against the top ~3,000 coins by CURRENT market cap; the
highest market cap wins. status = 'ok' if the winner's market cap is >= 3 x the next candidate's (or it is the only one), 'ambiguous' otherwise, 'unmapped' if no candidate.
Hindsight: the categorisation is today's, applied to the past; the market-cap ranking is today's.
SECTOR (one label, fixed priority, first substring match in the lower-cased category names): meme, artificial intelligence, real world assets, gaming, layer 2, layer 1, decentralized finance,
oracle, privacy, infrastructure; else 'other'; 'unmapped' for coins with no CoinGecko match. The full category list is stored beside it.
OUTPUT: research/dataset/static/hl_meta_snapshot.csv, coingecko_sector_snapshot.csv (with the snapshot date), both committed with the code.
"""
import json, sys, time, urllib.request, urllib.error
import pandas as pd

OUT = "research/dataset/static"
PRIORITY = ["meme", "artificial intelligence", "real world assets", "gaming", "layer 2", "layer 1", "decentralized finance", "oracle", "privacy", "infrastructure"]


def get(url, data=None, tries=8):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "pair-trading-research"})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20 + 20 * k)
                continue
            raise
        except Exception:
            time.sleep(5 + 5 * k)
    raise RuntimeError(url)


def base_name(n):
    if len(n) >= 4 and n[0] == "k" and n[1:].isupper():
        return n[1:]
    return n


def main():
    now = pd.Timestamp.now(tz="UTC")
    meta = get("https://api.hyperliquid.xyz/info", data=json.dumps({"type": "meta"}).encode())
    tabs = {t[0]: t[1] for t in meta["marginTables"]}
    rows = []
    for u in meta["universe"]:
        tiers = tabs.get(u.get("marginTableId"), {}).get("marginTiers", [])
        rows.append(dict(coin=u["name"], max_leverage=u["maxLeverage"], margin_table_id=u.get("marginTableId"), size_decimals=u["szDecimals"],
                         tier1_max_leverage=float(tiers[0]["maxLeverage"]) if tiers else None, n_tiers=len(tiers), is_delisted=bool(u.get("isDelisted", False)),
                         snapshot_utc=str(now)))
    M = pd.DataFrame(rows)
    M.to_csv(f"{OUT}/hl_meta_snapshot.csv", index=False)
    print(f"[META] {len(M)} coins in the current universe, snapshot {now}")
    mk = []
    for page in range(1, 13):
        d = get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}")
        mk += d
        print(f"  markets page {page}: {len(d)} coins  [{time.strftime('%H:%M:%S')}]", flush=True)
        time.sleep(4)
    C = pd.DataFrame(mk)[["id", "symbol", "name", "market_cap"]]
    C["symbol_u"] = C.symbol.str.upper()
    return M, C, now


if __name__ == "__main__":
    M, C, now = main()
    coins = sorted(set(pd.read_csv(sys.argv[1]).coin)) if len(sys.argv) > 1 else sorted(M.coin)
    out = []
    for i, c in enumerate(coins):
        b = base_name(c)
        cand = C[C.symbol_u == b.upper()].sort_values("market_cap", ascending=False)
        if cand.empty:
            out.append(dict(coin=c, base=b, cg_id=None, status="unmapped", n_candidates=0, categories="", sector="unmapped", market_cap=None))
            continue
        top = cand.iloc[0]
        ok = len(cand) == 1 or (pd.notna(top.market_cap) and (pd.isna(cand.iloc[1].market_cap) or top.market_cap >= 3 * cand.iloc[1].market_cap))
        cats = []
        d = get(f"https://api.coingecko.com/api/v3/coins/{top.id}?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false")
        cats = d.get("categories") or []
        low = [x.lower() for x in cats if x]
        sector = next((p for p in PRIORITY if any(p in x for x in low)), "other")
        out.append(dict(coin=c, base=b, cg_id=top.id, status="ok" if ok else "ambiguous", n_candidates=len(cand), categories="|".join(cats), sector=sector, market_cap=top.market_cap))
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(coins)} coins  [{time.strftime('%H:%M:%S')}]", flush=True)
        time.sleep(4)
    S = pd.DataFrame(out)
    S["snapshot_utc"] = str(now)
    S.to_csv(f"{OUT}/coingecko_sector_snapshot.csv", index=False)
    print(f"[SECTOR] {len(S)} coins: ok {int((S.status == 'ok').sum())}, ambiguous {int((S.status == 'ambiguous').sum())}, unmapped {int((S.status == 'unmapped').sum())}")
    print(S.sector.value_counts().to_string())
    print("k-prefixed names mapped: " + ", ".join(f"{r.coin}->{r.base}" for r in S.itertuples() if r.coin != r.base))
    print("ambiguous: " + ", ".join(f"{r.coin}({r.cg_id}, {r.n_candidates})" for r in S.itertuples() if r.status == "ambiguous"))
    print("unmapped: " + ", ".join(S.coin[S.status == "unmapped"]))
