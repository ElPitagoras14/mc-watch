"""Query one server once and print the result.

Usage: uv run python scripts/probe_once.py [--edition java|bedrock|unknown] <host[:port]>
Exit code: 0 online, 1 unreachable or unresolvable, 2 bad usage.
"""

import argparse
import asyncio
import logging
import sys

from mc_watch.models import Edition, ProbeOk, ProbeUnresolvable, ServerConfig
from mc_watch.probe import probe


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Consulta un servidor una vez.")
    parser.add_argument("address", metavar="host[:port]")
    parser.add_argument("--edition", choices=[e.value for e in Edition], default="unknown")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        return 2

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    address: str = args.address
    server = ServerConfig(name=address, address=address, edition=Edition(args.edition))
    result = asyncio.run(probe(server))

    if isinstance(result, ProbeOk):
        print(
            f"{address}: online {result.online}/{result.max} "
            f"({result.latency_ms:.0f} ms, {result.edition.value})"
        )
        return 0
    if isinstance(result, ProbeUnresolvable):
        print(f"{address}: el host no resuelve")
    else:
        print(f"{address}: sin respuesta")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
