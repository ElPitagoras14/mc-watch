"""Query one server once and print the result.

Usage: uv run python scripts/probe_once.py <host[:port]>
Exit code: 0 online, 1 unreachable or unresolvable, 2 bad usage.
"""

import asyncio
import logging
import sys

from mc_watch.models import ProbeOk, ProbeUnresolvable, ServerConfig
from mc_watch.probe import probe


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    address = argv[1]
    result = asyncio.run(probe(ServerConfig(name=address, address=address)))

    if isinstance(result, ProbeOk):
        print(f"{address}: online {result.online}/{result.max} ({result.latency_ms:.0f} ms)")
        return 0
    if isinstance(result, ProbeUnresolvable):
        print(f"{address}: el host no resuelve")
    else:
        print(f"{address}: sin respuesta")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
