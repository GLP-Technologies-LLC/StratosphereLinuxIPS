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
from slips_files.common.slips_utils import utils
import multiprocessing
import sys
import os
from datetime import datetime
from watchdog.observers import Observer
from .filemonitor import FileEventHandler
from .database import __database__
import configparser
import time
import json
import traceback
import threading
import subprocess
import shutil


# Input Process
class InputProcess(multiprocessing.Process):
    """A class process to run the process of the flows"""

    def __init__(
            self,
            outputqueue,
            profilerqueue,
            input_type,
            input_information,
            config,
            packet_filter,
            zeek_or_bro,
            line_type,
            redis_port,
    ):
        multiprocessing.Process.__init__(self)
        self.name = 'InputProcess'
        self.outputqueue = outputqueue
        self.profilerqueue = profilerqueue
        self.config = config
        # Start the DB
        __database__.start(self.config, redis_port)
        self.redis_port = redis_port
        self.input_type = input_type
        # in case of reading from stdin, the user mst tell slips what type of lines is the input
        self.line_type = line_type
        # entire path
        self.given_path = input_information
        # filename only
        self.given_file = self.given_path.split('/')[-1]
        self.zeek_folder = f'./zeek_files_{self.given_file}/'
        self.zeek_or_bro = zeek_or_bro
        self.read_lines_delay = 0
        # Read the configuration
        self.read_configuration()
        # If we were given something from command line, has preference
        # over the configuration file
        if packet_filter:
            self.packet_filter = "'" + packet_filter + "'"
        self.event_handler = None
        self.event_observer = None
        # number of lines read
        self.lines = 0
        # these are the files that slips doesn't read
        self.ignored_files = {
            'capture_loss',
            'loaded_scripts',
            'packet_filter',
            'stats',
            'ocsp',
            'weird',
            'reporter',
            'x509',
        }
        # create the remover thread
        self.remover_thread = threading.Thread(
            target=self.remove_old_zeek_files, daemon=True
        )
        self.open_file_handlers = {}
        self.c1 = __database__.subscribe('remove_old_files')
        self.timeout = None

    def read_configuration(self):
        """Read the configuration file for what we need"""

        try:
            self.packet_filter = self.config.get('parameters', 'pcapfilter')
        except (
                configparser.NoOptionError,
                configparser.NoSectionError,
                NameError,
        ):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.packet_filter = 'ip or not ip'

        try:
            self.tcp_inactivity_timeout = self.config.get(
                'parameters', 'tcp_inactivity_timeout'
            )
            # make sure the value is a valid int
            self.tcp_inactivity_timeout = int(self.tcp_inactivity_timeout)

        except (
                configparser.NoOptionError,
                configparser.NoSectionError,
                NameError,
                ValueError,
        ):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.tcp_inactivity_timeout = '5'

        try:
            self.rotation = self.config.get('parameters', 'rotation')
            self.rotation = 'yes' in self.rotation
        except (
                configparser.NoOptionError,
                configparser.NoSectionError,
                NameError,
        ):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.rotation = True

    def print(self, text, verbose=1, debug=0):
        """
        Function to use to print text using the outputqueue of slips.
        Slips then decides how, when and where to print this text by taking all the processes into account
        :param verbose:
            0 - don't print
            1 - basic operation/proof of work
            2 - log I/O operations and filenames
            3 - log database/profile/timewindow changes
        :param debug:
            0 - don't print
            1 - print exceptions
            2 - unsupported and unhandled types (cases that may cause errors)
            3 - red warnings that needs examination - developer warnings
        :param text: text to print. Can include format like 'Test {}'.format('here')
        """

        levels = f'{verbose}{debug}'
        self.outputqueue.put(f'{levels}|{self.name}|{text}')

    def stop_queues(self):
        """Stops the profiler and output queues"""

        self.profilerqueue.put('stop')
        self.outputqueue.put(
            '02|input|[In] No more input. Stopping input process. Sent {} lines ({}).\n'.format(
                self.lines, datetime.now().strftime('%Y-%m-%d--%H:%M:%S')
            )
        )
        self.outputqueue.close()
        self.profilerqueue.close()

    def read_nfdump_output(self) -> int:
        try:
            """
            A binary file generated by nfcapd can be read by nfdump.
            The task for this function is to send nfdump output line by line to profilerProcess.py for processing
            """

            line = {'type': 'nfdump'}
            if not self.nfdump_output:
                # The nfdump command returned nothing
                self.print('Error reading nfdump output ', 1, 3)
            else:
                lines = len(self.nfdump_output.splitlines())
                for nfdump_line in self.nfdump_output.splitlines():
                    # this line is taken from stdout we need to remove whitespaces
                    nfdump_line.replace(' ', '')
                    ts = nfdump_line.split(',')[0]
                    if not ts[0].isdigit():
                        # The first letter is not digit -> not valid line.
                        # TODO: What is this valid line check?? explain
                        continue
                    line['data'] = nfdump_line
                    self.profilerqueue.put(line)

            return lines
        except KeyboardInterrupt:
            return True

    def read_zeek_files(self) -> int:
        try:
            # Get the zeek files in the folder now
            zeek_files = __database__.get_all_zeek_file()
            self.open_file_handlers = {}
            file_time = {}
            cache_lines = {}
            # Try to keep track of when was the last update so we stop this reading
            last_updated_file_time = datetime.now()
            lines = 0
            while True:
                # Go to all the files generated by Zeek and read them
                for filename in zeek_files:

                    # filename is the log file name with .log extension in case of interface or pcap
                    # and without the ext in case of zeek files
                    if not filename.endswith('.log'):
                        filename += '.log'
                    # Ignore the files that do not contain data. These are the zeek log files that we don't use
                    filename_without_ext = filename.split('/')[-1].split('.')[
                        0
                    ]
                    if filename_without_ext in self.ignored_files:
                        continue

                    # Update which files we know about
                    try:
                        # We already opened this file
                        file_handler = self.open_file_handlers[filename]
                    except KeyError:
                        # First time opening this file.
                        try:
                            file_handler = open(filename, 'r')
                            lock = threading.Lock()
                            lock.acquire()
                            self.open_file_handlers[filename] = file_handler
                            lock.release()
                            # now that we replaced the old handle with the newly created file handle
                            # delete the old .log file, they have a timestamp in their name.
                        except FileNotFoundError:
                            # for example dns.log
                            # zeek changes the dns.log file name every 1h, it adds a timestamp to it
                            # it doesn't create the new dns.log until a new dns request occurs
                            # if slips tries to read from the old dns.log now it won't find it
                            # because it's been renamed and the new one isn't created yet
                            # simply continue until the new log file is created and added to the zeek_files list
                            continue

                    # Only read the next line if the previous line was sent
                    try:
                        _ = cache_lines[filename]
                        # We have still something to send, do not read the next line from this file
                    except KeyError:
                        # We don't have any waiting line for this file, so proceed
                        try:
                            zeek_line = file_handler.readline()
                        except ValueError:
                            # remover thread just finished closing all old handles.
                            # comes here if I/O operation failed due to a closed file.
                            # to get the new dict of open handles.
                            continue

                        # self.print(f'Reading from file {filename}, the line {zeek_line}', 0, 6)
                        # Did the file end?
                        if not zeek_line:
                            # We reached the end of one of the files that we were reading. Wait for more data to come
                            continue

                        # Since we actually read something form any file, update the last time of read
                        last_updated_file_time = datetime.now()
                        try:
                            nline = json.loads(zeek_line)
                            line = {'type': filename, 'data': nline}

                            # All bro files have a field 'ts' with the timestamp.
                            # So we are safe here not checking the type of line
                            # In some Zeek files there may not be a ts field
                            # Like in some weird smb files
                            timestamp = nline.get('ts', 0)

                        except json.decoder.JSONDecodeError:
                            # It is not JSON format. It is tab format line.
                            nline = zeek_line
                            # Ignore comments at the beginning of the file.
                            if not nline or nline[0] == '#':
                                continue

                            line = {'type': filename, 'data': nline}
                            timestamp = nline.split('\t')[0]

                        try:

                            # is a dict with {'filename': ts, ...}
                            file_time[filename] = float(timestamp)
                            # self.print(f'File {filename}. TS: {timestamp}')
                            # Store the line in the cache
                            # self.print(f'Adding cache and time of {filename}')
                            cache_lines[filename] = line
                        except ValueError:
                            # this ts doesnt repr a float value, ignore it
                            pass

                ###################################################################################
                # Out of the for that check each Zeek file one by one
                # self.print('Cached lines: {}'.format(str(cache_lines)))

                # If we don't have any cached lines to send, it may mean that new lines are not arriving. Check
                if not cache_lines:
                    # Verify that we didn't have any new lines in the
                    # last 10 seconds. Seems enough for any network to have ANY traffic
                    now = datetime.now()
                    diff = now - last_updated_file_time
                    diff = diff.seconds
                    if diff >= self.bro_timeout:
                        # It has been 10 seconds without any file
                        # being updated. So stop Zeek
                        break

                # Now read lines in order. The line with the smallest timestamp first
                files_sorted_by_ts = sorted(file_time, key=file_time.get)
                # self.print('Sorted times: {}'.format(str(files_sorted_by_ts)))
                try:
                    # get the file that has the earliest flow
                    file_with_earliest_flow = files_sorted_by_ts[0]
                except IndexError:
                    # No more sorted keys. Just loop waiting for more lines
                    # It may happen that we check all the files in the folder, and there is still no file for us.
                    # To cover this case, just refresh the list of files
                    zeek_files = __database__.get_all_zeek_file()
                    time.sleep(1)
                    continue

                # to fix the problem of evidence being generated BEFORE their corresponding flows are added to our db
                # make sure we read flows in the following order:
                # dns.log  (make it a priority to avoid FP connection without dns resolution alerts)
                # conn.log
                # any other flow
                # for key in cache_lines:
                #     if 'dns' in key:
                #         file_with_earliest_flow = key
                #         break
                # comes here if we're done with all conn.log flows and it's time to process other files
                line_to_send = cache_lines[file_with_earliest_flow]

                # self.print('Line to send from file {}. {}'.format(file_with_earliest_flow, line_to_send))
                self.print('	> Sent Line: {}'.format(line_to_send), 0, 3)
                self.profilerqueue.put(line_to_send)
                # Count the read lines
                lines += 1
                # Delete this line from the cache and the time list
                # self.print('Deleting cache and time of {}'.format(earliest_flow))
                del cache_lines[file_with_earliest_flow]
                del file_time[file_with_earliest_flow]
                # Get the new list of files. Since new files may have been created by Zeek while we were processing them.
                zeek_files = __database__.get_all_zeek_file()

            ################
            # Out of the while

            # We reach here after the break produced if no zeek files are being updated.
            # No more files to read. Close the files
            for file, handle in self.open_file_handlers.items():
                self.print(f'Closing file {file}', 2, 0)
                handle.close()
            return lines
        except KeyboardInterrupt:
            return False

    def read_zeek_folder(self):
        try:
            # This is the case that a folder full of zeek files is passed with -f. Read them all
            for file in os.listdir(self.given_path):
                # Remove .log extension and add file name to database.
                extension = file[-4:]
                if extension == '.log':
                    # Add log file to database
                    file_name_without_extension = file[:-4]
                    __database__.add_zeek_file(
                        f'{self.given_path}/{file_name_without_extension}'
                    )

            # We want to stop bro if no new line is coming.
            self.bro_timeout = 1
            lines = self.read_zeek_files()
            self.print(
                f'\nWe read everything from the folder. No more input. Stopping input process. Sent {lines} lines',
                2,
                0,
            )
            self.stop_queues()
            return True
        except KeyboardInterrupt:
            return False

    def read_from_stdin(self):
        self.print('Receiving flows from stdin.')
        # By default read the stdin
        sys.stdin.close()
        sys.stdin = os.fdopen(0, 'r')
        file_stream = sys.stdin
        # tell profilerprocess the type of line the user gave slips
        line_info = {
            'type': 'stdin',
            'line_type': self.line_type
        }
        for line in file_stream:
            if line == '\n':
                continue

            # slips supports zeek json only, tabs arent supported
            if self.line_type == 'zeek':
                line = json.loads(line)

            line_info['data'] = line
            self.print(f'	> Sent Line: {line_info}', 0, 3)
            self.profilerqueue.put(line_info)
            self.lines += 1

        self.stop_queues()
        return True

    def handle_binetflow(self):
        try:
            self.lines = 0
            self.read_lines_delay = 0.02
            with open(self.given_path) as file_stream:
                line = {'type': 'argus'}
                # fake = {'type': 'argus', 'data': 'StartTime,Dur,Proto,SrcAddr,Sport,
                # Dir,DstAddr,Dport,State,sTos,dTos,TotPkts,TotBytes,SrcBytes,SrcPkts,Label\n'}
                # self.profilerqueue.put(fake)

                # read first line to determine the type of line, tab or comma separated
                t_line = file_stream.readline()
                if '\t' in t_line:
                    # this is the header line
                    line['type'] = 'argus-tabs'
                line['data'] = t_line
                self.profilerqueue.put(line)
                self.lines += 1

                # go through the rest of the file
                for t_line in file_stream:
                    time.sleep(self.read_lines_delay)
                    line['data'] = t_line
                    # argus files are either tab separated orr comma separated
                    if len(t_line.strip()) != 0:
                        self.profilerqueue.put(line)
                    self.lines += 1

            self.stop_queues()
            return True
        except KeyboardInterrupt:
            return True

    def handle_suricata(self):
        try:
            with open(self.given_path) as file_stream:
                line = {'type': 'suricata'}
                self.read_lines_delay = 0.02
                for t_line in file_stream:
                    time.sleep(self.read_lines_delay)
                    line['data'] = t_line
                    self.print(f'	> Sent Line: {line}', 0, 3)
                    if len(t_line.strip()) != 0:
                        self.profilerqueue.put(line)
                    self.lines += 1
            self.stop_queues()
            return True
        except KeyboardInterrupt:
            return True

    def handle_zeek_log_file(self):
        try:
            try:
                file_name_without_extension = self.given_path[
                                              : self.given_path.index('.log')
                                              ]
            except IndexError:
                # filename doesn't have an extension, probably not a conn.log
                return False
            # Add log file to database
            __database__.add_zeek_file(file_name_without_extension)
            self.bro_timeout = 1
            self.lines = self.read_zeek_files()
            self.stop_queues()
            return True
        except KeyboardInterrupt:
            return True

    def handle_nfdump(self):
        try:
            command = f'nfdump -b -N -o csv -q -r {self.given_path}'
            # Execute command
            result = subprocess.run(command.split(), stdout=subprocess.PIPE)
            # Get command output
            self.nfdump_output = result.stdout.decode('utf-8')
            self.lines = self.read_nfdump_output()
            self.print(
                f'We read everything. No more input. Stopping input process. Sent {self.lines} lines'
            )
            return True
        except KeyboardInterrupt:
            return True

    def handle_pcap_and_interface(self) -> int:
        """Returns the number of zeek lines read"""

        try:
            # Create zeek_folder if does not exist.
            if not os.path.exists(self.zeek_folder):
                os.makedirs(self.zeek_folder)
            self.print(f'Storing zeek log files in {self.zeek_folder}')
            # Now start the observer of new files. We need the observer because Zeek does not create all the files
            # at once, but when the traffic appears. That means that we need
            # some process to tell us which files to read in real time when they appear
            # Get the file eventhandler
            # We have to set event_handler and event_observer before running zeek.
            self.event_handler = FileEventHandler(self.config, self.redis_port, self.zeek_folder)
            # Create an observer
            self.event_observer = Observer()
            # Schedule the observer with the callback on the file handler
            self.event_observer.schedule(
                self.event_handler, self.zeek_folder, recursive=True
            )
            # Start the observer
            self.event_observer.start()

            # rotation is disabled unless it's an interface
            rotation_interval = (
                "-e 'redef Log::default_rotation_interval = 0sec;'"
            )
            if self.input_type == 'interface':
                if self.rotation:
                    rotation_interval = (
                        "-e 'redef Log::default_rotation_interval =  1day;'"
                    )
                # Change the bro command
                bro_parameter = f'-i {self.given_path}'
                # We don't want to stop bro if we read from an interface
                self.bro_timeout = 9999999999999999
            elif self.input_type == 'pcap':
                # Find if the pcap file name was absolute or relative
                if self.given_path[0] == '/':
                    # If absolute, do nothing
                    bro_parameter = '-r "' + self.given_path + '"'
                else:
                    # If relative, add ../ since we will move into a special folder
                    bro_parameter = '-r "../' + self.given_path + '"'
                # This is for stopping the inputprocess
                # if bro does not receive any new line while reading a pcap
                self.bro_timeout = 30

            zeek_files = os.listdir(self.zeek_folder)
            if len(zeek_files) > 0:
                # First clear the zeek folder of old .log files
                for f in zeek_files:
                    os.remove(os.path.join(self.zeek_folder, f))

            # Run zeek on the pcap or interface. The redef is to have json files
            zeek_scripts_dir = f'{os.getcwd()}/zeek-scripts'
            # 'local' is removed from the command because it loads policy/protocols/ssl/expiring-certs and
            # and policy/protocols/ssl/validate-certs and they have conflicts with our own zeek-scripts/expiring-certs and validate-certs
            # we have our own copy pf local.zeek in __load__.zeek
            command = (
                f'cd {self.zeek_folder}; {self.zeek_or_bro} -C {bro_parameter} '
                f'tcp_inactivity_timeout={self.tcp_inactivity_timeout}mins '
                f'tcp_attempt_delay=1min -f {self.packet_filter} '
                f'{zeek_scripts_dir} {rotation_interval} 2>&1 > /dev/null &'
            )
            self.print(f'Zeek command: {command}', 3, 0)
            # Run zeek.
            os.system(command)
            # Give Zeek some time to generate at least 1 file.
            time.sleep(3)

            lines = self.read_zeek_files()
            self.print(
                f'We read everything. No more input. Stopping input process. Sent {lines} lines'
            )

            self.stop_observer()
            return True
        except KeyboardInterrupt:
            return False

    def stop_observer(self):
        # Stop the observer
        try:
            self.event_observer.stop()
            self.event_observer.join()
        except AttributeError:
            # In the case of nfdump, there is no observer
            pass

    def remove_old_zeek_files(self):
        """
        This thread waits for filemonitor.py to tell it that zeek changed the files,
        it deletes old zeek-date.log files and clears slips' open handles and sleeps again
        """
        while True:
            msg = self.c1.get_message(timeout=self.timeout)
            if msg and msg['data'] == 'stop_process':
                return True
            if utils.is_msg_intended_for(msg, 'remove_old_files'):
                # this channel receives renamed zeek log files, we can safely delete them and close their handle
                changed_files = json.loads(msg['data'])

                # for example the old log file should be  ./zeek_files/dns.2022-05-11-14-43-20.log
                # new log file should be dns.log without the ts
                old_log_file = changed_files['old_file']
                new_log_file = changed_files['new_file']
                new_logfile_without_path = new_log_file.split('/')[-1].split(
                    '.'
                )[0]
                if new_logfile_without_path in self.ignored_files:
                    # just delete the old file
                    os.remove(old_log_file)
                    continue
                # don't allow inputprocess to access the
                # open_file_handlers dict until this thread sleeps again
                lock = threading.Lock()
                lock.acquire()
                try:
                    # close slips' open handles
                    self.open_file_handlers[new_log_file].close()
                    # delete cached filename
                    del self.open_file_handlers[new_log_file]
                except KeyError:
                    # we don't have a handle for that file,
                    # we probably don't need it in slips
                    # ex: loaded_scripts.log, stats.log etc..
                    pass
                # delete the old log file (the one with the ts)
                os.remove(old_log_file)
                lock.release()

    def shutdown_gracefully(self):
        # Stop the observer
        self.stop_observer()
        __database__.publish('finished_modules', self.name)

    def run(self):
        utils.drop_root_privs()
        # this thread should be started from run() to get the PID of inputprocess and have shared variables
        # if it started from __init__() it will have the PID of slips.py therefore,
        # any changes made to the shared variables in inputprocess will not appear in the thread
        if '-i' in sys.argv:
            self.remover_thread.start()
        try:
            # Process the file that was given
            # If the type of file is 'file (-f) and the name of the file is '-' then read from stdin
            if self.input_type == 'stdin':
                self.read_from_stdin()
            elif self.input_type == 'zeek_folder':
                # is a zeek folder
                self.read_zeek_folder()
            elif self.input_type == 'zeek_log_file':
                # Is a zeek.log file
                file_name = self.given_path.split('/')[-1]
                if 'log' in file_name:
                    self.handle_zeek_log_file()
                else:
                    return False
            elif self.input_type == 'nfdump':
                # binary nfdump file
                self.handle_nfdump()
            elif self.input_type == 'binetflow' or 'binetflow-tabs' in self.input_type:
                # argus or binetflow
                self.handle_binetflow()
            elif self.input_type in ['pcap', 'interface']:
                self.handle_pcap_and_interface()
            elif self.input_type == 'suricata':
                self.handle_suricata()
            else:
                # if self.input_type is 'file':
                # default value
                self.print(
                    f'Unrecognized file type "{self.input_type}". Stopping.'
                )
                return False
            self.shutdown_gracefully()
            return True
        except KeyboardInterrupt:
            self.shutdown_gracefully()
            return False
        except Exception as inst:
            exception_line = sys.exc_info()[2].tb_lineno
            self.print(
                f'Problem with Input Process. line {exception_line}', 0, 1
            )
            self.print(
                f'Stopping input process. Sent {self.lines} lines', 0, 1
            )
            self.print(type(inst), 0, 1)
            self.print(inst.args, 0, 1)
            self.print(inst, 0, 1)
            self.print(traceback.format_exc(), 0, 1)
            self.shutdown_gracefully()
            return False
