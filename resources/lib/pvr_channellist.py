#!/usr/bin/python
import locale
import re
from datetime import datetime, timedelta
from resources.lib.helper import *

broadcast_properties_short = [
    'title',
    'plot',
    'starttime',
    'endtime',
    'runtime',
    'progress',
    'progresspercentage',
    'episodename',
    'episodenum',
    'genre',
    'year',
    'hastimer',
    'isactive',
    'wasactive'
]

#######################################################################################

def formatEPGTime(value):
    if not value:
        return ''

    value = str(value).strip()

    # Ak Kodi vr�ti timestamp (sekundy)
    if value.isdigit():
        try:
            dt = datetime.fromtimestamp(int(value))
            # Pre istotu posunieme aj timestamp, ak by bol v UTC
            return (dt + timedelta(hours=2)).strftime('%H:%M')
        except Exception:
            pass

    # Ak Kodi vr�ti text "YYYY-MM-DD HH:MM:SS" alebo "YYYY-MM-DDTHH:MM:SS"
    # Vytiahneme ��sla pomocou regul�rneho v�razu
    match = re.search(r'(\d{4})[-.](\d{2})[-.](\d{2})[ T](\d{2}):(\d{2})', value)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5))

            # Vytvor�me datetime objekt a natvrdo prir�tame 2 hodiny
            dt = datetime(year, month, day, hour, minute)
            dt_corrected = dt + timedelta(hours=2)

            return dt_corrected.strftime('%H:%M')
        except Exception:
            # Ak by �oko�vek zlyhalo, vr�time p�vodn� v�rez hod�n a min�t
            time_match = re.search(r'(\d{2}):(\d{2})', value)
            if time_match:
                return time_match.group(0)

    return ''

def formatEPGDate(value):
    if not value:
        return ''

    value = str(value).strip()

    # Vytiahneme d�tum a tie� ho skorigujeme, ak by posun o 2 hodiny preklopil polnoc
    match = re.search(r'(\d{4})[-.](\d{2})[-.](\d{2})[ T](\d{2}):(\d{2})', value)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5))

            dt = datetime(year, month, day, hour, minute)
            dt_corrected = dt + timedelta(hours=2)

            return dt_corrected.strftime('%Y-%m-%d')
        except Exception:
            pass

    # Fallback ak hore nie�o zlyhalo
    match_simple = re.search(r'(\d{4}-\d{2}-\d{2})', value)
    if match_simple:
        return match_simple.group(0)

    return ''


def parseEPGDateTime(value):
    if not value:
        return None

    value = str(value).strip()

    # Ak Kodi vrati timestamp v sekundach.
    if value.isdigit():
        try:
            return datetime.fromtimestamp(int(value)) + timedelta(hours=2)
        except Exception:
            pass

    # Ak Kodi vrati text "YYYY-MM-DD HH:MM:SS" alebo "YYYY-MM-DDTHH:MM:SS".
    match = re.search(r'(\d{4})[-.](\d{2})[-.](\d{2})[ T](\d{2}):(\d{2})', value)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5))

            return datetime(year, month, day, hour, minute) + timedelta(hours=2)
        except Exception:
            pass

    return None

#######################################################################################

class PVRChannelList:

    def __init__(self):
        def_loc = ''
        try:
            def_loc = locale.getdefaultlocale()[0]
            locale.setlocale(locale.LC_ALL, def_loc)
        except Exception:
            log("ERROR setting locale: %s" % def_loc)

    def setChannelIds(self):
        query = json_call(
            'PVR.GetChannels',
            properties=['channelnumber'],
            params={'channelgroupid': 'alltv'}
        )

        channels = []
        try:
            channels = query['result']['channels']
        except Exception:
            return None

        channel_ids = {}
        for channel in channels:
            channel_ids[channel['channelnumber']] = channel['channelid']

        channel_ids_json = json.dumps(channel_ids)

        xbmcgui.Window(10700).setProperty('channel_ids', channel_ids_json)
        xbmcgui.Window(10000).setProperty('channel_ids', channel_ids_json)
        xbmcgui.Window(xbmcgui.getCurrentWindowId()).setProperty('channel_ids', channel_ids_json)

    def fetchBroadcasts(self, channel_id):
        query = json_call(
            'PVR.GetBroadcasts',
            properties=broadcast_properties_short,
            params={'channelid': channel_id}
        )

        broadcasts = []
        try:
            broadcasts = query['result']['broadcasts']
        except Exception:
            return []

        return self.beautifyBroadcasts(channel_id, broadcasts)

    def beautifyBroadcasts(self, channel_id, broadcasts):
        broadcasts_beautified = []

        for bc in broadcasts:
            # Ak rel�cia u� skon�ila pod�a Kodi, ignorujeme ju
            if bc.get('wasactive') is True:
                continue

            raw_start = bc.get('starttime', '')
            raw_end = bc.get('endtime', '')

            # Zobrazujeme iba aktualnu relaciu a relacie, ktore zacnu do 24 hodin.
            # Ked cas nevieme precitat, relaciu radsej ponechame, aby sa omylom nestratila.
            start_dt = parseEPGDateTime(raw_start)
            if start_dt:
                now_dt = datetime.now()
                limit_dt = now_dt + timedelta(hours=24)
                if start_dt > limit_dt:
                    continue

            bc_beautified = {}
            bc_beautified['broadcastid'] = bc.get('broadcastid', '')
            bc_beautified['channelid'] = channel_id
            bc_beautified['id'] = bc.get('broadcastid', '')
            bc_beautified['channel_id'] = channel_id
            bc_beautified['title'] = bc.get('title', '')
            bc_beautified['episodename'] = bc.get('episodename', '')
            bc_beautified['runtime'] = bc.get('runtime', '')

            bc_beautified['plot'] = bc.get('plot', '')
            bc_beautified['genre'] = bc.get('genre', '')
            bc_beautified['year'] = bc.get('year', '')
            bc_beautified['progress'] = bc.get('progress', '')
            bc_beautified['progresspercentage'] = bc.get('progresspercentage', '')

            # Pou�ijeme nov� stabiln� form�tovanie
            bc_beautified['date'] = formatEPGDate(raw_start)
            bc_beautified['starttime'] = formatEPGTime(raw_start)
            bc_beautified['endtime'] = formatEPGTime(raw_end)

            broadcasts_beautified.append(bc_beautified)

        return broadcasts_beautified
