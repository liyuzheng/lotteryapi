# Copyright (c) 2006-2007, Linden Research, Inc.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import sys

import gevent
from gevent import socket

from gevent.testing import TestCase, main, tcp_listener
from gevent.testing import skipOnPyPy
from gevent.testing import params



PYPY = hasattr(sys, 'pypy_version_info')
PY3 = sys.version_info[0] >= 3


def _write_to_closed(f, s):
    try:
        r = f.write(s)
    except ValueError:
        assert PY3
    else:
        assert r is None, r


class TestGreenIo(TestCase):

    def test_close_with_makefile(self):

        def accept_close_early(listener):
            # verify that the makefile and the socket are truly independent
            # by closing the socket prior to using the made file
            try:
                conn, _ = listener.accept()
                fd = conn.makefile(mode='wb')
                conn.close()
                fd.write(b'hello\n')
                fd.close()
                _write_to_closed(fd, b'a')
                self.assertRaises(socket.error, conn.send, b'b')
            finally:
                listener.close()

        def accept_close_late(listener):
            # verify that the makefile and the socket are truly independent
            # by closing the made file and then sending a character
            try:
                conn, _ = listener.accept()
                fd = conn.makefile(mode='wb')
                fd.write(b'hello')
                fd.close()
                conn.send(b'\n')
                conn.close()
                _write_to_closed(fd, b'a')
                self.assertRaises(socket.error, conn.send, b'b')
            finally:
                listener.close()

        def did_it_work(server):
            client = socket.create_connection((params.DEFAULT_CONNECT, server.getsockname()[1]))
            fd = client.makefile(mode='rb')
            client.close()
            self.assertEqual(fd.readline(), b'hello\n')
            self.assertFalse(fd.read())
            fd.close()

        server = tcp_listener()
        server_greenlet = gevent.spawn(accept_close_early, server)
        did_it_work(server)
        server_greenlet.kill()

        server = tcp_listener()
        server_greenlet = gevent.spawn(accept_close_late, server)
        did_it_work(server)
        server_greenlet.kill()

    @skipOnPyPy("GC is different")
    def test_del_closes_socket(self):
        def accept_once(listener):
            # delete/overwrite the original conn
            # object, only keeping the file object around
            # closing the file object should close everything

            # XXX: This is not exactly true on Python 3.
            # This produces a ResourceWarning.
            oconn = None
            try:
                conn, _ = listener.accept()
                if PY3:
                    oconn = conn
                conn = conn.makefile(mode='wb')
                conn.write(b'hello\n')
                conn.close()
                _write_to_closed(conn, b'a')
            finally:
                listener.close()
                if oconn is not None:
                    oconn.close()

        server = tcp_listener()
        gevent.spawn(accept_once, server)
        client = socket.create_connection((params.DEFAULT_CONNECT, server.getsockname()[1]))
        with gevent.Timeout.start_new(0.5):
            fd = client.makefile()
            client.close()
            self.assertEqual(fd.read(), 'hello\n')
            self.assertEqual(fd.read(), '')


if __name__ == '__main__':
    main()
