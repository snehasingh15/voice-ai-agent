import socket
import ssl
import certifi

hosts = [
    'ac-fsfe2z1-shard-00-00.vwottkq.mongodb.net',
    'ac-fsfe2z1-shard-00-01.vwottkq.mongodb.net',
    'ac-fsfe2z1-shard-00-02.vwottkq.mongodb.net',
]

for host in hosts:
    print('\n----', host)
    for protocol in [ssl.PROTOCOL_TLS_CLIENT, ssl.PROTOCOL_TLSv1_2]:
        try:
            ctx = ssl.SSLContext(protocol)
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_verify_locations(certifi.where())
            print('protocol', protocol, 'cipher_suites', getattr(ctx, 'set_ciphers', None))
            with socket.create_connection((host, 27017), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    print('  OK', protocol, ssock.version(), ssock.cipher())
        except Exception as exc:
            print('  FAIL', protocol, type(exc).__name__, exc)
