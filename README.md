# zk-stateroot-soundness

## Overview
**zk-stateroot-soundness** compares **block header roots** across two RPC providers over a block range:
- `stateRoot` (global state commitment)
- `transactionsRoot`
- `receiptsRoot`
- `hash` and `parentHash`

It’s a fast way to detect **header divergence**, **reorg windows**, or **provider drift** — critical for zk systems (Aztec, Zama) that assume consistent L1/L2 inputs for proof soundness and bridge safety.

## Features
- Samples headers at a configurable stride (e.g., every block or every N blocks)  
- Verifies parent link continuity — highlights potential reorgs per RPC  
- Reports any per-field mismatches (hash/stateRoot/txRoot/receiptsRoot)  
- JSON output for CI dashboards and integrity monitoring  
- Works with any EVM-compatible JSON-RPC endpoint

## Installation
1) Python 3.9+  
2) Install dependency:
   pip install web3  
3) (Optional) Set defaults:
   export RPC_URL_A=https://mainnet.infura.io/v3/YOUR_KEY  
   export RPC_URL_B=https://eth.llamarpc.com

## Usage
Compare two RPCs over the last 100 blocks (stride 1):
   python app.py --from-block 19999000 --to-block 20000000 --rpc-a https://mainnet.infura.io/v3/YOUR_KEY --rpc-b https://eth.llamarpc.com

Sample every 50th block across a wide range:
   python app.py --from-block 18000000 --to-block 20000000 --step 50 --rpc-a https://mainnet.infura.io/v3/YOUR_KEY --rpc-b https://eth.llamarpc.com

Emit JSON for CI:
   python app.py --from-block 19999000 --to-block 20000000 --json

Tight scan for recent reorgs:
   python app.py --from-block 20000000 --to-block 20000100 --rpc-a $RPC_URL_A --rpc-b $RPC_URL_B

Increase timeout for slow providers:
   python app.py --from-block 19999000 --to-block 20000000 --timeout 60

## Expected Result
- Prints chain IDs (when available), RPCs, and a progress line per sampled block.  
- For each mismatching block, shows which header fields differ and the values on A vs B.  
- Summary includes:
  - Count of blocks with mismatches  
  - Any broken parent links per RPC (possible reorg windows)  
  - Final **SOUND/UNSOUND** status and elapsed time  
- Exit code: `0` if sound, `2` if unsound (mismatches or broken links detected).

## Example Output (truncated)
🔧 zk-stateroot-soundness  
🧭 Chain A ID: 1  
🧭 Chain B ID: 1  
🔗 RPC A: https://mainnet.infura.io/v3/…  
🔗 RPC B: https://eth.llamarpc.com  
🧱 Range: 19999000 → 20000000 (step=50)  
🔍 Block 19999000 (1/21, 4.8%)  
🔍 Block 19999050 (2/21, 9.5%)  
   ❌ stateRoot mismatch:
      A:0x9f…32a
      B:0x1b…e77
…  
📊 Summary  
   • Sampled blocks: 21  
   • Blocks with header/stateRoot mismatches: 2  
     ↳ 19999050, 19999550  
   • Broken parent links on RPC A: 0  
   • Broken parent links on RPC B: 1  
     ↳ at blocks: 19999600  

🚨 UNSOUND — completed in 1.84s

## Notes
- **Data Source Integrity:** Ensures both RPCs agree on the same canonical chain state.  
- **ZK Security Impact:** Diverging state roots across sources can invalidate zk proofs or bridge verifications.  
- **Reorg Detection:** Broken parent chains reveal reorg windows; such ranges should be avoided in zk commitments.  
- **Sampling Strategy:** Using `--step` reduces load while maintaining accuracy for large ranges.  
- **RPC Discrepancy Causes:** Mismatches may result from archive lag, pending reorgs, or network partitions.  
- **Automation:** Integrate into CI/CD to continuously monitor RPC consistency.  
- **Performance:** For thousands of blocks, use higher `--step` to balance speed and depth.  
- **JSON Reporting:** Ideal for dashboards that visualize drift and mismatches.  
- **Exit Codes:**  
  `0` → All headers matched and linked properly.  
  `2` → At least one mismatch or broken link detected.  
- **Security Best Practice:**  
  Run this check before zk proof generation or L2 settlement operations to ensure all inputs are canonical.  
- **Cross-RPC Testing:**  
  Useful for comparing Infura, Alchemy, LlamaRPC, or self-hosted nodes for drift detection.  
- **Validation Tip:**  
  When an UNSOUND result appears, re-run after 1–2 confirmations to rule out temporary reorgs. 
