# neubot/log.py

#
# Copyright (c) 2010-2011 Simone Basso <bassosimone@gmail.com>,
#  NEXA Center for Internet & Society at Politecnico di Torino
#
# This file is part of Neubot <http://www.neubot.org/>.
#
# Neubot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Neubot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Neubot.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import traceback

from neubot import system
from neubot import utils

class InteractiveLogger(object):

    """Log messages on the standard error.  This is the simplest
       logger one can think and is the one we use at startup."""

    def error(self, message):
        sys.stderr.write(message + "\n")

    def warning(self, message):
        sys.stderr.write(message + "\n")

    def info(self, message):
        sys.stderr.write(message + "\n")

    def debug(self, message):
        sys.stderr.write(message + "\n")

#
# We commit every NOCOMMIT log messages or when we see
# a WARNING or ERROR message (whichever of the two comes
# first).
#
NOCOMMIT = 32

class Logger(object):

    """Logging object.  Usually there should be just one instance
       of this class, accessible with the default logging object
       LOG.  We keep recent logs in the database in order to implement
       the /api/log API."""

    def __init__(self):
        self.logger = InteractiveLogger()
        self.interactive = True
        self.noisy = False
        self.message = None
        self.ticks = 0

        self._nocommit = NOCOMMIT
        self._use_database = False

        #
        # We cannot import the database here because of a
        # circular dependency.  Instead the database registers
        # with us when it is ready.
        #
        self.database = None
        self.table_log = None

    def attach(self, database, table_log):
        self.database = database
        self.table_log = table_log

    #
    # We don't want to log into the database when we run
    # the server side or when we run from command line.
    #
    def use_database(self):
        self._use_database = True

    def verbose(self):
        self.noisy = True

    def quiet(self):
        self.noisy = False

    def redirect(self):
        self.logger = system.BackgroundLogger()
        system.redirect_to_dev_null()
        self.interactive = False

    #
    # In some cases it makes sense to print progress during a
    # long operation, as follows::
    #
    #   Download in progress......... done
    #
    # This makes sense when: (i) the program is not running in
    # verbose mode; (ii) logs are directed to the stderr.
    # If the program is running in verbose mode, there might
    # be many messages between the 'in progress...' and 'done'.
    # And if the logs are not directed to stderr then it does
    # not make sense to print progress as well.
    # So, in these cases, the output will look like::
    #
    #   Download in progress...
    #    [here we might have many debug messages]
    #   Download complete.
    #
    def start(self, message):
        self.ticks = utils.ticks()
        if self.noisy or not self.interactive:
            self.info(message + " in progress...")
            self.message = message
        else:
            sys.stderr.write(message + "...")

    def progress(self, dot="."):
        if not self.noisy and self.interactive:
            sys.stderr.write(dot)

    def complete(self, done="done\n"):
        elapsed = utils.time_formatter(utils.ticks() - self.ticks)
        done = "".join([done.rstrip(), " [in ", elapsed, "]\n"])
        if self.noisy or not self.interactive:
            if not self.message:
                self.message = "???"
            self.info(self.message + "..." + done)
            self.message = None
        else:
            sys.stderr.write(done)

    # Log functions

    def exception(self, message="", func=None):
        if not func:
            func = self.error
        if message:
            func("EXCEPT: " + message + " (traceback follows)")
        for line in traceback.format_exc().split("\n"):
            func(line)

    def oops(self, message="", func=None):
        if not func:
            func = self.error
        if message:
            func("OOPS: " + message + " (traceback follows)")
        for line in traceback.format_stack()[:-1]:
            func(line)

    def error(self, message):
        self._log(self.logger.error, "ERROR", message)

    def warning(self, message):
        self._log(self.logger.warning, "WARNING", message)

    def info(self, message):
        self._log(self.logger.info, "INFO", message)

    def debug(self, message):
        if self.noisy:
            self._log(self.logger.debug, "DEBUG", message)

    def log_access(self, message):
        #
        # CAVEAT Currently Neubot do not update logs "in real
        # time" using AJAX.  If it did we would run in trouble
        # because each request for /api/log would generate a
        # new access log record.  A new access log record will
        # cause a new "logwritten" event.  And the result is
        # something like a Comet storm.
        #
        self._log(self.logger.info, "ACCESS", message)

    def _log(self, printlog, severity, message):
        message = message.rstrip()

        if self._use_database and self.database and severity != "ACCESS":
            record = {
                      "timestamp": utils.timestamp(),
                      "severity": severity,
                      "message": message,
                     }

            #
            # We don't need to commit INFO and DEBUG
            # records: it's OK to see those with some
            # delay.  While we want to see immediately
            # WARNING and ERROR records.
            # TODO We need to commit the database on
            # sys.exit() and signals etc.  (This is
            # more a database problem that a problem
            # of this file.)
            #
            if severity in ("INFO", "DEBUG"):
                commit = False

                # Do we need to commit now?
                self._nocommit = self._nocommit -1
                if self._nocommit <= 0:
                    self._nocommit = NOCOMMIT
                    commit = True

            else:
                # Must commit now
                self._nocommit = NOCOMMIT
                commit = True

            self.table_log.insert(self.database.connection(), record, commit)

        printlog(message)

    # Marshal

    def listify(self):
        return self.table_log.listify(self.database.connection())

LOG = Logger()
