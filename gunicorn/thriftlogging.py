# -*- coding: utf-8 -
import time
import traceback
import os
import logging

from gunicorn.glogging import Logger

class RotatingFileLogger(Logger):
    """Logger class,add Rotating RotatingFileHandler, default 100MB."""
    def _set_handler(self, log, output, fmt):
    # remove previous gunicorn log handler
    h = self._get_gunicorn_handler(log)
    if h:
        log.handlers.remove(h)
    if output is not None:
        if output == "-":
            h = logging.StreamHandler()
        else:
            util.check_is_writeable(output)
            if log is self.access_log:
                h = logging.RotatingFileHandler(output, maxBytes=100 * 1024 * 1024, backupCount=0)
            else:
                h = logging.FileHandler(output)
        h.setFormatter(fmt)
        h._gunicorn = True
        log.addHandler(h)


class TimedRotatingFileLogger(Logger):
    """Logger class,add Rotating TimedRotatingFileHandler, default 1 day."""
    def _set_handler(self, log, output, fmt):
    # remove previous gunicorn log handler
    h = self._get_gunicorn_handler(log)
    if h:
        log.handlers.remove(h)
    if output is not None:
        if output == "-":
            h = logging.StreamHandler()
        else:
            util.check_is_writeable(output)
            if log is self.access_log:
                h = logging.TimedRotatingFileHandler(output, when="midnight", interval=1, backupCount=0)
            else:
                h = logging.FileHandler(output)
        h.setFormatter(fmt)
        h._gunicorn = True
        log.addHandler(h)


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

class ThriftRotatingFileLogger(ThriftLogger, RotatingFileLogger):
    """ThriftLogger class,log access info. add Rotating RotatingFileHandler, default 100MB."""
    pass

class ThriftTimedRotatingFileLogger(ThriftLogger, TimedRotatingFileLogger):
    """ThriftLogger class,log access info. add Rotating TimedRotatingFileHandler, default 1 day."""
    pass