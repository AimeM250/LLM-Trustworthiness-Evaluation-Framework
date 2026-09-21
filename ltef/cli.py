import argparse
import json
import sys
from pathlib import Path

from .schema import read_json, read_cases, ValidationError
from .engine import evaluate, compare
from .metrics import catalog
from .reporting import save_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="LTEF research evaluation engine")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("evaluate")
    p.add_argument("--cases", required=True)
    p.add_argument("--observations", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--out", required=True, help="New output directory; existing paths are never overwritten")
    p = sub.add_parser("compare")
    p.add_argument("--report", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--out", required=True, help="New JSON file")
    sub.add_parser("metrics")
    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate":
            report = evaluate(read_cases(args.cases), read_json(args.observations), read_json(args.profile))
            save_report(report, args.out)
            print(f"Wrote {args.out}/report.json and report.md ({report['evidence_class']})")
        elif args.command == "compare":
            result = compare(read_json(args.report), args.baseline, args.candidate)
            with Path(args.out).open("x", encoding="utf-8") as f:
                json.dump(result, f, indent=2, allow_nan=False)
                f.write("\n")
            print("Wrote " + args.out)
        else:
            print(json.dumps(catalog(), indent=2))
    except (ValidationError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"LTEF error: {exc}", file=sys.stderr)
        return 2
    return 0
