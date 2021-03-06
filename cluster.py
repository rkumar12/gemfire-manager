#!/usr/bin/python
#
# Copyright (c) 2015-2016 Pivotal Software, Inc. All Rights Reserved.
#
from __future__ import print_function

import clusterdef
import gemprops
#import netifaces
import os
import os.path
import platform
import socket
import subprocess
import sys
import time

# This file will read information from cluster.json (generated by generateAWSCluster.py)
#
LOCATOR_PID_FILE="cf.gf.locator.pid"
SERVER_PID_FILE="vf.gf.server.pid"

clusterDef = None



def ensureDir(dname):
    if not os.path.isdir(dname):
        os.mkdir(dname)

def locatorDir(processName):
    clusterHomeDir = clusterDef.locatorProperty(processName, 'cluster-home')
    return(os.path.join(clusterHomeDir,processName))

def datanodeDir(processName):
    clusterHomeDir = clusterDef.datanodeProperty(processName, 'cluster-home')
    return(os.path.join(clusterHomeDir,processName))


def pidIsAlive(pidfile):
    if platform.system() == 'Windows':
        if not os.path.exists(pidfile):
            return False
        else:
            return True
    else:
        if not os.path.exists(pidfile):
            return False

        with open(pidfile,"r") as f:
            pid = int(f.read())

        proc = subprocess.Popen(["ps",str(pid)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        proc.communicate()

        if proc.returncode == 0:
            return True
        else:
            return False

def killDataNode(processName):
    pidfile = os.path.join(clusterDef.datanodeProperty(processName, 'cluster-home'), processName, SERVER_PID_FILE)
    with open(pidfile,"r") as f:
        pid = int(f.read())

    if platform.system == 'Windows':
        subprocess.call(['Taskkill', '/PID' ,pid, '/F'])
    else:
        subprocess.call(['kill','-9',pid])

    os.remove(pidfile)

def serverIsRunning(processName):
    try:
        port = clusterDef.locatorProperty(processName, 'server-port')
        bindAddress = clusterDef.datanodeProperty(processName, 'server-bind-address')

        #leave the double parens in the line below!
        sock = socket.create_connection((bindAddress, port))
        sock.close()

        return True
    except Exception as x:
        pass
        # ok - probably not running

    # now check the pid file
    pidfile = os.path.join(clusterDef.datanodeProperty(processName, 'cluster-home'), processName, SERVER_PID_FILE)
    result = pidIsAlive(pidfile)
    return result

def locatorIsRunning(processName):
    port = clusterDef.locatorProperty(processName, 'port')
    bindAddress = clusterDef.locatorProperty(processName, 'bind-address',notFoundOK = True)
    if bindAddress is None:
        # if bind address was not specified then the locator should be
        # listening on all network interfaces including 127.0.0.1
        bindAddress = '127.0.0.1'

    try:
        #leave the double parens in the line below!
        sock = socket.create_connection( (bindAddress, port))
        sock.close()
        return True
    except Exception as x:
        pass
        # ok - probably not running

    # now check the pid file
    pidfile = os.path.join(clusterDef.locatorProperty(processName, 'cluster-home'), processName, LOCATOR_PID_FILE)

    return pidIsAlive(pidfile)

def stopLocator(processName):
    GEMFIRE = clusterDef.locatorProperty(processName,'gemfire')
    os.environ['GEMFIRE'] = GEMFIRE
    os.environ['JAVA_HOME'] = clusterDef.locatorProperty(processName,'java-home')

    if not locatorIsRunning(processName):
        print('{0} is not running'.format(processName))
        return
    try:
        subprocess.check_call([os.path.join(GEMFIRE,'bin',gfsh_script)
            , "stop", "locator"
            ,"--dir=" + locatorDir(processName)])

        for attempt in range(18):
            if not locatorIsRunning(processName):
                break
            else:
                print('waiting for locator to stop ...')
                time.sleep(10)

        if locatorIsRunning(processName):
            print('WARNING: could not verify that {0} has stopped'.format(processName))
        else:
            print('stopped ' + processName)

    except subprocess.CalledProcessError as x:
        sys.exit(x.message)

def stopServer(processName):
    GEMFIRE = clusterDef.datanodeProperty(processName,'gemfire')
    os.environ['GEMFIRE'] = GEMFIRE
    os.environ['JAVA_HOME'] = clusterDef.datanodeProperty(processName,'java-home')

    if not serverIsRunning(processName):
        print('{0} is not running'.format(processName))
        return
    try:
        subprocess.check_call([os.path.join(GEMFIRE,'bin',gfsh_script)
            , "stop", "server"
            ,"--dir=" + datanodeDir(processName)])

        for attempt in range(18):
            if not serverIsRunning(processName):
                break
            else:
                print('waiting for server to stop ...')
                time.sleep(10)

        if serverIsRunning(processName):
            print('WARNING: could not verify that {0} has stopped (it will be killed)'.format(processName))
            killDataNode(processName)

        else:
            print('stopped ' + processName)



    except subprocess.CalledProcessError as x:
        sys.exit(x.message)


def statusLocator(processName):
    GEMFIRE = clusterDef.locatorProperty(processName,'gemfire')
    os.environ['GEMFIRE'] = GEMFIRE
    os.environ['JAVA_HOME'] = clusterDef.locatorProperty(processName,'java-home')

    try:
        subprocess.check_call([os.path.join(GEMFIRE,'bin',gfsh_script)
            , "status", "locator"
            ,"--dir=" + locatorDir(processName)])

    except subprocess.CalledProcessError as x:
        sys.exit(x.output)

def statusServer(processName):
    GEMFIRE = clusterDef.datanodeProperty(processName,'gemfire')
    os.environ['GEMFIRE'] = GEMFIRE
    os.environ['JAVA_HOME'] = clusterDef.datanodeProperty(processName,'java-home')

    try:
        subprocess.check_call([os.path.join(GEMFIRE,'bin',gfsh_script)
            , "status", "server"
            ,"--dir=" + datanodeDir(processName)])

    except subprocess.CalledProcessError as x:
        sys.exit(x.output)

def launchLocatorProcess(processName):
    GEMFIRE = clusterDef.locatorProperty(processName,'gemfire')
    JAVA_HOME = clusterDef.locatorProperty(processName,'java-home')
    os.environ['GEMFIRE'] = GEMFIRE
    os.environ['JAVA_HOME'] = JAVA_HOME
    if 'CLASSPATH' in os.environ:
        os.environ['CLASSPATH'] = os.environ['CLASSPATH'] + os.pathsep + os.path.join(JAVA_HOME,'lib','tools.jar')
    else:
        os.environ['CLASSPATH'] = os.path.join(JAVA_HOME,'lib','tools.jar')


    ensureDir(clusterDef.locatorProperty(processName, 'cluster-home'))
    ensureDir(locatorDir(processName))

    if locatorIsRunning(processName):
        print('locator {0} is already running'.format(processName))
        return

    cmdLine = [os.path.join(GEMFIRE,'bin',gfsh_script)
        , "start", "locator"
        ,"--dir=" + locatorDir(processName)
        ,"--name={0}".format(processName)]

    #these are optional
    for setting in gemprops.HANDLED_PROPS[4:]:
        if clusterDef.hasLocatorProperty(processName,setting):
            cmdLine.append('--{1}={0}'.format(clusterDef.locatorProperty(processName, setting),setting))

    cmdLine[len(cmdLine):] = clusterDef.gfshArgs('locator',processName)

    try:
        proc = subprocess.Popen(cmdLine)
    except subprocess.CalledProcessError as x:
        sys.exit(x.message)

    return proc


def startLocator(processName):
    proc = launchLocatorProcess(processName)

    #could be none if the locator was really already running
    if proc is not None:
        if proc.wait() != 0:
            sys.exit("locator process failed to start - see the logs in {0}".format(locatorDir(processName)))

def startServerCommandLine(processName):
    GEMFIRE = clusterDef.datanodeProperty(processName,'gemfire')

    #the properties in this list are required
    cmdLine = [os.path.join(GEMFIRE,'bin',gfsh_script)
        , "start", "server"
        ,"--dir=" + datanodeDir(processName)
        ,"--name={0}".format(processName)
        ]

    #these are optional
    for setting in gemprops.HANDLED_PROPS[4:]:
        if clusterDef.hasDatanodeProperty(processName,setting):
            cmdLine.append('--{1}={0}'.format(clusterDef.datanodeProperty(processName, setting),setting))

    #all the rest are passed through as -Ds. Those recognized as gemfire properties
    #are prefixed with "gemfire."
    cmdLine[len(cmdLine):] = clusterDef.gfshArgs('datanode',processName)

    return cmdLine

# returns a Popen object
def launchServerProcess(processName):
    GEMFIRE = clusterDef.datanodeProperty(processName,'gemfire')
    JAVA_HOME = clusterDef.datanodeProperty(processName,'java-home')
    os.environ['GEMFIRE'] = GEMFIRE
    os.environ['JAVA_HOME'] = JAVA_HOME
    os.environ['JAVA_ARGS'] = '-Dgfsh.log-dir=. -Dgfsh.log-level=fine'
    if 'CLASSPATH' in os.environ:
        os.environ['CLASSPATH'] = os.environ['CLASSPATH'] + os.pathsep + os.path.join(JAVA_HOME,'lib','tools.jar')
    else:
        os.environ['CLASSPATH'] = os.path.join(JAVA_HOME,'lib','tools.jar')
    #os.environ['JAVA_ARGS'] = '-Dgfsh.log-dir=.'

    ensureDir(clusterDef.datanodeProperty(processName, 'cluster-home'))
    ensureDir(datanodeDir(processName))

    if serverIsRunning(processName):
        print('{0} is already running'.format(processName))
        return

    cmdLine = startServerCommandLine(processName)
    #print('>>> starting server with {0}'.format(' '.join(cmdLine)))

    try:
        proc = subprocess.Popen(cmdLine)
    except subprocess.CalledProcessError as x:
        sys.exit(x.message)

    return proc


def startServer(processName):
    proc = launchServerProcess(processName)

    #could be none if the server was really already running
    if proc is not None:
        if proc.wait() != 0:
            sys.exit("cache server process failed to start - see the logs in {0}".format(datanodeDir(processName)))

# node type is 'datanode' or 'accessor'
def startNodes(nodeType):
    procList = []
    for dnode in clusterDef.processesOnThisHost(nodeType):
        proc = launchServerProcess(dnode)
        #can be None if server was already started
        if proc is not None:
            procList.append(proc)

    failCount = 0
    for proc in procList:
        if proc.wait() != 0:
            failCount += 1

    if failCount > 0:
        print('At least one server failed to start. Please check the logs for more detail')

# this method does not start accessors
def startClusterLocal():

    # probably is only going to be one - using "launch" for local clusters with multiple locators
    procList = []
    failCount = 0
    for locator in clusterDef.locatorsOnThisHost():
        proc = launchLocatorProcess(locator)
        if proc is not None:
            procList.append(proc)

    for proc in procList:
        if proc.wait() != 0:
            failCount += 1

    if failCount > 0:
        sys.exit('At least one locator failed to start.  Please check the logs.')

    for attempt in range(3):
        failCount = 0
        procList = []
        for dnode in clusterDef.datanodesOnThisHost():
            proc = launchServerProcess(dnode)
            #can be None if server was already started
            if proc is not None:
                procList.append(proc)

        for proc in procList:
            if proc.wait() != 0:
                failCount += 1

        if failCount == 0:
            break
        else:
            print('at least one server failed to start - will try {0} more times'.format(2-attempt))
            time.sleep(20)

    if failCount > 0:
        sys.exit('at least one server failed to start. Please check the logs for more detail')

# nodeType is 'datanode' or 'accessor'
def stopNodes(nodeType):
    for dnode in clusterDef.processesOnThisHost(nodeType):
        stopServer(dnode)


def stopClusterLocal():

    for dnode in clusterDef.datanodesOnThisHost():
        stopServer(dnode)

    # probably is only going to be one
    for locator in clusterDef.locatorsOnThisHost():
        stopLocator(locator)


# calls gfsh shutdown but does not stop locators
def stopCluster():
    GEMFIRE = None
    JAVA = None
    processList = clusterDef.locatorsOnThisHost()
    if len(processList) > 0:
        GEMFIRE = clusterDef.locatorProperty(processList[0],'gemfire')
        JAVA_HOME = clusterDef.locatorProperty(processList[0],'java-home')
    else:
        processList = clusterDef.datanodesOnThisHost()
        if len(processList) > 0:
            GEMFIRE = clusterDef.locatorProperty(processList[0],'gemfire')
            JAVA_HOME = clusterDef.locatorProperty(processList[0],'java-home')
        else:
            sys.exit('no cluster processes are on this host - unable to ascertain gfsh setup information')

    os.environ['GEMFIRE'] = GEMFIRE
    os.environ['JAVA_HOME'] = JAVA_HOME

    # pick any locator and connect to it
    success = False
    for hkey in clusterDef.clusterDef['hosts']:
        host = clusterDef.clusterDef['hosts'][hkey]
        for pkey in host['processes']:
            process = host['processes'][pkey]
            if process['type'] == 'locator':
                if not success:
                    bindAddress = clusterDef.locatorProperty(pkey,'bind-address', host = hkey, notFoundOK = True)
                    if bindAddress is None:
                        bindAddress = '127.0.0.1'

                    port = clusterDef.locatorProperty(pkey,'port', host = hkey)
                    GEMFIRE = clusterDef.locatorProperty(pkey,'gemfire', host = hkey)
                    rc = subprocess.call([os.path.join(GEMFIRE,'bin',gfsh_script)
                        , "-e", "connect --locator={0}[{1}]".format(bindAddress,port)
                        ,"-e", "shutdown"])
                    if rc == 0:
                        success = True

    if success == False:
        sys.exit('could not shut down cluster')


def printUsage():
    print('Usage:')
    print('   cluster.py  [--cluster-def=path/to/clusterdef.json] start <process-name>')
    print('   cluster.py  [--cluster-def=path/to/clusterdef.json] start datanodes')
    print('   cluster.py  [--cluster-def=path/to/clusterdef.json] start accessors')
    print('   cluster.py  [--cluster-def=path/to/clusterdef.json] stop <process-name>')
    print('   cluster.py  [--cluster-def=path/to/clusterdef.json] stop accessors')
    print('   cluster.py  [--cluster-def=path/to/clusterdef.json] stop datanodes')
    print('   cluster.py  [--cluster-def=path/to/clusterdef.json] status <process-name>')
    print()
    print('   cluster.py [--cluster-def=path/to/clusterdef.json] shutdown')
    print('   cluster.py [--cluster-def=path/to/clusterdef.json] start')
    print('   cluster.py [--cluster-def=path/to/clusterdef.json] stop')
    print('Notes:')
    print('* all commands are idempotent')


if __name__ == '__main__':
    if len(sys.argv) == 1:
        printUsage()
        sys.exit(0)

    nextIndex = 1
    clusterDefFile = None

    if platform.system() == 'Windows':
        gfsh_script = 'gfsh.bat'
    else:
        gfsh_script = 'gfsh'

    #now process -- args
    while nextIndex < len(sys.argv):
        if sys.argv[nextIndex].startswith('--'):
            if sys.argv[nextIndex].startswith('--cluster-def='):
                clusterDefFile = sys.argv[nextIndex][len('--cluster-def='):]
            else:
                sys.exit('{0} is not a recognized option'.format(sys.argv[nextIndex]))
            nextIndex += 1
        else:
            break

    if clusterDefFile is None:
        here = os.path.dirname(sys.argv[0])
        clusterDefFile = os.path.join(here, 'cluster.json')

    if not os.path.isfile(clusterDefFile):
        sys.exit('could not find cluster definition file: ' + clusterDefFile)

    clusterDef = clusterdef.ClusterDef(clusterDefFile)

    if nextIndex >= len(sys.argv):
        sys.exit('invalid input, please provide a command')

    cmd = sys.argv[nextIndex]
    nextIndex += 1

    if len(sys.argv) == nextIndex:
        if cmd == 'start':
            startClusterLocal()
        elif cmd == 'shutdown':
            stopCluster()
        elif cmd == 'stop':
            stopClusterLocal()
        else:
            sys.exit('unknown command: ' + cmd)
    else:
        obj = sys.argv[nextIndex]
        nextIndex += 1

        if obj == 'datanodes':
            if cmd == 'start':
                startNodes('datanode')
            elif cmd == 'stop':
                stopNodes('datanode')
            else:
                sys.exit(cmd + ' is an unkown operation for datanodes')

        elif obj == 'accessors':
            if cmd == 'start':
                startNodes('accessor')
            elif cmd == 'stop':
                stopNodes('accessor')
            else:
                sys.exit(cmd + ' is an unkown operation for accessors')

        elif clusterDef.isLocatorOnThisHost(obj):
            if cmd == 'start':
                startLocator(obj)
            elif cmd == 'stop':
                stopLocator(obj)
            elif cmd == 'status':
                statusLocator(obj)
            else:
                sys.exit(cmd + ' is an unkown operation for locators')

        elif clusterDef.isDatanodeOnThisHost(obj):
            if cmd == 'start':
                startServer(obj)
            elif cmd == 'stop':
                stopServer(obj)
            elif cmd == 'status':
                statusServer(obj)
            else:
                sys.exit(cmd + ' is an unkown operation for datanodes')

        else:
            sys.exit(obj + ' is not defined for this host or is not a known process type')
