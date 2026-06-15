#!/usr/bin/python
import re
from datetime import datetime, timedelta
import locale
from resources.lib.helper import *

broadcast_properties = [
    'title',
    'plot',
    'starttime',
    'endtime',
    'runtime',
    'episodename',
    'episodenum',
    'genre',
    'year',
    'hastimer',
    'isactive',
    'wasactive',

    # Image fields for custom info dialog.
    # Native Kodi DialogPVRInfo can read ListItem.EPGEventIcon directly,
    # but our custom WindowXMLDialog only sees properties we pass into it.
    'thumbnail'
]

#######################################################################################

# FIX: Hardcoded +2h nahradený getUtcOffset() z helper.py
# Funguje správne aj v zime (CET = +1h) aj v lete (CEST = +2h).
def safeParseAndCorrectTime(value):
    if not value:
        return None

    value = str(value).strip()
    utc_offset = getUtcOffset()

    if value.isdigit():
        try:
            return datetime.fromtimestamp(int(value)) + utc_offset
        except Exception:
            pass

    match = re.search(r'(\d{4})[-.](\d{2})[-.](\d{2})[ T](\d{2}):(\d{2})', value)
    if match:
        try:
            dt = datetime(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
                int(match.group(5))
            )
            return dt + utc_offset
        except Exception:
            pass

    return None


def formatTimeDelta(delta):
    try:
        total_seconds = int(delta.total_seconds())
    except Exception:
        return ''

    if total_seconds < 0:
        total_seconds = 0

    # Zaokruhli nahor na minuty, aby 59 sekund neukazovalo 0 min.
    total_minutes = int((total_seconds + 59) / 60)

    if total_minutes <= 0:
        return 'menej ako 1 min'

    days = total_minutes // 1440
    remainder = total_minutes % 1440
    hours = remainder // 60
    minutes = remainder % 60

    parts = []
    if days:
        parts.append('%d d' % days)
    if hours:
        parts.append('%d h' % hours)
    if minutes or not parts:
        parts.append('%d min' % minutes)

    return ' '.join(parts)

#######################################################################################

