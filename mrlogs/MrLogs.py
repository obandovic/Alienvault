#!/usr/bin/env python
# MrLogs takes syslog logs and cuts them up and resends them to a specified
# syslog server.
#
#execute: python Mrlogs.py -s USM_Server_IP -f daemon logfile_name
#
# Author: Alex Lisle alisle@alienvault.com

__version__ = '0.02'

import argparse
import sys
import re
import netsyslog
import random
import syslog
import time
from datetime import datetime

_MAX_LINES = 1000
_SERVERS = ["127.0.0.1"]
_USE_DATE = False
_EPS = 10
_ONLYONCE = False
_FACILITY = 'local0'
_PRIORITY = 'info'
_MAXMSGS  = 0

SYSLOG_FACILITIES = ['local0', 'local1', 'local2', 'local3',
     'local4', 'local5', 'local6', 'local7',
     'kern', 'user', 'mail', 'daemon', 'auth',
     'syslog', 'lpr', 'news', 'uucp', 'cron',
     'authpriv', 'ftp' ]

SYSLOG_SEVERITIES = ['emerg', 'alert', 'crit', 'err',
     'warning', 'notice', 'info', 'debug']

messages = []


def Version():
    print "MrLog Version:" + __version__


def ProcessFiles(files):
    global messages, args
    syslogMask = re.compile(r'^(?P<date>\w{3}\s{1,2}\d{1,2}\s\d{2}:\d{2}:\d{2})\s(?P<host>\S+)\s(?P<tag>\S+)\s(?P<msg>.*)')

    for file in files:
        print "Loading lines from " + file

        currentFile = open(file)
        line = currentFile.readline()

        for x in range(1, args.numlines):
            if not line:
                break

            matches  = syslogMask.search(line)
            if matches is not None:
                message = {}
                if args.keepdate:
                    message["Date"] =  matches.group(1)
                else:
                    message["Date"] =  datetime.now().strftime('%b %d %H:%M:%S')

                message["Host"] = matches.group(2)
                message["Tag"] = matches.group(3).replace(':','')
                message["Msg"] = matches.group(4)

                messages.append(message)

            line = currentFile.readline()

def ServerSplit(s):
    try:
        servers = s.split(',')
        return servers
    except:
        raise argparse.ArgumentTypeError("Servers must be single server or a list of comma separated servers")

def SyslogFacility(s):
    ### used as a default
    global _FACILITY

    intfacility = -1

    facility = "LOG_" + s.upper()
    intfacility = eval("syslog." + facility)
    return int(intfacility)

def SyslogPriority(s):
    ### used as a default
    global _PRIORITY

    intpriority = -1

    priority = "LOG_" + s.upper()
    intpriority = eval("syslog." + priority)
    return int(intpriority)

def StartLogging():

    global messages, args, _EPS

    _EPS = args.eps
    smoothEPS = args.eps
    maxTime = 1

    # We need to smooth out the EPS, if we chuck all the logs as fast as we
    # can, we end up filling up the buffers and packets get dropped. So we
    # limit the output
    if args.eps > 100:
        smoothEPS = args.eps / 100
        maxTime = 0.01

    logger = netsyslog.Logger()

    for server in args.server:
        if ':' in server:
            host, port = server.split(":")

            if host:
                print "Adding host: " + host
                logger.add_host(host)
                if port:
                    print "Adding port: " + port
                    logger.PORT = int(port)
        else:
            logger.add_host(server)

    #for server in _SERVERS:
        #host = server
        #port = 514

        #if ":" in server:
            #host, port = server.split(":")

        #if host:
            #print "Adding host: " + host
            #logger.add_host(host)
            #if port:
                #print "Adding port: " + str(port)
                #logger.PORT = int(port)
        #else:
            #logger.add_host(server)

    packetsSent = 0
    eps_time_start = time.time()

    facility = SyslogFacility(args.facility)
    priority = SyslogPriority(args.priority)

    while 1:
        smooth_time_start = time.time()

        messages_sent = 0
        for x in range(0, smoothEPS):
            messages_sent +=1
            message = messages[random.randrange(0, len(messages))]
            pri = netsyslog.PriPart(facility, priority)
            message["Date"] =  datetime.now().strftime('%b %d %H:%M:%S')
            header = netsyslog.HeaderPart(message["Date"], message["Host"])
            msg = netsyslog.MsgPart(tag=message["Tag"], content=message["Msg"])
            packet = netsyslog.Packet(pri, header, msg)
            logger.send_packet(packet)

        time_taken = time.time() - smooth_time_start
        if time_taken < maxTime:
            time.sleep(maxTime - time_taken)

        time_taken = time.time() - eps_time_start
        if time_taken > 1:
            #if _EPS > 100:
                #print "Current EPS=" + str(messages_sent * 100)
            #else:
                #print "Current EPS=" + str(messages_sent)

            print "Current EPS=" + str(_EPS)  # + str(messages_sent * 100)
            eps_time_start = time.time()

        packetsSent += messages_sent
        if args.once and packetsSent > args.eps:
            break
        if args.max and packetsSent > args.max:
            break

parser = argparse.ArgumentParser(description="Send logs to a series of hosts")

### add command line argument processing
parser.add_argument('-n', '--numlines', type=int,
    help="Specify the number of lines to take from each log, default: 1000", default=_MAX_LINES)
parser.add_argument('-v', '--version',
    help="Print version number and exit.", action='store_true')
parser.add_argument('-s', '--server',
    help="Specify syslog server(s) to use, example: 10.0.0.1,10.0.0.2", default="127.0.0.1", type=ServerSplit)

parser.add_argument('-d', '--keepdate', action='store_true',
    help="Keep the dates within the logs when sending them. Default: ignore date", default=_USE_DATE)

parser.add_argument('-e', '--eps',
    help="EPS rate, default: 10", default=_EPS, type=int)

parser.add_argument('-o', '--once',
    help="Only send the logs once", default=_ONLYONCE, action='store_true')

parser.add_argument('-m', '--max', type=int,
    help="Maximum number of messages to send, 0 means no maximum, default: 0", default=_MAXMSGS)

parser.add_argument('-f', '--facility',
    help="Syslog facility used for sending logs", default=_FACILITY,
    choices=SYSLOG_FACILITIES )

parser.add_argument('-p', '--priority',
    help="Syslog priority used for sending logs", default=_PRIORITY,
    choices=SYSLOG_SEVERITIES )

parser.add_argument('files',
    help="files with events", nargs='+')

args = parser.parse_args()

if args.version:
    Version()
    exit()

ProcessFiles(args.files)

if len(messages) < 1:
    exit(1)

StartLogging()

