# -*- coding: utf-8 -
import time
import traceback
import os

from gunicorn.glogging import Logger

class ThriftLogger(Logger):
    """ThriftLogger class,log access info."""

    def atoms(self, address, name, status, finish):
        end_ts = time.time()
        atoms = {
            'h': address[0],
            't': self.now(),
            'n': name,
            's': status,
            'T': finish * 1000,
            'p': "<%s>" % os.getpid()
        }
        return atoms

    def access(self, address, name, status, finish):

        if not self.cfg.accesslog and not self.cfg.logconfig:
            return

        atoms = self.atoms(address, name, status, finish)
        access_log_format = "%(h)s %(t)s %(n)s %(s)s %(T)s %(p)s"
        try:
            self.access_log.info(access_log_format % atoms)
        except:
            self.error(traceback.format_exc())
