# Stratosphere Linux IPS. A machine-learning Intrusion Detection System
# Copyright (C) 2021 Sebastian Garcia

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
# Contact: eldraco@gmail.com, sebastian.garcia@agents.fel.cvut.cz, stratosphere@aic.fel.cvut.cz

import os
import signal
import json
import time
from watchdog.events import RegexMatchingEventHandler
from .database import __database__
from slips_files.common.slips_utils import utils


class FileEventHandler(RegexMatchingEventHandler):
    REGEX = [r'.*\.log$', r'.*\.conf$']

    def __init__(self, config, redis_port, monitored_zeek_files):
        super().__init__(self.REGEX)
        self.config = config
        self.monitored_zeek_files = monitored_zeek_files
        # Start the DB
        __database__.start(self.config, redis_port)
        utils.drop_root_privs()

    def on_created(self, event):
        filename, ext = os.path.splitext(event.src_path)
        if 'log' in ext:
            __database__.add_zeek_file(filename + ext)

    def on_moved(self, event):
        """this will be triggered everytime zeek renames all log files"""
        # tell inputProcess to delete old files
        if event.dest_path != 'True':
            to_send = {'old_file': event.dest_path, 'new_file': event.src_path}
            to_send = json.dumps(to_send)
            __database__.publish('remove_old_files', to_send)
            # give inputProc.py time to close the handle and delete the file
            time.sleep(3)

    def on_modified(self, event):
        """this will be triggered everytime zeek modifies a log file"""
        # we only need to know modifications to reporter.log,
        # so if zeek recieves a termination signal,
        # slips would know about it
        filename, ext = os.path.splitext(event.src_path)
        if 'reporter' in filename:
            # check if it's a termination signal
            # get the exact file name (a ts is appended to it)
            for file in os.listdir(self.monitored_zeek_files):
                if 'reporter' not in file:
                    continue
                with open(os.path.join(self.monitored_zeek_files, file), 'r') as f:
                    while line := f.readline():
                        if 'termination' in line:
                            # to use shutdown gracefully we need to get slips.py PID and send it a sigint
                            __database__.publish('finished_modules', 'stop_slips')
                            break
        elif 'whitelist' in filename:
            __database__.publish('reload_whitelist', 'reload')
