
import re
from numpy import double

from Chandra.Time import DateTime

def read_eclipse_file(filename='/home/mission/Backstop/History/ECLIPSE.txt'):

    def parse_line(line):
        words = line.split()
        starttime = words[0][4:] + ':' + words[0][:3] + ':' + words[1]
        stoptime = words[2][4:] + ':' + words[2][:3] + ':' + words[3]

        returndict = {'Start Time':starttime,
                      'Stop Time':stoptime,
                      'Duration':words[4],
                      'Current Condition': words[5],
                      'Obstruction':words[6],
                      'durationsec':double(words[4]),
                      'startsec':DateTime(starttime).secs,
                      'stopsec':DateTime(stoptime).secs}

        if len(words) == 9:
            returndict.update({'Entry Timer':words[7],
                               'timersec':double(words[7]),
                               'Type':words[8]})

        return returndict


    with open(filename, 'rb') as fid:
        datalines = fid.readlines()

    # The first line includes the year and day the file was generated
    #
    # Note: This entry may be manually created and could be a source of error
    # if read incorrectly.
    words = datalines.pop(0).split()
    eclipse = {'epoch':dict(zip(('year','day'),
                                (words[-2][:4],words[-2][5:])))}

    # Remove spacing lines
    line = datalines.pop(0)
    while len(line.strip()) < 5:
        line = datalines.pop(0)

    headers = re.split("\s{2,5}",line.strip())

    # Truncate the Start Time, Stop Time and Duration header names
    headers[0] = headers[0][:10]
    headers[1] = headers[1][:9]
    headers[2] = headers[2][:8]

    # Remove the dashed lines separating the header from the eclipse data entries
    line = datalines.pop(0)

    # This is the eclipse number; it is used to index all eclipses in the
    # file. It has no other significance.
    n = -1
    eclipse.update({'eclipse_nums':[]})

    while len(datalines) > 0:
        line = datalines.pop(0).strip()

        # All eclipse entries start wth 9 "words"
        if len(line.split()) == 9:

            # increment the eclipse number and create a placeholder dict
            n = n + 1
            eclipse['eclipse_nums'].append(n)
            eclipse.update({n:{}})

            # Add the entrance penumbra data, there will always be an entrance
            # penumbra
            eclipsedata = parse_line(line)
            eclipse[n].update({'entrancepenumbra':eclipsedata})

            # If this is a full eclipse, then there will also be umbra and
            # exit penumbra phases. These always have 7 "words"
            if len(datalines[0].split()) == 7:

                line = datalines.pop(0)
                eclipsedata = parse_line(line)
                eclipse[n].update({'umbra':eclipsedata})

                line = datalines.pop(0)
                eclipsedata = parse_line(line)
                eclipse[n].update({'exitpenumbra':eclipsedata})

    return eclipse





