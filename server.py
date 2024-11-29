import socket
import struct
import time
from dnslib import DNSRecord, RR, A
from dnslib.server import DNSServer
from dnslib.dns import QTYPE, RCODE
from threading import Thread

# In-memory cache
cache = {}

# Caching Time-To-Live (TTL) in seconds
CACHE_TTL = 300  # 5 minutes

# DNS server settings
UPSTREAM_DNS = "8.8.8.8"  # Upstream DNS server for recursive resolution
DNS_PORT = 53  # Port for listening to DNS queries

# Log file
log_file = "dns_log.txt"

def log_request(domain, from_cache):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    log_msg = f"[{timestamp}] Domain: {domain}, {'Cache' if from_cache else 'Upstream'}\n"
    with open(log_file, "a") as log:
        log.write(log_msg)
    print(log_msg.strip())

def resolve_upstream(domain):
    """Forward DNS request to upstream DNS server (recursive resolution)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    
    # Create a DNS query packet
    query = DNSRecord.question(domain)
    sock.sendto(query.pack(), (UPSTREAM_DNS, DNS_PORT))
    
    try:
        # Receive response from upstream server
        data, _ = sock.recvfrom(512)
        response = DNSRecord.parse(data)
        return response
    except socket.timeout:
        print(f"Timeout querying upstream DNS for {domain}")
        return None

def check_cache(domain):
    """Check the cache for a valid entry."""
    if domain in cache:
        entry = cache[domain]
        if time.time() < entry['expire_time']:
            return entry['response']
        else:
            # Cache expired
            del cache[domain]
    return None

def add_to_cache(domain, response):
    """Add a DNS response to cache with an expiration time."""
    expire_time = time.time() + CACHE_TTL
    cache[domain] = {'response': response, 'expire_time': expire_time}

class MyResolver:
    def resolve(self, request, handler):
        qname = request.q.qname
        domain = str(qname)
        print(f"Received query for {domain}")
        
        # Check cache first
        cached_response = check_cache(domain)
        if cached_response:
            log_request(domain, from_cache=True)
            return cached_response
        
        # If not in cache, resolve upstream
        response = resolve_upstream(domain)
        if response:
            log_request(domain, from_cache=False)
            # Cache the response
            add_to_cache(domain, response)
            return response
        else:
            # Return a failure response if upstream query failed
            reply = request.reply()
            reply.header.rcode = RCODE.SERVFAIL
            return reply

class UDPServer(Thread):
    """Run the DNS server using UDP and dnslib."""
    def __init__(self, resolver, address="0.0.0.0", port=53):
        Thread.__init__(self)
        self.resolver = resolver
        self.address = address
        self.port = port
    
    def run(self):
        # Start a DNS server with UDP on port 53
        server = DNSServer(self.resolver, port=self.port, address=self.address, logger=None)
        server.start_thread()

def main():
    resolver = MyResolver()
    udp_server = UDPServer(resolver)
    udp_server.start()
    
    print(f"DNS server is running on UDP port {DNS_PORT}...")
    try:
        while True:
            time.sleep(1)  # Keep the main thread alive
    except KeyboardInterrupt:
        print("Stopping DNS server...")

if __name__ == '__main__':
    main()

