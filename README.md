# Netgrave 
A tool for retrieving login credentials from Netwave IP cameras using a memory dump vulnerability (CVE-2018-17240). This project was inspired by [expcamera](https://github.com/vanpersiexp/expcamera) and offers performance and efficiency improvements. This tool works for all platforms as it does not use any Linux CLI tools through shell commands like expcamera does.

## CVE-2018-17240
On Linux systems, `/proc/kcore` is a virtual file that provides a direct mapping to the system's physical memory, allowing read access to the entire kernel's virtual memory space. Some Netwave IP cameras expose this file publicly via its web server, allowing unauthenticated users to retrieve the memory dump of the device, exposing sensitive information such as login credentials.

---

This tool will first attempt to find the device ID in the memory dump. Once this has been found, it likely means that the credentials are nearby and will begin searching for them.

## Host Options

### Specifying Hosts
This tool supports two different ways to specify hosts to check for the vulnerability.

#### `--host`
The first way is to specify a single host using the `--host` option. This option can be specified multiple times to check multiple hosts. The hosts should be in the `ip:port` format.

#### `--file`
The second way is to specify a file containing a list of hosts in the `ip:port` format using the `--file` option.

---

### Retrieving Hosts
This tool supports retrieving hosts from Censys, Shodan, and ZoomEye to check for the vulnerability.

#### `--censys`
You can retrieve hosts from the Censys API by using the `--censys` option. This option requires the `CENSYS_API_ID` and `CENSYS_API_SECRET` environment variables to be set.

#### `--shodan`
You can retrieve hosts from the Shodan API by using the `--shodan` option. This option requires the `SHODAN_API_KEY` environment variable to be set.

#### `--zoomeye`
You can retrieve hosts from the ZoomEye API by using the `--zoomeye` option. This option requires the `ZOOMEYE_API_KEY` environment variable to be set.

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
  --censys              Retrieve hosts from the Censys API using the API ID and secret specified with the CENSYS_API_ID and CENSYS_API_SECRET environment variables
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
