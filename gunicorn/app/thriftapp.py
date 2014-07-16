# -*- coding: utf-8 -
import os
import sys

from gunicorn.errors import ConfigError, AppImportError
from gunicorn.app.base import Application
from gunicorn import util


class ThriftApplication(Application):

    def init(self, parser, opts, args):
        if opts.paste and opts.paste is not None:
            app_name = 'main'
            path = opts.paste
            if '#' in path:
                path, app_name = path.split('#')
            path = os.path.abspath(os.path.normpath(
                os.path.join(util.getcwd(), path)))

            if not os.path.exists(path):
                raise ConfigError("%r not found" % path)

            # paste application, load the config
            self.cfgurl = 'config:%s#%s' % (path, app_name)
            self.relpath = os.path.dirname(path)

            from .pasterapp import paste_config
            return paste_config(self.cfg, self.cfgurl, self.relpath)

        if len(args) != 1:
            parser.error("No application module specified.")

        self.cfg.set("default_proc_name", args[0])
        self.app_uri = args[0]

    def chdir(self):
        # chdir to the configured path before loading,
        # default is the current dir
        os.chdir(self.cfg.chdir)

        # add the path to sys.path
        sys.path.insert(0, self.cfg.chdir)

    def load_thriftapp(self):
        self.chdir()

        # load the app
        return self._import_app(self.app_uri)

    def _import_app(self, module):
        """fork from gunicorn.until.import_app.
        thrift app is not callable,delete callable test.
        """
        parts = module.split(":", 1)
        if len(parts) == 1:
            module, obj = module, "application"
        else:
            module, obj = parts[0], parts[1]

        try:
            __import__(module)
        except ImportError:
            if module.endswith(".py") and os.path.exists(module):
                raise ImportError("Failed to find application, did "
                    "you mean '%s:%s'?" % (module.rsplit(".", 1)[0], obj))
            else:
                raise

        mod = sys.modules[module]

        try:
            app = eval(obj, mod.__dict__)
        except NameError:
            raise AppImportError("Failed to find application: %r" % module)

        if app is None:
            raise AppImportError("Failed to find application object: %r" % obj)
        return app


    def load_pasteapp(self):
        self.chdir()

        # load the paste app
        from .pasterapp import load_pasteapp
        return load_pasteapp(self.cfgurl, self.relpath, global_conf=None)

    def _load(self):
        if self.cfg.paste is not None:
            return self.load_pasteapp()
        else:
            return self.load_thriftapp()

    def load(self):
        app = self._load()
        return app


def run():
    """\
    The ``gunicorn`` command line runner for launching Gunicorn with
    generic thrift applications.
    """
    from gunicorn.app.thriftapp import ThriftApplication
    ThriftApplication("%(prog)s [OPTIONS] [APP_MODULE]").run()


if __name__ == '__main__':
    run()
