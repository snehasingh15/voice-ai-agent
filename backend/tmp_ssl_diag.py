import socket
import ssl
import certifi

hosts = [
    ('google.com', 443),
    ('ac-fsfe2z1-shard-00-00.vwottkq.mongodb.net', 27017),
]

protocols = [
    ssl.PROTOCOL_TLS_CLIENT,
    ssl.PROTOCOL_TLSv1_2,
]

for host, port in hosts:
    print('\n====', host, port)
    for proto in protocols:
        try:
            ctx = ssl.SSLContext(proto)
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_verify_locations(certifi.where())
            ctx.set_ciphers('DEFAULT')
            with socket.create_connection((host, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    print('proto', proto, 'OK', ssock.version(), ssock.cipher())
        except Exception as e:
            print('proto', proto, 'FAIL', type(e).__name__, e)

print('\n==== Atlas SRV test only')
for host in ['_mongodb._tcp.cluster0.vwottkq.mongodb.net']:
    try:
        import dns.resolver
        answers = dns.resolver.resolve(host, 'SRV')
        for r in answers:
            print('SRV', r)
    except Exception as e:
        print('SRV FAIL', type(e).__name__, e)
