# -*- coding: utf-8 -

import errno
import os
import sys
from datetime import datetime
from functools import partial
import time
import traceback

_socket = __import__("socket")

# workaround on osx, disable kqueue
if sys.platform == "darwin":
    os.environ['EVENT_NOKQUEUE'] = "1"

try:
    import gevent
except ImportError:
    raise RuntimeError("You need gevent installed to use this worker.")
from gevent.pool import Pool
from gevent.server import StreamServer
from gevent.socket import wait_write, socket
from gevent.timeout import Timeout, with_timeout

import gunicorn
from gunicorn.workers.async import AsyncWorker

from gunicorn.thrift.transport import TTransport
from gunicorn.thrift.protocol import TBinaryProtocol
from gunicorn.thrift.transport.TTransport import TFileObjectTransport
from gunicorn.thrift.Thrift import TApplicationException


VERSION = "gevent/%s gunicorn/%s" % (gevent.__version__, gunicorn.__version__)

class ThriftWorker(AsyncWorker):

    server_class = None

    def patch(self):
        from gevent import monkey
        monkey.noisy = False

        # if the new version is used make sure to patch subprocess
        if gevent.version_info[0] == 0:
            monkey.patch_all()
        else:
            monkey.patch_all(subprocess=True)

        # patch sockets
        sockets = []
        for s in self.sockets:
            sockets.append(socket(s.FAMILY, _socket.SOCK_STREAM,
                _sock=s))
        self.sockets = sockets


    def notify(self):
        super(ThriftWorker, self).notify()
        if self.ppid != os.getppid():
            self.log.info("Parent changed, shutting down: %s", self)
            sys.exit(0)

    def timeout_ctx(self):
        return gevent.Timeout(self.cfg.keepalive, False)

    def run(self):
        servers = []
        ssl_args = {}

        if self.cfg.is_ssl:
            ssl_args = dict(server_side=True, **self.cfg.ssl_options)

        for s in self.sockets:
            s.setblocking(1)
            pool = Pool(self.worker_connections)
            tfactory = TTransport.TTransportFactoryBase()
            pfactory = TBinaryProtocol.TBinaryProtocolFactory()
            server = ThriftServer(self.log, pool, self.cfg.backlog, s, self.wsgi, tfactory, tfactory, pfactory, pfactory, self.cfg.timeout)
            server.start()
            servers.append(server)

        try:
            while self.alive:
                self.notify()
                gevent.sleep(1.0)

        except KeyboardInterrupt:
            pass
        except:
            for server in servers:
                try:
                    server.stop()
                except:
                    pass
            raise

        try:
            # Stop accepting requests
            for server in servers:
                if hasattr(server, 'close'): # gevent 1.0
                    server.close()
                if hasattr(server, 'kill'):  # gevent < 1.0
                    server.kill()

            # Handle current requests until graceful_timeout
            ts = time.time()
            while time.time() - ts <= self.cfg.graceful_timeout:
                accepting = 0
                for server in servers:
                    if server.pool.free_count() != server.pool.size:
                        accepting += 1

                # if no server is accepting a connection, we can exit
                if not accepting:
                    return

                self.notify()
                gevent.sleep(1.0)

            # Force kill all active the handlers
            self.log.warning("Worker graceful timeout (pid:%s)" % self.pid)
            [server.stop(timeout=1) for server in servers]
        except:
            pass

    def handle_request(self, *args):
        try:
            super(ThriftWorker, self).handle_request(*args)
        except gevent.GreenletExit:
            pass
        except SystemExit:
            pass

    if gevent.version_info[0] == 0:

        def init_process(self):
            # monkey patch here
            self.patch()

            # reinit the hub
            import gevent.core
            gevent.core.reinit()

            #gevent 0.13 and older doesn't reinitialize dns for us after forking
            #here's the workaround
            gevent.core.dns_shutdown(fail_requests=1)
            gevent.core.dns_init()
            super(ThriftWorker, self).init_process()

    else:

        def init_process(self):
            # monkey patch here
            self.patch()

            # reinit the hub
            from gevent import hub
            hub.reinit()

            # then initialize the process
            super(ThriftWorker, self).init_process()


class ThriftServer(StreamServer):
    """Thrift server based on StreamServer."""

    def __init__(self, log, pool, backlog, listener, processor, inputTransportFactory=None,
                 outputTransportFactory=None, inputProtocolFactory=None,
                 outputProtocolFactory=None, timeout=30, **kwargs):
        StreamServer.__init__(self, listener, self._process_socket, None, pool, **kwargs)
        self.log = log
        self.timeout = timeout
        self.processor = self.wrapper_processor_class(processor)
        self.inputTransportFactory = (inputTransportFactory
            or TTransport.TFramedTransportFactory())
        self.outputTransportFactory = (outputTransportFactory
            or TTransport.TFramedTransportFactory())
        self.inputProtocolFactory = (inputProtocolFactory
            or TBinaryProtocol.TBinaryProtocolFactory())
        self.outputProtocolFactory = (outputProtocolFactory
            or TBinaryProtocol.TBinaryProtocolFactory())

    def _process_socket(self, client, address):
        """A greenlet for handling a single client."""
        client = TFileObjectTransport(client.makefile())
        itrans = self.inputTransportFactory.getTransport(client)
        otrans = self.outputTransportFactory.getTransport(client)
        iprot = self.inputProtocolFactory.getProtocol(itrans)
        oprot = self.outputProtocolFactory.getProtocol(otrans)
        try:
            while True:
                name, status, finish, err = self.processor.process(iprot, oprot, self.timeout)
                self.log.access(address, name, status, finish)
                if status != 200:
                    self.log.error(err)
                    raise Exception(err)
        except EOFError:
            pass
        except Exception, ex:
            pass
        itrans.close()
        otrans.close()

    def wrapper_processor_class(self, processor):
        processor.__class__.process = process
        return processor


def process(self, iprot, oprot, timeout):
    (name, type, seqid) = iprot.readMessageBegin()
    begin_ts = time.time()
    try:
        timeout_con = Timeout(timeout, Timeout)
        timeout_con.start()
        if name not in self._processMap:
            iprot.skip(TType.STRUCT)
            iprot.readMessageEnd()
            x = TApplicationException(
                TApplicationException.UNKNOWN_METHOD, 'Unknown function %s' % (name))
            oprot.writeMessageBegin(name, TMessageType.EXCEPTION, seqid)
            x.write(oprot)
            oprot.writeMessageEnd()
            oprot.trans.flush()
            result = (name, 404, time.time() - begin_ts, 'Unknown function %s' % (name))
        else:
            self._processMap[name](self, seqid, iprot, oprot)
            result = (name, 200, time.time() - begin_ts, None)
        timeout_con.cancel()
        return result
    except Timeout, ex:
        return (name, 504, time.time() - begin_ts, "A greenlet process timeout.")
    except Exception, ex:
        return (name, 500, time.time() - begin_ts, str(ex) + traceback.format_exc())