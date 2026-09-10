"""Exercise the production WSGI launcher against a synthetic local database."""
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='ramen-wsgi-') as directory:
        database = Path(directory) / 'synthetic.db'
        with closing(sqlite3.connect(database)) as conn, conn:
            conn.execute('CREATE TABLE Ratings (ID TEXT, Country TEXT, Brand TEXT, Type TEXT, Package TEXT, Rating TEXT)')
            conn.execute('INSERT INTO Ratings VALUES (?, ?, ?, ?, ?, ?)', ('1', 'SG', 'Fixture', 'Soup', 'Cup', '4'))
        before = sha256(database.read_bytes()).hexdigest()
        with closing(socket.socket()) as port_socket:
            port_socket.bind(('127.0.0.1', 0))
            port = port_socket.getsockname()[1]
        env = {**os.environ, 'RAMEN_DATABASE': str(database), 'RAMEN_ADMIN_TOKEN': '', 'PYTHONDONTWRITEBYTECODE': '1'}
        with (Path(directory) / 'server.log').open('w+') as log:
            process = subprocess.Popen([sys.executable, '-m', 'gunicorn', '--bind', f'127.0.0.1:{port}', '--workers', '1', '--threads', '4', '--timeout', '30', 'main:app'], env=env, stdout=log, stderr=log)
            try:
                base = f'http://127.0.0.1:{port}'
                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None:
                        raise RuntimeError('Gunicorn exited before serving the fixture.')
                    try:
                        with urlopen(base + '/', timeout=1) as response:
                            assert response.status == 200
                        break
                    except URLError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError('Gunicorn did not become ready.') from None
                        time.sleep(0.1)
                for route in ['/documentation', '/help', '/display']:
                    with urlopen(base + route, timeout=3) as response:
                        assert response.status == 200
                with urlopen(base + '/api/selectall', timeout=3) as response:
                    assert json.load(response)['items'][0]['Brand'] == 'Fixture'
                try:
                    urlopen(base + '/api/deleteall', timeout=3).close()
                    raise AssertionError('A destructive GET must be rejected.')
                except HTTPError as error:
                    assert error.code == 405
                    error.close()
                assert sha256(database.read_bytes()).hexdigest() == before
                print('Gunicorn served four pages and structured JSON; destructive GET rejected; fixture preserved.')
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
