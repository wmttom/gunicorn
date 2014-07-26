bind = "0.0.0.0:8888"
backlog = 2048
workers = 4
worker_class = "gunicorn.workers.gthrift.ThriftWorker"
worker_connections = 1000
timeout = 30
graceful_timeout = 30
daemon = False
accesslog = "access.log"
errorlog = "error.log"

### default thrift logger class
logger_class = "gunicorn.thriftlogging.ThriftLogger"

### thrift rotating logger class,by 100MB.
# logger_class = "gunicorn.thriftlogging.ThriftRotatingFileLogger"

### thrift timed rotating logger class,by day.
# logger_class = "gunicorn.thriftlogging.ThriftTimedRotatingFileLogger"

### wsgi rotating logger class,by 100MB.
# logger_class = "gunicorn.thriftlogging.RotatingFileLogger"

### wsgi timed rotating logger class,by day.
# logger_class = "gunicorn.thriftlogging.TimedRotatingFileLogger"