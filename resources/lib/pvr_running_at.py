#!/usr/bin/python
import time
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
    'progress',
    'progresspercentage',
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

def safeParseAndCorrectTime(value):
    if not value:
        return None

    value = str(value).strip()

    if value.isdigit():
        try:
            return datetime.fromtimestamp(int(value)) + timedelta(hours=2)
        except Exception:
            pass

    match = re.search(r'(\d{4})[-.](\d{2})[-.](\d{2})[ T](\d{2}):(\d{2})', value)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            hour = int(match.group(4))
            minute = int(match.group(5))

            dt = datetime(year, month, day, hour, minute)
            return dt + timedelta(hours=2)
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
        def_loc = ''
        try:
            def_loc = locale.getdefaultlocale()[0]
            locale.setlocale(locale.LC_ALL, def_loc)
        except Exception:
            log("ERROR setting locale: %s" % def_loc)

    def getBroadcastAt(self, starttime, channelid):
        broadcasts = self.getBroadcasts(channelid)
        if not broadcasts:
            return None

        interval = self.getStartTimeInterval(starttime)
        starttime_dt = interval[0]
        start_interval = interval[1]
        stop_interval = interval[2]

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

        # Progress bar test for custom info dialog.
        # Kodi exposes progress/progresspercentage in PVR.GetBroadcastDetails,
        # but the custom WindowXMLDialog needs it passed as Window properties.
        progresspercentage = broadcast.get('progresspercentage', '')
        if progresspercentage in [None, '']:
            progresspercentage = broadcast.get('progress', '')

        try:
            progress_value = float(progresspercentage)
            if progress_value < 0:
                progress_value = 0
            if progress_value > 100:
                progress_value = 100
            progresspercentage = str(int(round(progress_value)))
        except Exception:
            progresspercentage = '0'

        isactive_value = 'true' if broadcast.get('isactive') is True else 'false'
        showprogress_value = 'true' if isactive_value == 'true' else 'false'

        win.setProperty('progress', str(broadcast.get('progress', '')))
        win.setProperty('progresspercentage', progresspercentage)
        win.setProperty('isactive', isactive_value)
        win.setProperty('showprogress', showprogress_value)

        # log(
        #   'SHOWINFO PROGRESS DEBUG: raw_progress=%s raw_progresspercentage=%s final_progresspercentage=%s isactive=%s showprogress=%s'
        #    % (
        #        broadcast.get('progress', ''),
        #        broadcast.get('progresspercentage', ''),
        #        progresspercentage,
        #        isactive_value,
        #        showprogress_value
        #   ),
        #   xbmc.LOGINFO,
        #   force=True
        # )


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

        channel = broadcast.get('channel') or {}
        win.setProperty('channelid', str(channel.get('channelid', '')))
        win.setProperty('channel', channel.get('channel', ''))
        win.setProperty('channelnumber', str(channel.get('channelnumber', '')))
        win.setProperty('channelicon', channel.get('icon', ''))

        # --- TÚTO ČASŤ TU PRIDAJ/UPRAV ---
        # Pred spustením okna musíme okno najprv "ukázať" (show),
        # aby Kodi načítalo controls do pamäte, inak ich Python nenájde.
        win.show()

        # Počkáme malinký zlomok sekundy, kým Kodi control reálne vytvorí
        time.sleep(0.05)

        try:
            # Vytiahneme si progress bar z XML pomocou jeho ID
            progress_control = win.getControl(601)
            # progresspercentage už máš v kóde vypočítané ako čisté číslo v stringu
            progress_control.setPercent(int(progresspercentage))
        except Exception as e:
            log("ERROR: Nepodarilo sa naplniť progress bar z Pythonu: %s" % e, xbmc.LOGERROR)

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
        query = json_call(
            'PVR.GetBroadcasts',
            params={'channelid': channelid},
            properties=['starttime', 'endtime']
        )

        try:
            broadcasts = query['result']['broadcasts']
        except Exception:
            log("ERROR getBroadcast")
            return None

        return broadcasts

    def _parseKodiDateTime(self, value):
        return safeParseAndCorrectTime(value)

    def _formatRawTime(self, value, add_hours=2):
        dt = safeParseAndCorrectTime(value)
        if dt:
            return dt.strftime('%H:%M')

        value = str(value).strip()
        if len(value) >= 16 and ':' in value:
            return value[11:16]
        return value

    def _formatRawDate(self, value, add_hours=2):
        dt = safeParseAndCorrectTime(value)
        if dt:
            return dt.strftime('%d.%m')

        value = str(value).strip()
        try:
            return datetime.strptime(value[:10], '%Y-%m-%d').strftime('%d.%m')
        except Exception:
            return value[:10]

    def _formatRawDateLong(self, value, add_hours=2):
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

        if now > starttime:
            starttime = starttime + timedelta(days=1)

        start_interval = starttime - timedelta(seconds=300)
        stop_interval = starttime + timedelta(seconds=300)

        return (starttime, start_interval, stop_interval)


