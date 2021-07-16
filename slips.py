#!/usr/bin/env python3
# Slips. A machine-learning Intrusion Detection System
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

import configparser
import argparse
import sys
import redis
import os
import time
import shutil
from datetime import datetime
import socket
import warnings
from modules.UpdateManager.update_file_manager import UpdateFileManager
import json
import pkgutil
import inspect
import modules
import importlib
from slips.common.abstracts import Module
from slips.common.argparse import ArgumentParser

#---------------------

version = '0.7.3'

# Ignore warnings on CPU from tensorflow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
# Ignore warnings in general
warnings.filterwarnings('ignore')
#---------------------

# # Must imports
# from slips.common.abstracts import Module
import multiprocessing
from slips.core.database import __database__
# import configparser
# import platform
#
# Your imports
import sys, os, atexit, time
from signal import SIGTERM

class Daemon(Module, multiprocessing.Process):
    description = 'This module runs when slips is in daemonized mode'

    def __init__(self, outputqueue, config):
        multiprocessing.Process.__init__(self)
        # All the printing output should be sent to the outputqueue.
        # The outputqueue is connected to another process called OutputProcess
        self.outputqueue = outputqueue
        # In case you need to read the slips.conf configuration file for
        # your own configurations
        self.config = config
        # Start the DB
        __database__.start(self.config)
        self.timeout = None
        self.read_configuration()
        self.run()


    def read_configuration(self):
        """ Read the configuration file for what we need """
        try:
            self.stdout = self.config.get('modes', 'stdin')
        except (configparser.NoOptionError, configparser.NoSectionError, NameError):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.stdout = '/dev/null' # todo should the default output file be dev null or a specific file in slips dir?

        try:
            self.stderr = self.config.get('modes', 'stderr')
        except (configparser.NoOptionError, configparser.NoSectionError, NameError):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.stderr = '/dev/null' # todo should the default stderr file be dev null or a specific file in slips dir?

        try:
            # this file is used to store the pid of the daemon and is deleted when the daemon stops
            self.pidfile = self.config.get('modes', 'pidfile')
        except (configparser.NoOptionError, configparser.NoSectionError, NameError):
            # There is a conf, but there is no option, or no section or no configuration file specified
            self.pidfile = '/etc/slips/pidfile'

        # todo these files will be growing wayy too fast we need to solve that!!
        # this is where we'll be storing stdout, stderr, and pidfile
        try:
            # create the dir
            os.mkdir('/etc/slips')
        except FileExistsError:
            pass

        # create stderr if it doesn't exist
        if not os.path.exists(self.stderr):
            open(self.stderr,'w').close()

        # create stdout if it doesn't exist
        if not os.path.exists(self.stdout):
            open(self.stdout,'w').close()

        # we don't use it anyway
        self.stdin='/dev/null'

    def print(self, text, verbose=1, debug=0):
        """
        Function to use to print text using the outputqueue of slips.
        Slips then decides how, when and where to print this text by
        taking all the prcocesses into account

        Input
         verbose: is the minimum verbosity level required for this text to
         be printed
         debug: is the minimum debugging level required for this text to be
         printed
         text: text to print. Can include format like 'Test {}'.format('here')

        If not specified, the minimum verbosity level required is 1, and the
        minimum debugging level is 0
        """

        vd_text = str(int(verbose) * 10 + int(debug))
        self.outputqueue.put(vd_text + '|' + self.name + '|[' + self.name + '] ' + str(text))

    def run(self):
        while True:
            try:
                self.print(f"Daemon is running, stdout: {self.stdout} stderr: {self.stderr}")
            except KeyboardInterrupt:
                # On KeyboardInterrupt, slips.py sends a stop_process msg to all modules, so continue to receive it
                continue
            except Exception as inst:
                self.print('Problem on the run()', 0, 1)
                self.print(str(type(inst)), 0, 1)
                self.print(str(inst.args), 0, 1)
                self.print(str(inst), 0, 1)
                return True

    def on_termination(self):
        """ deletes the pidfile to mark the daemon as closed """
        os.remove(self.pidfile)

    def daemonize(self):
        """
        Does the Unix double-fork to create a daemon
        """
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # os.chdir("/")
        # dissociate the daemon from its controlling terminal.
        # calling setsid means that this child will be the session leader of the new session
        os.setsid()
        os.umask(0)

        # If you want to prevent a process from acquiring a tty, the process shouldn't be the session leader
        # fork again so that the second child is no longer a session leader
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent (aka first child)
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # Now this code is run from the daemon
        # A daemon must close it's input and output file descriptors otherwise, it would still
        # be attached to the terminal it was started in.
        sys.stdout.flush()
        sys.stderr.flush()

        # redirect standard file descriptors
        with open(self.stdin, 'r') as stdin,\
            open(self.stdout, 'a+') as stdout,\
            open(self.stderr,'a+') as stderr:
            os.dup2(stdin.fileno(), sys.stdin.fileno())
            os.dup2(stdout.fileno(), sys.stdout.fileno())
            os.dup2(stderr.fileno(), sys.stderr.fileno())

        # write the pid of the daemon to a file so we can check if it's already opened before re-opening
        pid = str(os.getpid())
        with open(self.pidfile,'w+') as pidfile:
            pidfile.write(pid+'\n')

        # Register a function to be executed if sys.exit() is called or the main module’s execution completes
        # atexit.register(self.on_termination)

    def start(self):
        """Start the daemon"""
        # Check for a pidfile to see if the daemon is already running
        try:
            with open(self.pidfile,'r') as pidfile:
                pid = int(pidfile.read().strip())
        except (IOError,ValueError):
                pid = None

        if pid:
            sys.stderr.write(f"pidfile {pid} already exist. Daemon already running?")
            sys.exit(1)
        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """Stop the daemon"""
        # Get the pid from the pidfile
        try:
            with open(self.pidfile,'r') as pidfile:
                pid = int(pidfile.read().strip())
        except IOError:
            pid = None

        if not pid:
            sys.stderr.write(f"pidfile {pid} doesn't exist. Daemon not running?")
            return

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except (OSError) as e:
            e = str(e)
            if e.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
                else:
                    print(str(e))
                    sys.exit(1)

    def restart(self):
        """Restart the daemon"""
        self.stop()
        self.start()




