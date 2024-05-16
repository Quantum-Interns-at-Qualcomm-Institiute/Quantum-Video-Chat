import re
import argparse
import psutil


def find_interface(ip=None, ipv6=False):
    pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$') if not ipv6 else re.compile(r'(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4})')
    addrs = psutil.net_if_addrs()

    if not ip:  # If no IP is specified
        for interface, addresses in addrs.items():
            for addr in addresses:
                if ipv6 and addr.family == 23 or not ipv6 and addr.family == 2:
                    print(f"Interface {interface} has IP {addr.address}")
        return "All interfaces listed above"
    else:  # If an IP is specified
        match = pattern.match(ip)

        if not match:
            return "Invalid IP address."

        for interface, addresses in addrs.items():
            for addr in addresses:
                if ip == addr.address and (addr.family == 23 if ipv6 else addr.family == 2):  # Check IPv4 or IPv6
                    return f"Interface {interface} has IP {ip}"

        return "IP not found on any interface."


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Find the interface name for a given IP address')
    parser.add_argument('-i', '--ip', help="IPv4 or IPv6 address")
    parser.add_argument('-v6', '--isv6', action='store_true', help="Flag for IPv6")

    args = parser.parse_args()

    print(find_interface(args.ip, ipv6=args.isv6))
