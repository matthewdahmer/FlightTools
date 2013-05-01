
import json
import pickle
import numpy as np
import re
import subprocess as sp

import Ska.engarchive.fetch_eng as fetch_eng
from Chandra.Time import DateTime

# Parsing functions placed in separate file to improve readability
from greta_parse import *


def getGLIMMONLimits(MSID, glimmon=None):
    """ Get the GLIMMON limits from the glimmon datastructure
    """
    if not glimmon:
        glimmon = readGLIMMON()

    glimits = {}

    if MSID in glimmon.keys():
        if glimmon[MSID].has_key('default'):
            gdefault = glimmon[MSID]['default']
        else:
            gdefault = 0

        glimits['warning_low'] = glimmon[MSID][gdefault]['warning_low']
        glimits['caution_low'] = glimmon[MSID][gdefault]['caution_low']
        glimits['caution_high'] = glimmon[MSID][gdefault]['caution_high']
        glimits['warning_high'] = glimmon[MSID][gdefault]['warning_high']

    return glimits


def getSafetyLimits(telem):
    """ Update the current database limits

    The database limits are replaced with the G_LIMMON limits if the
    G_LIMMON limits are more permissive (which would only be the case if
    the database limits are outdated). Only those individual limits that
    are more permissive are replaced, not the entire set.

    For MSIDs that have numeric limits, update any database limit if the
    corresponding GLIMMON limit is outside of the database limit.

    The updated limit set is returned in a separate dictionary, regardless
    of whether or not any updates were made.

    This is meant to generate a pseudo-P010 database limit set. This assumes
    that the GLIMMON limit set reflects the new database limits. However often
    GLIMMON limits will be set within newly adjusted database limits, so the
    values returned by this routine may be more conservative than necessary.

    glimmon is a dictionary of limits and expected states read in from a
    GLIMMON file, for all msids in GLIMMON.

    telem is a single telemetry data class instance generated using the
    Ska.engarchive.fetch_eng.Msid function. (single MSID)

    In the future this function can add the ability to traverse all limit sets
    for a single MSID

    #FIXME PRIORITY LOW Add the ability to update multiple limit sets for a
    a single msid#
    """

    def getTDBLimits(telem):
        """ Retrieve the TDB limits from the telem object

        Returns an empty dict object if there are no limits specified in the
        database
        """

        safetylimits = {}

        try:
            # Get the TDB default set num, this is the only limit set that is
            # modified.
            tdbdefault = telem.tdb.limit_default_set_num

            limits = telem.tdb.Tlmt

            if limits:

                if len(telem.tdb.Tlmt) == 1:
                    #In this case there is only one limit set
                    safetylimits['warning_low'] = limits['WARNING_LOW']
                    safetylimits['caution_low'] = limits['CAUTION_LOW']
                    safetylimits['caution_high'] = limits['CAUTION_HIGH']
                    safetylimits['warning_high'] = limits['WARNING_HIGH']

                else:
                    # Then assume there is more than one limit set and use the
                    # default set.
                    mask = telem.tdb.Tlmt['LIMIT_SET_NUM'].data == tdbdefault

                    safetylimits['warning_low'] = \
                                        limits['WARNING_LOW'].data[mask][0]
                    safetylimits['caution_low'] = \
                                        limits['CAUTION_LOW'].data[mask][0]
                    safetylimits['caution_high'] = \
                                        limits['CAUTION_HIGH'].data[mask][0]
                    safetylimits['warning_high'] = \
                                        limits['WARNING_HIGH'].data[mask][0]
        except AttributeError as e:
            print('%s Attribute Error: %S'%(telem.MSID, str(e)))
            safetylimits = {}

        except KeyError:
            print('%s does not have limits in Engineering Archive TDB'
                   %telem.MSID)
            safetylimits = {}

        return safetylimits

    # Set the safetylimits dict here. An empty dict is returned if there are no
    # limits specified. This is intended and relied upon later.
    safetylimits = getTDBLimits(telem)

    # Make it simpler to index into the glimmon dict, where msids names are all
    # upper case.
    MSID = telem.msid.upper()

    # Read the GLIMMON file
    glimmon = readGLIMMON()

    # Generate GLIMMON tests for use later
    msid_has_glimmon_limits = False # Initialize to False
    msid_in_glimmon = MSID in glimmon.keys()
    if msid_in_glimmon:
        if glimmon[MSID].has_key(0):
            if glimmon[MSID][0].has_key('type'):
                msid_has_glimmon_limits = glimmon[MSID][0]['type'] == 'limit'

    # If there are no limits in the TDB but there are in GLIMMON, use the
    # GLIMMON limits
    if not safetylimits and  msid_in_glimmon and msid_has_glimmon_limits:
        safetylimits = getGLIMMONLimits(MSID, glimmon)

    # If there are limits in both GLIMMON and the TDB use the set that
    # is most permissive.
    if safetylimits and  msid_in_glimmon and msid_has_glimmon_limits:
        glimits = getGLIMMONLimits(MSID, glimmon)

        if glimits['warning_low'] < safetylimits['warning_low']:
            safetylimits['warning_low'] = glimits['warning_low']
            print('Updated warning low safety limit for %s'%telem.msid)

        if glimits['caution_low'] < safetylimits['caution_low']:
            safetylimits['caution_low'] = glimits['caution_low']
            print('Updated caution low safety limit for %s'%telem.msid)

        if glimits['warning_high'] > safetylimits['warning_high']:
            safetylimits['warning_high'] = glimits['warning_high']
            print('Updated warning high safety limit for %s'%telem.msid)

        if glimits['caution_high'] > safetylimits['caution_high']:
            safetylimits['caution_high'] = glimits['caution_high']
            print('Updated caution high safety limit for %s'%telem.msid)

    return safetylimits


