# Netgrave 
A tool for retrieving login credentials from Netwave IP cameras using a memory dump vulnerability (CVE-2018-17240). This project was inspired by [expcamera](https://github.com/vanpersiexp/expcamera) and offers performance and efficiency improvements. This tool works for all platforms as it does not use any Linux CLI tools through shell commands like expcamera does.

## Host Retrieval Options
This tool supports three different ways of retrieving hosts to check for the vulnerability. The hosts should be in the `ip:port` format.

### `--host`
The first way is to specify a single host using the `--host` option. This option can be specified multiple times to check multiple hosts.

### `--file`
The second way is to specify a file containing a list of hosts using the `--file` option. 

### `--key`
The third way is to use the [ZoomEye](https://www.zoomeye.org/) API to search for hosts using the `--key` option to specify your API key or by setting the `ZOOMEYE_API_KEY` environment variable.

## Installation
    $ pip install -r requirements.txt

## Usage
```
Usage: main.py [-h] [--host HOST | -f FILE | -k KEY] [-o OUTPUT] [-p PAGES] [-t TIMEOUT] [-c CONCURRENT]

A tool for retrieving login credentials from Netwave IP cameras using a memory dump vulnerability (CVE-2018-17240)

Options:
  -h, --help            show this help message and exit
  --host HOST           A host to check, can be specified multiple times
  -f, --file FILE       A file containing the hosts to check
  -k, --key KEY         The ZoomEye API key to use, by default the ZOOMEYE_API_KEY environment variable
  -o, --output OUTPUT   The file to write the credentials to, by default credentials.txt
  -p, --pages PAGES     The number of pages to search on ZoomEye, by default 20
  -t, --timeout TIMEOUT
                        The timeout in seconds for retrieving the credentials from the memory dump, by default 300
  -c, --concurrent CONCURRENT
                        The number of hosts to check concurrently, by default 20
```

## Disclaimer
This tool is for educational purposes only. The contributors of this project will not be held liable for any damages or legal issues that may arise from the use of this tool. Use at your own risk.
