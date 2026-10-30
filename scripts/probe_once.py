"""Query one server once and print the result.

Usage: uv run python scripts/probe_once.py [--edition java|bedrock|unknown] [--query] <host[:port]>
Exit code: 0 online, 1 unreachable, unresolvable or asleep, 2 bad usage.
"""

import argparse
import asyncio
import logging
import sys

from mc_watch.models import Edition, ProbeAsleep, ProbeOk, ProbeUnresolvable, ServerConfig
from mc_watch.players import players_view
from mc_watch.probe import probe


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Consulta un servidor una vez.")
    parser.add_argument("address", metavar="host[:port]")
    parser.add_argument("--edition", choices=[e.value for e in Edition], default="unknown")
    parser.add_argument("--query", action="store_true", help="pide también la lista por Query")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        return 2

    # MOTDs and versions carry characters such as "●" that a legacy console cannot print.
    sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    address: str = args.address
    server = ServerConfig(name=address, address=address, edition=Edition(args.edition))
    result = asyncio.run(probe(server, query=args.query))

    if isinstance(result, ProbeOk):
        print(
            f"{address}: online {result.online}/{result.max} "
            f"({result.latency_ms:.0f} ms, {result.edition.value})"
        )
        motd = "".join(segment.text for segment in result.info.motd).replace("\n", " | ")
        print(f"  versión: {result.info.version or '—'}")
        print(f"  motd:    {motd or '—'}")
        print(f"  icono:   {'sí' if result.info.icon else 'no'}")
        mode, names = players_view(result)
        print(f"  jugadores: {mode.value} {', '.join(names) if names else '—'}")
        print(f"  query:   {result.query.value}")
        return 0
    if isinstance(result, ProbeAsleep):
        print(f"{address}: dormido (el proveedor responde, el servidor está apagado)")
    elif isinstance(result, ProbeUnresolvable):
        print(f"{address}: el host no resuelve")
    else:
        print(f"{address}: sin respuesta")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
