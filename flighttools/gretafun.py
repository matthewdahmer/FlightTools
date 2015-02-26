
import json
import pickle
import numpy as np
import re
import subprocess as sp
import sqlite3
#import json
import cPickle as pickle

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


# def getTDBLimits(telem):
#     """ Retrieve the TDB limits from the telem object

#     Returns an empty dict object if there are no limits specified in the
#     database
#     """

#     tdblimits = {}

#     try:
#         # Get the TDB default set num, this is the only limit set that is
#         # modified.
#         tdbdefault = telem.tdb.limit_default_set_num
#         limits = telem.tdb.Tlmt

#         if limits:

#             if isinstance(telem.tdb.Tlmt['LIMIT_SET_NUM'], np.ndarray):
#                 # There is more than one limit set, use the default set.
#                 mask = telem.tdb.Tlmt['LIMIT_SET_NUM'] == tdbdefault
#                 limits = telem.tdb.Tlmt[mask]

#             tdblimits['warning_low'] = limits['WARNING_LOW']
#             tdblimits['caution_low'] = limits['CAUTION_LOW']
#             tdblimits['caution_high'] = limits['CAUTION_HIGH']
#             tdblimits['warning_high'] = limits['WARNING_HIGH']

#     except AttributeError as e:
#         print('%s Attribute Error: %S'%(telem.MSID, str(e)))
#         tdblimits = {}

#     except KeyError:
#         print('%s does not have limits in Engineering Archive TDB'
#                %telem.MSID)
#         tdblimits = {}

#     return tdblimits

def isnotnan(arg):
   try:
       np.isnan(arg)
   except: # Need to use blanket except, NotImplementedError won't catch
       return True
   return False


def getTDBLimits(telem, dbver='p012'):
    """ Retrieve the TDB limits from a json version of the MS Access database.

    Returns an empty dict object if there are no limits specified in the
    database
    """

    def assign_sets(dbsets):
        """ Copy over only the limit/expst sets, other stuff is not copied.

        This also adds a list of set numbers.
        """
        limits = {'setkeys':[]}
        for setnum in dbsets.keys():
            setnumint = int(setnum) - 1
            limits.update({setnumint:dbsets[setnum]})
            limits['setkeys'].append(setnumint)
        return limits

    def get_tdb(dbver):
        # tdbs = json.load(open('/home/mdahmer/AXAFAUTO/G_LIMMON_Archive/tdb_all.json','r'))
        tdbs = pickle.load(open('/home/mdahmer/AXAFAUTO/G_LIMMON_Archive/tdb_all.pkl','r'))
        return tdbs[dbver.lower()]

    try:
        # telem is only used to pass the msid name, and is used for backwards compatibility only.
        msid = telem.msid.lower()
        tdb = get_tdb(dbver)

        limits = assign_sets(tdb[msid]['limit'])
        limits['type'] = 'limit'

        if isnotnan(tdb[msid]['limit_default_set_num']):
            limits['default'] = tdb[msid]['limit_default_set_num'] - 1
        else:
            limits['default'] = 0

        # Add limit switch info if present
        if isnotnan(tdb[msid]['limit_switch_msid']):
            limits['mlimsw'] = tdb[msid]['limit_switch_msid']

        # Fill in switchstate info if present
        for setkey in limits['setkeys']:
            if 'state_code' in limits[setkey].keys():
                limits[setkey]['switchstate'] = limits[setkey]['state_code']
                _ = limits[setkey].pop('state_code')

        # For now, only the default limit set is returned, this will help with backwards compatibility.
        # Future versions, rewritten for web applications will not have this limitation.
        tdblimits = limits[limits['default']]

    except KeyError:
        print('{} does not have limits in the TDB'.format(telem.MSID))
        tdblimits = {}

    return tdblimits




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

    # Set the safetylimits dict here. An empty dict is returned if there are no
    # limits specified. This is intended and relied upon later.
    safetylimits = getTDBLimits(telem)

    # Make it simpler to index into the glimmon dict, where msids names are all
    # upper case.
    MSID = telem.msid.upper()

    # Read the GLIMMON data
    try:
        db = sqlite3.connect('/home/mdahmer/AXAFAUTO/G_LIMMON_Archive/glimmondb.sqlite3')
        cursor = db.cursor()
        cursor.execute('''SELECT a.msid, a.setkey, a.default_set, a.warning_low, 
                          a.caution_low, a.caution_high, a.warning_high FROM limits AS a 
                          WHERE a.active_set=1 AND a.setkey = a.default_set AND a.msid = ?
                          AND a.modversion = (SELECT MAX(b.modversion) FROM limits AS b
                          WHERE a.msid = b.msid and a.setkey = b.setkey)''', [MSID.lower(),])
        lims = cursor.fetchone()
        glimits = {'warning_low':lims[3], 'caution_low':lims[4], 'caution_high':lims[5], 
                   'warning_high':lims[6]}
    except:
        print('{} not in G_LIMMON Database'.format(MSID))
        glimits = {}

    # glimmon = readGLIMMON()

    # # Generate GLIMMON tests for use later
    # msid_has_glimmon_limits = False # Initialize to False
    # msid_in_glimmon = MSID in glimmon.keys()
    # if msid_in_glimmon:
    #     if glimmon[MSID].has_key(0):
    #         if glimmon[MSID][0].has_key('type'):
    #             msid_has_glimmon_limits = glimmon[MSID][0]['type'] == 'limit'

    # If there are no limits in the TDB but there are in GLIMMON, use the
    # GLIMMON limits
    if not safetylimits and glimits:
        safetylimits = glimits

    # If there are limits in both GLIMMON and the TDB use the set that
    # is most permissive.
    if safetylimits and glimits:

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

    envfile is a file with all required GRETA environment variables. This is
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