def readxlist(filename, data=None):

    # there's probably a faster way to do this with recarrays

    fid = file(filename,'r')
    headers = fid.readline().split()

    if not data:
        data = {}

    for header in headers:
        data[header.lower()] = []

    for line in fid:
        vals = line.split()
        t = vals.pop(0)
        time = '%s:%s:%s:%s:%s.%s'%(t[:4], t[4:7], t[8:10], t[10:12], t[12:14],
                                    t[14:])
        data['time'].append(DateTime(time).secs)

        for header in headers[1:]: # Already assigned time
            value = vals.pop(0)
            if value[0].isdigit():
                data[header.lower()].append(float(value))
            else:
                data[header.lower()].append(value)
            stale = vals.pop(0)

    fid.close()
    return data


def readxlist2(filename):
    def RepresentsInt(s):
        if '.' in s:
            return False
        elif 'e' in s:
            return False
        else:
            return True

    def Update(val):
        if val == 'S':
            return False
        else:
            return True

    def RepresentsNumber(s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    with open(filename, 'r') as fid:
        headers = fid.readline().split()
        testline = fid.readline().split()

    #fid = file(filename,'r')
    #headers = fid.readline().split()
    #testline = fid.readline().split()
    #fid.close()

    names = ['time']
    update_names = []
    for header in headers[1:]:
        header = header.lower()
        names.append(header)
        update_names.append(header + '_update')

    conv = dict(zip(update_names, [Update] * len(update_names)))

    dt = [(names[0], 'float64')]
    k = 0
    for item in testline[1:(len(testline) + 1):2]:
        k = k + 1
        name = headers[k].lower()

        if RepresentsNumber(item):
            if RepresentsInt(item):
                dt.append((name, [('data', 'int64'), ('update', 'bool')]))
            else:
                dt.append((name, [('data', 'float64'), ('update', 'bool')]))
        else:
            dt.append((name, [('data', 'S8'), ('update', 'bool')]))

    data = np.genfromtxt(filename, dtype=dt, names=names, converters=conv,
                         skip_header=1)

    return data


def runDecFile(time1, time2, outfile, decfile, envfile='env.txt'):
    """ Run an XList Query using GRETA

    Using a prewritten dec file, generate an XList query from the GRETA VCDU
    files.

    time1 and time2 are time strings compatible as inputs to the DateTime
    function.

    outfile is where the xlist data are written to.

    decfile is the prewritten GRETA dec file (with full path).

    envfile is a file with all required GRETA environment variables. This

    necessary since some of these variables are overwritten when enabling the
    Ska environment.

    NOTE: This allows one to run GRETA from within the Ska environment which
          is not an officially sanctioned use of GRETA.

    """

    envvar = readENV('env.txt')

    time1 = DateTime(time1).greta
    time2 = DateTime(time2).greta

    decomcommand = ('decom98 -d ' + decfile + ' -m 3 -f ztlm_autoselect@' +
                    str(time1) + '-' + str(time2) + ' -a ' + outfile)
    print('running:\n  %s\n'%decomcommand)

    d = sp.call(decomcommand, shell=True, env=envvar)


def readENV(envfile):
    with open(envfile, 'r') as fid:
        env = fid.readlines()

    envvar = {}
    for line in env:
        pair = line.strip().split('=',1)
        envvar[pair[0]]=pair[1]
    return envvar
