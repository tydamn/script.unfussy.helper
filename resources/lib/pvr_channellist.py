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

# FIX: Jedna interná parse funkcia namiesto duplikovanej logiky na 3 miestach.
# Kodi vracia EPG časy v UTC — konvertujeme na lokálny čas cez getUtcOffset()
# z helper.py. Funguje správne aj v zime (CET = +1h) aj v lete (CEST = +2h).
def _parseRawEPG(value):
    """
    Interná funkcia — parsuje EPG čas z Kodi (UTC) a vracia datetime
    v lokálnom čase. Vracia None ak parsovanie zlyhá.
    """
    if not value:
        return None

    value = str(value).strip()
    utc_offset = getUtcOffset()

    # Kodi niekedy vráti Unix timestamp v sekundách
    if value.isdigit():
        try:
            return datetime.fromtimestamp(int(value)) + utc_offset
        except Exception:
            return None

    # Kodi niekedy vráti "YYYY-MM-DD HH:MM:SS" alebo "YYYY-MM-DDTHH:MM:SS"
    match = re.search(r'(\d{4})[-.](\d{2})[-.](\d{2})[ T](\d{2}):(\d{2})', value)
    if match:
        try:
            return datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
                int(match.group(5))
            ) + utc_offset
        except Exception:
            pass

    return None


def formatEPGTime(value):
    dt = _parseRawEPG(value)
    if dt:
        return dt.strftime('%H:%M')
    # Fallback — vytiahni HH:MM priamo z reťazca ak parsovanie zlyhalo
    m = re.search(r'(\d{2}):(\d{2})', str(value))
    return m.group(0) if m else ''


def formatEPGDate(value):
    dt = _parseRawEPG(value)
    if dt:
        return dt.strftime('%Y-%m-%d')
    # Fallback — vytiahni dátum priamo z reťazca ak parsovanie zlyhalo
    m = re.search(r'(\d{4}-\d{2}-\d{2})', str(value))
    return m.group(0) if m else ''


def parseEPGDateTime(value):
    return _parseRawEPG(value)


#######################################################################################

class PVRChannelList:

    def __init__(self):
        # FIX: locale.getdefaultlocale() je deprecated od Python 3.11
        # Prázdny reťazec '' = system default, čo je ekvivalent pôvodného správania
        try:
            locale.setlocale(locale.LC_ALL, '')
        except Exception:
            log("ERROR setting locale")

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

        # FIX: Window(10000) je globálne Home okno — property je dostupná odkiaľkoľvek.
        # Window(10700) necháme pre PVR okno kde je tiež potrebná.
        # getCurrentWindowId() bol zbytočný tretí zápis rovnakej hodnoty.
        xbmcgui.Window(10000).setProperty('channel_ids', channel_ids_json)
        xbmcgui.Window(10700).setProperty('channel_ids', channel_ids_json)

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

        # FIX: datetime.now() presunutý mimo slučky — volať raz, nie pri každej relácii
        now_dt = datetime.now()
        limit_dt = now_dt + timedelta(hours=24)

        for bc in broadcasts:
            # Ak relácia už skončila podľa Kodi, ignorujeme ju
            if bc.get('wasactive') is True:
                continue

            raw_start = bc.get('starttime', '')
            raw_end = bc.get('endtime', '')

            # Zobrazujeme iba aktuálnu reláciu a relácie, ktoré začnú do 24 hodín.
            # Keď čas nevieme prečítať, reláciu radšej ponecháme, aby sa omylom nestratila.
            start_dt = parseEPGDateTime(raw_start)
            if start_dt and start_dt > limit_dt:
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
            bc_beautified['date'] = formatEPGDate(raw_start)
            bc_beautified['starttime'] = formatEPGTime(raw_start)
            bc_beautified['endtime'] = formatEPGTime(raw_end)

            broadcasts_beautified.append(bc_beautified)

        return broadcasts_beautified
