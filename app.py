import os
import sys
import json
import time
import argparse
from typing import Dict, List, Tuple, Optional
from web3 import Web3

DEFAULT_RPC_A = os.environ.get("RPC_URL_A", os.environ.get("RPC_URL", "https://mainnet.infura.io/v3/YOUR_INFURA_KEY"))
DEFAULT_RPC_B = os.environ.get("RPC_URL_B", "https://eth.llamarpc.com")

HeaderDiff = Tuple[int, str, str, str]  # (block, field, a_value, b_value)


def connect(rpc: str, timeout: int) -> Web3:
    if not str(rpc).startswith(("http://", "https://")):
        raise ValueError(f"Invalid RPC URL: {rpc}")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))
    if not w3.is_connected():
        raise ConnectionError(f"RPC not reachable: {rpc}")
    return w3


def fetch_header(w3: Web3, number: int) -> Dict:
    blk = w3.eth.get_block(number)
    # Normalize hex strings to 0x… lowercase for consistent diffs
    norm = lambda v: v.hex() if hasattr(v, "hex") else v
    return {
        "number": blk.number,
        "hash": norm(blk.hash).lower(),
        "parentHash": norm(blk.parentHash).lower(),
        "stateRoot": norm(blk.stateRoot).lower(),
        "transactionsRoot": norm(blk.transactionsRoot).lower(),
        "receiptsRoot": norm(blk.receiptsRoot).lower(),
        "timestamp": blk.timestamp,
    }


def compare_headers(a: Dict, b: Dict) -> List[HeaderDiff]:
    diffs: List[HeaderDiff] = []
    for field in ("hash", "parentHash", "stateRoot", "transactionsRoot", "receiptsRoot"):
        if a[field] != b[field]:
            diffs.append((a["number"], field, str(a[field]), str(b[field])))
    return diffs


def analyze_chain_links(headers: List[Dict]) -> List[int]:
    """
    Return list of block numbers where parent linkage is broken (indicative of a reorg window on that RPC).
    """
    broken: List[int] = []
    for i in range(1, len(headers)):
        prev = headers[i - 1]
        cur = headers[i]
        if cur["parentHash"] != prev["hash"]:
            broken.append(cur["number"])
    return broken


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="zk-stateroot-soundness — cross-RPC header/stateRoot parity checker for Web3/zk systems (Aztec, Zama, L2s)."
    )
    p.add_argument("--rpc-a", default=DEFAULT_RPC_A, help="RPC A URL (default env RPC_URL_A or RPC_URL)")
    p.add_argument("--rpc-b", default=DEFAULT_RPC_B, help="RPC B URL (default env RPC_URL_B)")
    p.add_argument("--from-block", type=int, required=True, help="Start block number (inclusive)")
    p.add_argument("--to-block", type=int, required=True, help="End block number (inclusive)")
    p.add_argument("--step", type=int, default=1, help="Stride between sampled blocks (default: 1)")
    p.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds (default: 30)")
    p.add_argument("--json", action="store_true", help="Emit JSON summary")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.from_block > args.to_block:
        print("❌ --from-block must be <= --to-block")
        sys.exit(1)
    if args.step <= 0:
        print("❌ --step must be positive")
        sys.exit(1)

    # Connect
    try:
        w3a = connect(args.rpc_a, args.timeout)
        w3b = connect(args.rpc_b, args.timeout)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Banner
    print("🔧 zk-stateroot-soundness")
    try:
        print(f"🧭 Chain A ID: {w3a.eth.chain_id}")
    except Exception:
        pass
    try:
        print(f"🧭 Chain B ID: {w3b.eth.chain_id}")
    except Exception:
        pass
    print(f"🔗 RPC A: {args.rpc_a}")
    print(f"🔗 RPC B: {args.rpc_b}")
    print(f"🧱 Range: {args.from_block} → {args.to_block} (step={args.step})")

    t0 = time.time()
    headers_a: List[Dict] = []
    headers_b: List[Dict] = []
    all_diffs: List[HeaderDiff] = []

    # Scan
    samples = list(range(args.from_block, args.to_block + 1, args.step))
    total = len(samples)
    for idx, n in enumerate(samples, start=1):
        pct = (idx / total) * 100
        print(f"🔍 Block {n} ({idx}/{total}, {pct:.1f}%)")
        try:
            ha = fetch_header(w3a, n)
            hb = fetch_header(w3b, n)
        except Exception as e:
            print(f"⚠️  Block {n}: fetch error: {e}")
            continue
    # ✅ New: Show timestamp of the block in UTC
        from datetime import datetime
        ts = datetime.utcfromtimestamp(ha["timestamp"]).isoformat() + "Z"
        print(f"   🕒 Block timestamp (UTC): {ts}")


        headers_a.append(ha)
        headers_b.append(hb)
        diffs = compare_headers(ha, hb)
        all_diffs.extend(diffs)
        if diffs:
            # Print compact per-field mismatch
            for _, field, va, vb in diffs:
                print(f"   ❌ {field} mismatch:\n      A:{va}\n      B:{vb}")

    # Link integrity (per RPC)
    broken_a = analyze_chain_links(headers_a)
    broken_b = analyze_chain_links(headers_b)

    # Summaries
    mismatched_blocks = sorted(set(d[0] for d in all_diffs))
    ok = (len(mismatched_blocks) == 0) and (len(broken_a) == 0) and (len(broken_b) == 0)

    print("\n📊 Summary")
    print(f"   • Sampled blocks: {total}")
    print(f"   • Blocks with header/stateRoot mismatches: {len(mismatched_blocks)}")
    if mismatched_blocks:
        preview = ", ".join(str(b) for b in mismatched_blocks[:10])
        more = "…" if len(mismatched_blocks) > 10 else ""
        print(f"     ↳ {preview}{more}")
    print(f"   • Broken parent links on RPC A: {len(broken_a)}")
    if broken_a:
        print(f"     ↳ at blocks: {', '.join(map(str, broken_a[:10]))}{'…' if len(broken_a) > 10 else ''}")
    print(f"   • Broken parent links on RPC B: {len(broken_b)}")
    if broken_b:
        print(f"     ↳ at blocks: {', '.join(map(str, broken_b[:10]))}{'…' if len(broken_b) > 10 else ''}")

    elapsed = round(time.time() - t0, 2)
    print(f"\n{'✅ SOUND' if ok else '🚨 UNSOUND'} — completed in {elapsed}s")

    if args.json:
        out = {
            "rpc_a": args.rpc_a,
            "rpc_b": args.rpc_b,
            "range": [args.from_block, args.to_block, args.step],
            "mismatched_blocks": mismatched_blocks,
            "diffs": [
                {"block": b, "field": f, "a": va, "b": vb} for (b, f, va, vb) in all_diffs
            ],
            "broken_links": {
                "rpc_a": broken_a,
                "rpc_b": broken_b,
            },
            "ok": ok,
            "elapsed_seconds": elapsed,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))

    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