class Main():
    def __init__(self):
        self.c1 = __database__.subscribe('finished_modules')

    def read_configuration(self, config, section, name):
        """ Read the configuration file for what slips.py needs. Other processes also access the configuration """
        try:
            return config.get(section, name)
        except (configparser.NoOptionError, configparser.NoSectionError, NameError):
            # There is a conf, but there is no option, or no section or no configuration file specified
            return False

    def recognize_host_ip(self):
        """
        Recognize the IP address of the machine
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("1.1.1.1", 80))
            ipaddr_check = s.getsockname()[0]
            s.close()
        except Exception as ex:
            # not connected to the internet
            return None
        return ipaddr_check

    def create_folder_for_logs(self):
        '''
        Create a folder for logs if logs are enabled
        '''
        logs_folder = datetime.now().strftime('%Y-%m-%d--%H-%M-%S')
        if not os.path.exists(logs_folder):
            os.makedirs(logs_folder)
        return logs_folder

    def update_malicious_file(self, outputqueue, config):
        '''
        Update malicious files and store them in database before slips start
        '''
        update_manager = UpdateFileManager(outputqueue, config)
        update_manager.update()

    def check_redis_database(self, redis_host='localhost', redis_port=6379) -> str:
        """
        Check if we have redis-server running
        """
        try:
            r = redis.StrictRedis(host=redis_host, port=redis_port, db=0, charset="utf-8",
                                       decode_responses=True)
            r.ping()
        except Exception as ex:
            print('[DB] Error: Is redis database running? You can run it as: "redis-server --daemonize yes"')
            return False
        return True

    def clear_redis_cache_database(self, redis_host = 'localhost', redis_port = 6379) -> str:
        """
        Clear cache database
        """
        rcache = redis.StrictRedis(host=redis_host, port=redis_port, db=1, charset="utf-8",
                                   decode_responses=True)
        rcache.flushdb()

    def check_zeek_or_bro(self):
        """
        Check if we have zeek or bro
        """
        if shutil.which('zeek'):
            return 'zeek'
        elif shutil.which('bro'):
            return 'bro'
        return False

    def terminate_slips(self):
        """
        Do all necessary stuff to stop process any clear any files.
        """
        sys.exit(-1)

    def load_modules(self, to_ignore):
        """
        Import modules and loads the modules from the 'modules' folder. Is very relative to the starting position of slips
        """

        plugins = dict()

        # Walk recursively through all modules and packages found on the . folder.
        # __path__ is the current path of this python program
        for loader, module_name, ispkg in pkgutil.walk_packages(modules.__path__, modules.__name__ + '.'):
            if any(module_name.__contains__(mod) for mod in to_ignore):
                continue
            # If current item is a package, skip.
            if ispkg:
                continue

            # Try to import the module, otherwise skip.
            try:
                # "level specifies whether to use absolute or relative imports. The default is -1 which
                # indicates both absolute and relative imports will be attempted. 0 means only perform
                # absolute imports. Positive values for level indicate the number of parent
                # directories to search relative to the directory of the module calling __import__()."
                module = importlib.import_module(module_name)
            except ImportError as e:
                print("Something wrong happened while importing the module {0}: {1}".format(module_name, e))
                continue

            # Walk through all members of currently imported modules.
            for member_name, member_object in inspect.getmembers(module):
                # Check if current member is a class.
                if inspect.isclass(member_object):
                    if issubclass(member_object, Module) and member_object is not Module:
                        plugins[member_object.name] = dict(obj=member_object, description=member_object.description)

        return plugins

    def get_cwd(self):
        # Can't use os.getcwd() because slips directory name won't always be Slips plus this way requires less parsing
        for arg in sys.argv:
            if 'slips.py' in arg:
                # get the path preceeding slips.py (may be ../ or  ../../ or '' if slips.py is in the cwd) , this path is where slips.conf will be
                cwd = arg[:arg.index('slips.py')]
                return cwd

    def shutdown_gracefully(self):
        """ Wait for all modules to confirm that they're done processing and then shutdown """

        try:
            print('Stopping Slips')
            # Stop the modules that are subscribed to channels
            __database__.publish_stop()
            # Here we should Wait for any channel if it has still
            # data to receive in its channel
            finished_modules = []
            loaded_modules = self.modules_to_call.keys()
            # get dict of pids spawned by slips
            PIDs = __database__.get_PIDs()
            # timeout variable so we don't loop forever
            max_loops = 130
            # loop until all loaded modules are finished
            while len(finished_modules) < len(loaded_modules) and max_loops != 0:
                # print(f"Modules not finished yet {set(loaded_modules) - set(finished_modules)}")
                message = self.c1.get_message(timeout=0.01)
                if message and message['data'] == 'stop_process':
                    continue
                if message and message['channel'] == 'finished_modules' and type(message['data']) is not int:
                    # all modules must reply with their names in this channel after
                    # receiving the stop_process msg
                    # to confirm that all processing is done and we can safely exit now
                    module_name = message['data']
                    if module_name not in finished_modules:
                        finished_modules.append(module_name)
                        # remove module from the list of opened pids
                        PIDs.pop(module_name)
                        modules_left = len(set(loaded_modules) - set(finished_modules))
                        print(f"\033[1;32;40m{module_name}\033[00m Stopped... \033[1;32;40m{modules_left}\033[00m left.")
                max_loops -=1
            # kill processes that didn't stop after timeout
            for unstopped_proc,pid in PIDs.items():
                try:
                    os.kill(int(pid), 9)
                    print(f'\033[1;32;40m{unstopped_proc}\033[00m Killed.')
                except ProcessLookupError:
                    print(f'\033[1;32;40m{unstopped_proc}\033[00m Already exited.')
            # Send manual stops to the process not using channels
            try:
                self.logsProcessQueue.put('stop_process')
            except NameError:
                # The logsProcessQueue is not there because we
                # didnt started the logs files (used -l)
                pass
            self.outputProcessQueue.put('stop_process')
            self.profilerProcessQueue.put('stop_process')
            self.inputProcess.terminate()
            os._exit(-1)
            return
        except KeyboardInterrupt:
            return
        
    def run(self):
            
        # Before the argparse, we need to set up the default path fr alerts.log and alerts.json. In our case, it is output folder.
        alerts_default_path = 'output/'

        # Parse the parameters
        slips_conf_path = self.get_cwd() + 'slips.conf'
        parser = ArgumentParser(usage = "./slips.py -c <configfile> [options] [file ...]",
                                add_help=False)
        parser.add_argument('-c','--config', metavar='<configfile>',action='store',required=False,
                            help='path to the Slips config file.')
        parser.add_argument('-v', '--verbose',metavar='<verbositylevel>',action='store', required=False, type=int,
                            help='amount of verbosity. This shows more info about the results.')
        parser.add_argument('-e', '--debug', metavar='<debuglevel>',action='store', required=False, type=int,
                            help='amount of debugging. This shows inner information about the program.')
        parser.add_argument('-f', '--filepath',metavar='<file>', action='store',required=False,
                            help='read an Argus binetflow or a Zeek folder.')
        parser.add_argument('-i','--interface', metavar='<interface>',action='store', required=False,
                            help='read packets from an interface.')
        parser.add_argument('-r', '--pcapfile',metavar='<file>', action='store', required=False,
                            help='read a PCAP - Packet Capture.')
        parser.add_argument('-b', '--nfdump', metavar='<file>',action='store',required=False,
                            help='read an NFDUMP - netflow dump. ')
        parser.add_argument('-l','--nologfiles',action='store_true',required=False,
                            help='do not create log files with all the traffic info and detections.')
        parser.add_argument('-F','--pcapfilter',action='store',required=False,type=str,
                            help='packet filter for Zeek. BPF style.')
        parser.add_argument('-G', '--gui', help='Use the nodejs GUI interface.', required=False, default=False, action='store_true')
        parser.add_argument('-cc','--clearcache',action='store_true', required=False,
                            help='clear a cache database.')
        parser.add_argument('-p', '--blocking',action='store_true',required=False,
                            help='block IPs that connect to the computer. Supported only on Linux.')
        parser.add_argument('-o', '--output', action='store', required=False, default=alerts_default_path,
                            help='store alerts.json and alerts.txt in the provided folder.')
        parser.add_argument("-h", "--help", action="help", help="command line help")
    
        args = parser.parse_args()
    
        # Read the config file name given from the parameters
        # don't use '%' for interpolation.
        config = configparser.ConfigParser(interpolation=None)
        try:
            with open(args.config) as source:
                config.read_file(source)
        except IOError:
            pass
        except TypeError:
            # No conf file provided
            pass
    
        # Check if redis server running
        if self.check_redis_database() is False:
            self.terminate_slips()
    
        # If we need zeek (bro), test if we can run it.
        # Need to be assign to something because we pass it to inputProcess later
        zeek_bro = None
        if args.pcapfile or args.interface:
            zeek_bro = self.check_zeek_or_bro()
            if zeek_bro is False:
                # If we do not have bro or zeek, terminate Slips.
                print('no zeek nor bro')
                self.terminate_slips()
    
        # See if we have the nfdump, if we need it according to the input type
        if args.nfdump and shutil.which('nfdump') is None:
            # If we do not have nfdump, terminate Slips.
            self.terminate_slips()
    
        # Clear cache if the parameter was included
        if args.clearcache:
            print('Deleting Cache DB in Redis.')
            self.clear_redis_cache_database()
            self.terminate_slips()
    
        # Remove default folder for alerts, if exists
        if os.path.exists(alerts_default_path):
            try:
                shutil.rmtree(alerts_default_path)
            except OSError :
                # Directory not empty (may contain hidden non-deletable files), don't delete dir
                pass
    
        # Create output folder for alerts.txt and alerts.json if they do not exist
        if not os.path.exists(args.output):
            os.makedirs(args.output)
    
        try:
            # can be daemonized or interactive
            working_mode = config.get('modes', 'slips_mode')
        except (configparser.NoOptionError, configparser.NoSectionError, NameError, ValueError):
            #todo make it daemonized by default
            working_mode = 'interactive'

        # If the user wants to blocks, the user needs to give a permission to modify iptables
        # Also check if the user blocks on interface, does not make sense to block on files
        if args.interface and args.blocking:
            print('Allow Slips to block malicious connections. Executing "sudo iptables -N slipsBlocking"')
            os.system('sudo iptables -N slipsBlocking')
    
        """
        Import modules here because if user wants to run "./slips.py --help" it should never throw error. 
        """
        from multiprocessing import Queue
        from inputProcess import InputProcess
        from outputProcess import OutputProcess
        from profilerProcess import ProfilerProcess
        from guiProcess import GuiProcess
        from logsProcess import LogsProcess
        from evidenceProcess import EvidenceProcess
    
        # Any verbosity passed as parameter overrides the configuration. Only check its value
        if args.verbose == None:
            # Read the verbosity from the config
            try:
                args.verbose = int(config.get('parameters', 'verbose'))
            except (configparser.NoOptionError, configparser.NoSectionError, NameError, ValueError):
                # There is a conf, but there is no option, or no section or no configuration file specified
                # By default, 1
                args.verbose = 1
    
        # Limit any verbosity to > 0
        if args.verbose < 1:
            args.verbose = 1
    
        # Any debuggsity passed as parameter overrides the configuration. Only check its value
        if args.debug == None:
            # Read the debug from the config
            try:
                args.debug = int(config.get('parameters', 'debug'))
            except (configparser.NoOptionError, configparser.NoSectionError, NameError, ValueError):
                # There is a conf, but there is no option, or no section or no configuration file specified
                # By default, 0
                args.debug = 0
    
        # Limit any debuggisity to > 0
        if args.debug < 0:
            args.debug = 0
    
        # Check the type of input
        if args.interface:
            input_information = args.interface
            input_type = 'interface'
        elif args.pcapfile:
            input_information = args.pcapfile
            input_type = 'pcap'
        elif args.filepath:
            input_information = args.filepath
            input_type = 'file'
        elif args.nfdump:
            input_information = args.nfdump
            input_type = 'nfdump'
        else:
            print('You need to define an input source.')
            sys.exit(-1)
    
        ##########################
        # Creation of the threads
        ##########################
        from slips.core.database import __database__
        # Output thread. This thread should be created first because it handles
        # the output of the rest of the threads.
        # Create the queue
        self.outputProcessQueue = Queue()
        # Create the output thread and start it
        outputProcessThread = OutputProcess(self.outputProcessQueue, args.verbose, args.debug, config)
        outputProcessThread.start()
    
        # Before starting update malicious file
        self.update_malicious_file(self.outputProcessQueue,config)
        # Print the PID of the main slips process. We do it here because we needed the queue to the output process
        self.outputProcessQueue.put('20|main|Started main program [PID {}]'.format(os.getpid()))
        # Output pid
        self.outputProcessQueue.put('20|main|Started output thread [PID {}]'.format(outputProcessThread.pid))
        __database__.store_process_PID('outputProcess',int(outputProcessThread.pid))
    
        # Start each module in the folder modules
        self.outputProcessQueue.put('01|main|[main] Starting modules')
        to_ignore = self.read_configuration(config, 'modules', 'disable')
        # This plugins import will automatically load the modules and put them in the __modules__ variable
        if to_ignore:
            # Convert string to list
            to_ignore = to_ignore.replace("[","").replace("]","").replace(" ","").split(",")
            # Ignore exporting alerts module if export_to is empty
            export_to = config.get('ExportingAlerts', 'export_to').rstrip("][").replace(" ","")
            if 'stix' not in export_to.lower() and 'slack' not in export_to.lower():
                to_ignore.append('ExportingAlerts')
            # Disable blocking if was not asked and if it is not interface
            if not args.blocking or not args.interface:
                to_ignore.append('blocking')
    
            try:
                # This 'imports' all the modules somehow, but then we ignore some
                self.modules_to_call = self.load_modules(to_ignore)
                for module_name in self.modules_to_call:
                    if not module_name in to_ignore:
                        module_class = self.modules_to_call[module_name]['obj']
                        ModuleProcess = module_class(self.outputProcessQueue, config)
                        ModuleProcess.start()
                        self.outputProcessQueue.put('20|main|\t[main] Starting the module {} ({}) [PID {}]'.format(module_name, self.modules_to_call[module_name]['description'], ModuleProcess.pid))
                        __database__.store_process_PID(module_name, int(ModuleProcess.pid))
            except TypeError:
                # There are not modules in the configuration to ignore?
                print('No modules are ignored')
    
        # Get the type of output from the parameters
        # Several combinations of outputs should be able to be used
        if args.gui:
            # Create the curses thread
            guiProcessQueue = Queue()
            guiProcessThread = GuiProcess(guiProcessQueue, self.outputProcessQueue, args.verbose, args.debug, config)
            guiProcessThread.start()
            self.outputProcessQueue.put('quiet')
        # By default, don't log unless specified in slips.conf and -l isn't provided
        logs_folder = False
        # if there is no -l
        if not args.nologfiles:
            # By parameter, this is True. Then check the conf. Only create the logs if the conf file says True
            do_logs = self.read_configuration(config, 'parameters', 'create_log_files')
            if do_logs == 'yes':
                # Create a folder for logs
                logs_folder = self.create_folder_for_logs()
                # Create the logsfile thread if by parameter we were told, or if it is specified in the configuration
                self.logsProcessQueue = Queue()
                logsProcessThread = LogsProcess(self.logsProcessQueue, self.outputProcessQueue, args.verbose, args.debug, config, logs_folder)
                logsProcessThread.start()
                self.outputProcessQueue.put('20|main|Started logsfiles thread [PID {}]'.format(logsProcessThread.pid))
                __database__.store_process_PID('logsProcess',int(logsProcessThread.pid))
        # If args.nologfiles is False, then we don't want log files, independently of what the conf says.
    
        # Evidence thread
        # Create the queue for the evidence thread
        evidenceProcessQueue = Queue()
        # Create the thread and start it
        evidenceProcessThread = EvidenceProcess(evidenceProcessQueue, self.outputProcessQueue, config, args.output, logs_folder)
        evidenceProcessThread.start()
        self.outputProcessQueue.put('20|main|Started Evidence thread [PID {}]'.format(evidenceProcessThread.pid))
        __database__.store_process_PID('evidenceProcess', int(evidenceProcessThread.pid))
    
    
        # Profile thread
        # Create the queue for the profile thread
        self.profilerProcessQueue = Queue()
        # Create the profile thread and start it
        profilerProcessThread = ProfilerProcess(self.profilerProcessQueue, self.outputProcessQueue, args.verbose, args.debug, config)
        profilerProcessThread.start()
        self.outputProcessQueue.put('20|main|Started profiler thread [PID {}]'.format(profilerProcessThread.pid))
        __database__.store_process_PID('profilerProcess', int(profilerProcessThread.pid))
    
        # Input process
        # Create the input process and start it
        self.inputProcess = InputProcess(self.outputProcessQueue, self.profilerProcessQueue, input_type, input_information, config, args.pcapfilter, zeek_bro)
        self.inputProcess.start()
        self.outputProcessQueue.put('20|main|Started input thread [PID {}]'.format(self.inputProcess.pid))
        __database__.store_process_PID('inputProcess', int(self.inputProcess.pid))
    
    

        # Store the host IP address if input type is interface
        if input_type == 'interface':
            hostIP = self.recognize_host_ip()
            while True:
                try:
                    __database__.set_host_ip(hostIP)
                    break
                except redis.exceptions.DataError:
                    print("Not Connected to the internet. Reconnecting in 10s.")
                    time.sleep(10)
                    hostIP = self.recognize_host_ip()
    
        # As the main program, keep checking if we should stop slips or not
        # This is not easy since we need to be sure all the modules are stopped
        # Each interval of checking is every 5 seconds
        check_time_sleep = 5
        # In each interval we check if there has been any modifications to the database by any module.
        # If not, wait this amount of intervals and then stop slips.
        # We choose 6 to wait 30 seconds.
        limit_minimum_intervals_to_wait = 4
        minimum_intervals_to_wait = limit_minimum_intervals_to_wait
        fieldseparator = __database__.getFieldSeparator()
        slips_internal_time = 0
        try:
            while True:
                # Sleep some time to do rutine checks
                time.sleep(check_time_sleep)
                slips_internal_time = __database__.getSlipsInternalTime()
                # Get the amount of modified time windows since we last checked
                TWModifiedforProfile = __database__.getModifiedTWSinceTime(float(slips_internal_time) + 1)
                # TWModifiedforProfile = __database__.getModifiedTW()
                amount_of_modified = len(TWModifiedforProfile)
                # Get th time of last modified timewindow and set it as a new
                if amount_of_modified != 0:
                    time_last_modified_tw = TWModifiedforProfile[-1][-1]
                    __database__.setSlipsInternalTime(time_last_modified_tw)
                # How many profiles we have?
                profilesLen = str(__database__.getProfilesLen())
                self.outputProcessQueue.put('20|main|[Main] Total Number of Profiles in DB so far: {}. Modified Profiles in the last TW: {}. ({})'.format(profilesLen, amount_of_modified, datetime.now().strftime('%Y-%m-%d--%H:%M:%S')))
    
                # Check if we need to close some TW
                __database__.check_TW_to_close()
    
                # In interface we keep track of the host IP. If there was no
                # modified TWs in the host NotIP, we check if the network was changed.
                # Dont try to stop slips if its catpurting from an interface
                if args.interface:
                    # To check of there was a modified TW in the host IP. If not,
                    # count down.
                    modifiedTW_hostIP = False
                    for profileTW in TWModifiedforProfile:
                        profileIP = profileTW[0].split(fieldseparator)[1]
                        # True if there was a modified TW in the host IP
                        if hostIP == profileIP:
                            modifiedTW_hostIP = True
    
                    # If there was no modified TW in the host IP
                    # then start counting down
                    # After count down we update the host IP, to check if the
                    # network was changed
                    if not modifiedTW_hostIP and args.interface:
                        if minimum_intervals_to_wait == 0:
                            hostIP = self.recognize_host_ip()
                            if hostIP:
                                __database__.set_host_ip(hostIP)
                            minimum_intervals_to_wait = limit_minimum_intervals_to_wait
                        minimum_intervals_to_wait -= 1
                    else:
                        minimum_intervals_to_wait = limit_minimum_intervals_to_wait
    
                # ---------------------------------------- Stopping slips
    
                # When running Slips in the file.
                # If there were no modified TW in the last timewindow time,
                # then start counting down
                else:
                    if amount_of_modified == 0:
                        # print('Counter to stop Slips. Amount of modified
                        # timewindows: {}. Stop counter: {}'.format(amount_of_modified, minimum_intervals_to_wait))
                        if minimum_intervals_to_wait == 0:
                            self.shutdown_gracefully()
                            break
                        minimum_intervals_to_wait -= 1
                    else:
                        minimum_intervals_to_wait = limit_minimum_intervals_to_wait
    
        except KeyboardInterrupt:
            self.shutdown_gracefully()
        



####################
# Main
####################
if __name__ == '__main__':
    print('Slips. Version {}'.format(version))
    print('https://stratosphereips.org\n')