class PVRRunningAt:

    def __init__(self):
        # FIX: locale.getdefaultlocale() je deprecated od Python 3.11
        try:
            locale.setlocale(locale.LC_ALL, '')
        except Exception:
            log("ERROR setting locale")

    def getBroadcastAt(self, starttime, channelid):
        broadcasts = self.getBroadcasts(channelid)
        if not broadcasts:
            return None

        interval = self.getStartTimeInterval(starttime)
        starttime_dt, start_interval, stop_interval = interval
        if starttime_dt is None:
            return None

        bc = 0
        fallback = -1

        for broadcast in broadcasts:
            start_bc = safeParseAndCorrectTime(broadcast.get('starttime', ''))
            end_bc = safeParseAndCorrectTime(broadcast.get('endtime', ''))

            if not start_bc or not end_bc:
                continue

            if start_bc > start_interval and start_bc < stop_interval and end_bc > stop_interval:
                return broadcast

            if start_bc < starttime_dt and end_bc > starttime_dt:
                fallback = bc

            bc += 1

        if fallback > -1:
            return broadcasts[fallback]

        return None

    def showInfo(self, broadcast_id, channel_id, xml_file, xml_filepath):
        bc_id = [
            {
                'broadcastid': int(broadcast_id),
                'channelid': int(channel_id)
            }
        ]

        broadcasts = self.getBroadcastsById(bc_id)

        if len(broadcasts) == 0:
            log("error fetching broadcast details")
            return

        broadcast = broadcasts[0]

        # log('SHOWINFO BROADCAST FULL DATA: %s' % repr(broadcast), xbmc.LOGINFO, force=True)

        win = xbmcgui.WindowXMLDialog(xml_file, xml_filepath)

        win.setProperty('broadcastid', str(broadcast.get('broadcastid', '')))
        win.setProperty('title', broadcast.get('title', ''))
        win.setProperty('plot', broadcast.get('plot', ''))
        win.setProperty('plotoutline', broadcast.get('plotoutline', ''))
        win.setProperty('cast', broadcast.get('cast', ''))
        win.setProperty('genre', ', '.join(broadcast.get('genre', [])))
        win.setProperty('director', broadcast.get('director', ''))
        win.setProperty('episodename', broadcast.get('episodename', ''))
        win.setProperty('episodenum', str(broadcast.get('episodenum', '')))
        win.setProperty('episodepart', str(broadcast.get('episodepart', '')))

        # EPG image / event icon support.
        # PVR.GetBroadcastDetails returns the event image as "thumbnail" when available.
        # We expose the same value under multiple property names so XML can test/display it easily.
        epg_image = broadcast.get('thumbnail', '') or ''
        win.setProperty('thumbnail', epg_image)
        win.setProperty('epgeventicon', epg_image)
        win.setProperty('poster', epg_image)
        win.setProperty('artthumb', epg_image)
        win.setProperty('debug_broadcast_thumbnail', epg_image)

        win.setProperty('year', str(broadcast.get('year', '')))

        win.setProperty('date', broadcast.get('display_date', ''))
        win.setProperty('datelong', broadcast.get('display_datelong', ''))
        win.setProperty('starttime', broadcast.get('display_starttime', ''))
        win.setProperty('endtime', broadcast.get('display_endtime', ''))
        win.setProperty('runtime', str(broadcast.get('runtime', '')))
        win.setProperty('switchdate', broadcast.get('display_switchdate', ''))




        # Time info under poster:
        # - currently running broadcast: "Ostáva: ..."
        # - future broadcast: "Začne za: ..."
        # - past broadcast: hidden
        timing_label = ''
        timing_time = ''
        start_dt = safeParseAndCorrectTime(broadcast.get('starttime', ''))
        end_dt = safeParseAndCorrectTime(broadcast.get('endtime', ''))
        now_dt = datetime.now()

        if start_dt and end_dt:
            if start_dt <= now_dt < end_dt:
                timing_label = 'Končí o:'
                timing_time = formatTimeDelta(end_dt - now_dt)
            elif now_dt < start_dt:
                timing_label = 'Začína o:'
                timing_time = formatTimeDelta(start_dt - now_dt)

        win.setProperty('timinglabel', timing_label)
        win.setProperty('timingtime', timing_time)
        win.setProperty('timingtext', (timing_label + ' ' + timing_time).strip())

        # Nasledujúce relácie pod spodným separatorom.
        # Spoľahlivejšie berieme poradie z EPG podľa broadcastid, nie iba porovnanie času.
        for i in range(1, 9):
            win.setProperty('next%dstart' % i, '')
            win.setProperty('next%dend' % i, '')
            win.setProperty('next%dtime' % i, '')
            win.setProperty('next%dtitle' % i, '')
        win.setProperty('upcomingtext', '')

        try:
            upcoming = self.getUpcomingBroadcasts(
                channel_id,
                broadcast.get('broadcastid', ''),
                start_dt,
                end_dt,
                limit=8
            )

            upcoming_parts = []

            for idx, item in enumerate(upcoming, 1):
                start_txt = item.get('display_starttime', '')
                end_txt = item.get('display_endtime', '')
                title_txt = item.get('title', '')
                time_txt = start_txt

                if start_txt and end_txt:
                    time_txt = '%s - %s' % (start_txt, end_txt)

                win.setProperty('next%dstart' % idx, start_txt)
                win.setProperty('next%dend' % idx, end_txt)
                win.setProperty('next%dtime' % idx, time_txt)
                win.setProperty('next%dtitle' % idx, title_txt)

                if title_txt:
                    if start_txt:
                        upcoming_parts.append('[COLOR active]%s[/COLOR]  %s' % (start_txt, title_txt))
                    else:
                        upcoming_parts.append(title_txt)

            win.setProperty('upcomingtext', '   •   '.join(upcoming_parts))



        except Exception as e:
            log('ERROR: Nepodarilo sa nacitat nasledujuce relacie: %s' % e, xbmc.LOGERROR, force=True)

        channel = broadcast.get('channel') or {}
        win.setProperty('channelid', str(channel.get('channelid', '')))
        win.setProperty('channel', channel.get('channel', ''))
        win.setProperty('channelnumber', str(channel.get('channelnumber', '')))
        win.setProperty('channelicon', channel.get('icon', ''))

        win.doModal()
        del win

    def setTimer(self, bc_id):
        json_call(
            'PVR.AddTimer',
            params={'broadcastid': int(bc_id)}
        )

    #######################################################################################
    # private
    #######################################################################################

    def getBroadcasts(self, channelid):
        try:
            channelid_int = int(channelid)
        except Exception:
            channelid_int = channelid

        query = json_call(
            'PVR.GetBroadcasts',
            params={'channelid': channelid_int},
            properties=['title', 'plot', 'starttime', 'endtime', 'runtime', 'episodename', 'episodenum', 'genre', 'year', 'hastimer', 'isactive', 'wasactive']
        )

        try:
            broadcasts = query['result']['broadcasts']
        except Exception as e:
            log("ERROR getBroadcast: %s" % e, xbmc.LOGERROR, force=True)
            log("ERROR getBroadcast raw query: %s" % query, xbmc.LOGINFO, force=True)
            return None


        return broadcasts

    def _parseKodiDateTime(self, value):
        return safeParseAndCorrectTime(value)

    # FIX: Odstránený nepoužívaný parameter add_hours=2 — offset riadi getUtcOffset()
    def _formatRawTime(self, value):
        dt = safeParseAndCorrectTime(value)
        if dt:
            return dt.strftime('%H:%M')

        value = str(value).strip()
        if len(value) >= 16 and ':' in value:
            return value[11:16]
        return value

    def _formatRawDate(self, value):
        dt = safeParseAndCorrectTime(value)
        if dt:
            return dt.strftime('%d.%m')

        value = str(value).strip()
        try:
            return datetime.strptime(value[:10], '%Y-%m-%d').strftime('%d.%m')
        except Exception:
            return value[:10]

    def _formatRawDateLong(self, value):
        dt = safeParseAndCorrectTime(value)
        if dt:
            return self._formatKodiLocalizedDateLong(dt)

        value = str(value).strip()
        try:
            parsed_dt = datetime.strptime(value[:10], '%Y-%m-%d')
            return self._formatKodiLocalizedDateLong(parsed_dt)
        except Exception:
            return value[:10]

    def _formatKodiLocalizedDateLong(self, dt):
        try:
            days = {
                0: xbmc.getLocalizedString(11),
                1: xbmc.getLocalizedString(12),
                2: xbmc.getLocalizedString(13),
                3: xbmc.getLocalizedString(14),
                4: xbmc.getLocalizedString(15),
                5: xbmc.getLocalizedString(16),
                6: xbmc.getLocalizedString(17),
            }

            months = {
                1: xbmc.getLocalizedString(21),
                2: xbmc.getLocalizedString(22),
                3: xbmc.getLocalizedString(23),
                4: xbmc.getLocalizedString(24),
                5: xbmc.getLocalizedString(25),
                6: xbmc.getLocalizedString(26),
                7: xbmc.getLocalizedString(27),
                8: xbmc.getLocalizedString(28),
                9: xbmc.getLocalizedString(29),
                10: xbmc.getLocalizedString(30),
                11: xbmc.getLocalizedString(31),
                12: xbmc.getLocalizedString(32),
            }

            day_name = days.get(dt.weekday(), '')
            month_name = months.get(dt.month, '')

            return '%s %02d.%s' % (day_name, dt.day, month_name)

        except Exception:
            return dt.strftime('%a %d.%b')

    def getUpcomingBroadcasts(self, channel_id, current_broadcastid='', current_start_dt=None, current_end_dt=None, limit=8):
        broadcasts = self.getBroadcasts(channel_id)
        if not broadcasts:
                return []

        current_id = str(current_broadcastid or '')
        parsed_items = []

        for pos, item in enumerate(broadcasts):
            start_dt = safeParseAndCorrectTime(item.get('starttime', ''))
            end_dt = safeParseAndCorrectTime(item.get('endtime', ''))

            item_copy = dict(item)
            item_copy['_pos'] = pos
            item_copy['_start_dt'] = start_dt
            item_copy['_end_dt'] = end_dt

            if start_dt:
                item_copy['display_starttime'] = start_dt.strftime('%H:%M')
            else:
                item_copy['display_starttime'] = self._formatRawTime(item.get('starttime', ''))

            if end_dt:
                item_copy['display_endtime'] = end_dt.strftime('%H:%M')
            else:
                item_copy['display_endtime'] = self._formatRawTime(item.get('endtime', ''))

            parsed_items.append(item_copy)

        # 1) Najspoľahlivejšie: nájdeme aktuálnu reláciu podľa broadcastid a zoberieme položky za ňou.
        if current_id:
            for idx, item in enumerate(parsed_items):
                if str(item.get('broadcastid', '')) == current_id:
                    return parsed_items[idx + 1:idx + 1 + limit]

        # 2) Fallback: ak broadcastid v zozname nesedí, porovnaj čas.
        # Používame >= pri konci relácie, lebo ďalšia relácia často začína presne v čase konca aktuálnej.
        result = []
        after_dt = current_end_dt or current_start_dt

        if after_dt:
            for item in parsed_items:
                start_dt = item.get('_start_dt')
                if not start_dt:
                    continue
                if current_end_dt:
                    if start_dt >= current_end_dt:
                        result.append(item)
                elif current_start_dt:
                    if start_dt > current_start_dt:
                        result.append(item)
                if len(result) >= limit:
                    break

        # 3) Posledný fallback: zober najbližšie relácie, ktoré ešte nezačali / nie sú aktuálne aktívne.
        # Toto pomôže pri PVR addone, ktorý nevracia rovnaké broadcastid alebo má mierne iný časový formát.
        if not result:
            now_dt = datetime.now()
            for item in parsed_items:
                if item.get('isactive') is True:
                    continue
                start_dt = item.get('_start_dt')
                if start_dt and start_dt >= now_dt:
                    result.append(item)
                if len(result) >= limit:
                    break

        return result[:limit]

    def getBroadcastsById(self, broadcast_ids):
        broadcasts = []

        for bc in broadcast_ids:
            bc_id = bc['broadcastid']
            channel_id = bc['channelid']

            query = json_call(
                'PVR.GetBroadcastDetails',
                params={'broadcastid': bc_id},
                properties=broadcast_properties
            )

            try:
                broadcast = query['result']['broadcastdetails']

                if not broadcast.get('year') or broadcast.get('year') == 0:
                    plot = broadcast.get('plot', '')
                    match = re.search(r'\((\d{4})\)', plot)

                    if match:
                        try:
                            broadcast['year'] = int(match.group(1))
                        except Exception:
                            pass

                raw_starttime = broadcast.get('starttime', '')
                raw_endtime = broadcast.get('endtime', '')

                starttime_fixed = safeParseAndCorrectTime(raw_starttime)
                endtime_fixed = safeParseAndCorrectTime(raw_endtime)

                if starttime_fixed:
                    broadcast['display_date'] = starttime_fixed.strftime('%d.%m')
                    broadcast['display_datelong'] = self._formatKodiLocalizedDateLong(starttime_fixed)
                    broadcast['display_starttime'] = starttime_fixed.strftime('%H:%M')
                    broadcast['display_switchdate'] = starttime_fixed.strftime('%d.%m.%Y %H:%M')
                else:
                    broadcast['display_date'] = self._formatRawDate(raw_starttime)
                    broadcast['display_datelong'] = self._formatRawDateLong(raw_starttime)
                    broadcast['display_starttime'] = self._formatRawTime(raw_starttime)
                    broadcast['display_switchdate'] = raw_starttime

                if endtime_fixed:
                    broadcast['display_endtime'] = endtime_fixed.strftime('%H:%M')
                else:
                    broadcast['display_endtime'] = self._formatRawTime(raw_endtime)

                # Keep a debug log of the full broadcast details when debug logging is enabled.
                log('PVR.GetBroadcastDetails broadcastdetails: %s' % broadcast, xbmc.LOGDEBUG)

                broadcast['cast'] = self.beautifyCast(broadcast.get('cast', ''))
                broadcast['channel'] = self.getChannelDetails(channel_id) or {}

                broadcasts.append(broadcast)

            except Exception as e:
                xbmc.log('ERROR GetBroadcastDetails: %s' % e, xbmc.LOGERROR)

        return broadcasts

    def beautifyCast(self, cast):
        if not cast:
            return ''

        actors = cast.split(',')
        str_actors = ''

        for actor in actors:
            str_actors += '\n' + actor

        return str_actors

    def getChannelDetails(self, channel_id):
        channel = None

        query = json_call(
            'PVR.GetChannelDetails',
            properties=channel_properties,
            params={'channelid': channel_id}
        )

        try:
            channel = query['result']['channeldetails']
        except Exception:
            return None

        return channel

    def getStartTimeInterval(self, str_starttime):
        now = datetime.now()
        date_now = now.strftime("%m-%d-%Y")

        starttime = getTimeFromString(date_now + ' ' + str_starttime, '%m-%d-%Y %H:%M')

        if starttime is None:
            log('getStartTimeInterval: could not parse time: %s' % str_starttime, xbmc.LOGWARNING)
            return (None, None, None)

        if now > starttime:
            starttime = starttime + timedelta(days=1)

        start_interval = starttime - timedelta(seconds=300)
        stop_interval = starttime + timedelta(seconds=300)

        return (starttime, start_interval, stop_interval)


