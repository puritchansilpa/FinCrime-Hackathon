#!/usr/bin/env python3
"""Run the system several times and check the outputs are byte-identical.

Usage: python3 tools/check_runs.py dev [--runs 5] [--llm] [--keep output/dev.jsonl]

The scorer runs the system 5 times on the unseen set and pays 10% for giving the same
decision and reason code every time; this checks the whole output, which is stricter.
Reports each run's time and the SHA-256 of its output. With --keep, the first run's
output is copied to that path. Exit code 1 if any run differs or fails.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data_folder")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--keep", help="copy the first run's output here")
    args = ap.parse_args(argv)

    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "system") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    hashes, outputs, ok = [], [], True
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(1, args.runs + 1):
            out = os.path.join(tmp, f"run{i}.jsonl")
            cmd = [sys.executable, "-m", "screening", args.data_folder, out] + (["--llm"] if args.llm else [])
            started = time.time()
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8")
            took = time.time() - started
            if proc.returncode != 0:
                print(f"run {i}: FAILED (exit {proc.returncode})\n{proc.stderr[-2000:]}")
                ok = False
                continue
            with open(out, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            hashes.append(digest)
            outputs.append(out)
            lines = sum(1 for _ in open(out, encoding="utf-8"))
            print(f"run {i}: {took:6.1f}s  {lines} lines  sha256 {digest[:16]}")
        same = ok and len(set(hashes)) == 1
        print("ALL RUNS IDENTICAL" if same else "RUNS DIFFER")
        if args.keep and outputs:
            os.makedirs(os.path.dirname(os.path.abspath(args.keep)), exist_ok=True)
            shutil.copyfile(outputs[0], args.keep)
            print(f"kept run 1 as {args.keep}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
