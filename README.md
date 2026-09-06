# Netgrave

A tool for retrieving login credentials from Netwave IP cameras using a memory dump vulnerability (CVE-2018-17240). This project was inspired by [expcamera](https://github.com/vanpersiexp/expcamera) and offers performance and efficiency improvements. This tool works for all platforms as it does not use any Linux CLI tools through shell commands like expcamera does.

## CVE-2018-17240

On Linux systems, `/proc/kcore` is a virtual file that exposes system memory as an ELF core image. These cameras run uClinux on an MMU-less ARM7 core, so there is a single flat address space - the dump contains the camera application's memory alongside the kernel's, including the configuration blob it holds in a global.

It is reachable because the web server has an unauthenticated arbitrary file read: the request handler strips exactly one leading slash and calls `fopen()` with no traversal filtering, serving the result as root. `//proc/kcore` therefore resolves to `/proc/kcore`, which is why the request path carries a leading double slash.

---

### How the Credentials Are Recovered

The configuration blob has a fixed layout, so the credentials can be read straight out of it:

| Offset | Field                                                         |
| ------ | ------------------------------------------------------------- |
| `0x00` | `uint32` magic, always `0x440C9ABD`                           |
| `0x04` | `uint32` checksum                                             |
| `0x08` | `uint32` length                                               |
| `0x0C` | `char device_id[13]` 12 uppercase hex characters plus a NUL   |
| `0x36` | `struct { char name[13]; char pwd[13]; uint8 pri; } users[8]` |

The tool streams `/proc/kcore` and searches each chunk for the magic. Once found, it returns the highest privilege account from the users table.

## Host Options

### Specifying Hosts

This tool supports two different ways to specify hosts to check for the vulnerability. The hosts must be in the `ip:port` format.

| Argument | Description                                      |
| -------- | ------------------------------------------------ |
| `--host` | A host to check, can be specified multiple times |
| `--file` | A file containing a list of hosts check          |

---

### Retrieving Hosts

This tool supports retrieving hosts from Censys, Shodan, and ZoomEye to check for the vulnerability.

| IoT Search Engine | Argument    | Required Environment Variables |
| ----------------- | ----------- | ------------------------------ |
| Censys            | `--censys`  | `CENSYS_PERSONAL_ACCESS_TOKEN` |
| Shodan            | `--shodan`  | `SHODAN_API_KEY`               |
| ZoomEye           | `--zoomeye` | `ZOOMEYE_API_KEY`              |

Censys uses the Platform API. Create a personal access token at [platform.censys.io](https://platform.censys.io); set `CENSYS_ORGANIZATION_ID` as well to bill the search against an organization instead of your free wallet. Note that the Platform search endpoint requires a paid plan, as free accounts are limited to the lookup endpoints.

## Installation

    $ pip install -r requirements.txt

## Usage

```
Usage: main.py [-h] (--host HOST | -f FILE | --censys | --shodan | --zoomeye) [-n NUMBER] [-c CONCURRENT] [-t TIMEOUT] [-o OUTPUT]

A tool for retrieving login credentials from Netwave IP cameras using a memory dump vulnerability (CVE-2018-17240)

Options:
  -h, --help            show this help message and exit
  --host HOST           A host to check, can be specified multiple times
  -f, --file FILE       A file containing the hosts to check
  --censys              Retrieve hosts from the Censys Platform API using the personal access token specified with the CENSYS_PERSONAL_ACCESS_TOKEN environment variable
  --shodan              Retrieve hosts from the Shodan API using the API key specified with the SHODAN_API_KEY environment variable
  --zoomeye             Retrieve hosts from the ZoomEye API using the API key specified with the ZOOMEYE_API_KEY environment variable
  -n, --number NUMBER   The number of hosts to retrieve from the IoT search engine, by default 100
  -c, --concurrent CONCURRENT
                        The number of hosts to check concurrently, by default 25
  -t, --timeout TIMEOUT
                        The timeout in seconds for retrieving the credentials from the memory dump of each host, by default 300
  -o, --output OUTPUT   The file to write the credentials to, by default credentials.txt
```

## Disclaimer

This tool is for educational purposes only. The contributors of this project will not be held liable for any damages or legal issues that may arise from the use of this tool. Use at your own risk.
