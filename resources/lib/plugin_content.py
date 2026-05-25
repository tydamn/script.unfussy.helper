#!/usr/bin/python
import xbmcplugin
from resources.lib.helper import *
from resources.lib.pvr_running_at import PVRRunningAt
from resources.lib.pvr_timers import PVRTimers
from resources.lib.pvr_channellist import PVRChannelList

episode_properties = [
    'title', 'plot', 'plotoutline', 'season', 'episode', 'showtitle',
    'tvshowid', 'thumbnail', 'fanart', 'art', 'file', 'playcount',
    'lastplayed', 'resume', 'runtime', 'rating', 'firstaired', 'dateadded'
]

class PluginContent:

    def __init__(self):
        self.resultlist = list()

    def result(self):
        return self.resultlist

    def fetchNextEpisodes(self):
        inprogress_shows = self.getInprogressTVShows()
        for show in inprogress_shows:
            tvshowid = int(show['tvshowid'])
            last_played_episode = self.getLastPlayedEpisode(tvshowid)
            if not last_played_episode:
                continue
            next_episode_id = self.getNextEpisode(tvshowid, last_played_episode)
            if next_episode_id > 0:
                next_episode = self.getEpisode(next_episode_id)
                append_items(self.resultlist, [next_episode], type='episodes')

    def fetchActors(self, movie_id, tvshow):
        cast = []
        if movie_id:
            query = json_call('VideoLibrary.GetMovieDetails',
                properties=['cast'],
                params={'movieid': int(movie_id)}
            )
            cast = query['result']['moviedetails']['cast']
        elif tvshow:
            query = json_call('VideoLibrary.GetTVShows',
                properties=['cast'],
                limit=1,
                query_filter={'operator': 'is', 'field': 'title', 'value': tvshow}
            )
            cast = query['result']['tvshows'][0]['cast']
        append_items(self.resultlist, cast, type='cast')

    def fetchRunningAt(self, pointintime, channel_ids):
        running_at = PVRRunningAt()
        ok = pvrAvailable()
        if not ok:
            log("pvr not available, aborting")
            return
        channel_ids = channel_ids.replace('-', ',')
        channel_ids = json.loads(channel_ids)
        broadcast_ids = []
        for channel_id in channel_ids:
            bc = running_at.getBroadcastAt(pointintime, channel_id)
            if bc:
                broadcast_ids.append({
                    'broadcastid': bc['broadcastid'],
                    'channelid': channel_id
                })
        broadcasts = running_at.getBroadcastsById(broadcast_ids)
        append_items(self.resultlist, broadcasts, type='broadcasts')

    def fetchTimers(self):
        ok = pvrAvailable()
        if not ok:
            log("pvr not available, aborting")
            return
        ti = PVRTimers()
        timers = ti.fetchTimers()
        for t in timers:
            channel = ti.fetchChannel(t['channelid'])
            t['channelicon'] = channel['icon'] if channel else ''
        append_items(self.resultlist, timers, type='timers')

    def _dedupe_broadcast_items(self):
        # Defensive cleanup for PVR backends that return the same EPG block repeatedly.
        # We dedupe after append_items(), so we compare the final ListItem values that
        # are actually used by the skin/list.
        seen = set()
        cleaned = []

        for item in self.resultlist:
            try:
                url, li_item, is_folder = item

                title = li_item.getLabel() or ''
                date = li_item.getProperty('date') or ''
                starttime = li_item.getProperty('starttime') or ''
                endtime = li_item.getProperty('endtime') or ''
                broadcastid = li_item.getProperty('broadcastid') or ''

                # Prefer the visible row identity. Do NOT rely only on broadcastid,
                # because some PVR backends can repeat the same EPG item with a new id.
                key = (
                    title.strip().lower(),
                    date.strip(),
                    starttime.strip(),
                    endtime.strip()
                )

                # If the item has almost no time metadata, keep broadcastid in the key
                # so unrelated empty items are not accidentally collapsed.
                if not any(key):
                    key = ('broadcastid', broadcastid)

                if key in seen:
                    log('fetchBroadcasts: duplicate EPG item removed: %s %s %s-%s'
                        % (title, date, starttime, endtime), xbmc.LOGDEBUG)
                    continue

                seen.add(key)
                cleaned.append(item)
            except Exception:
                # If something unexpected is in resultlist, keep it rather than breaking UI.
                cleaned.append(item)

        self.resultlist = cleaned

    def fetchBroadcasts(self, channel_num, channel_ids):
        channel_id = None

        try:
            channel_id = channel_ids.get(str(channel_num))
        except Exception:
            channel_id = None

        if channel_id is None:
            try:
                channel_id = channel_ids.get(channel_num)
            except Exception:
                channel_id = None

        if channel_id is None:
            log('fetchBroadcasts: missing channel_id for channel_num=%s channel_ids=%s' % (channel_num, channel_ids), xbmc.LOGWARNING)
            return

        cl = PVRChannelList()
        broadcasts = cl.fetchBroadcasts(channel_id)

        before = len(self.resultlist)
        append_items(self.resultlist, broadcasts, type='broadcasts_short')
        after_append = len(self.resultlist)

        self._dedupe_broadcast_items()
        after_dedupe = len(self.resultlist)

        log('fetchBroadcasts: channel_id=%s broadcasts=%s result_before=%s after_append=%s after_dedupe=%s'
            % (channel_id, len(broadcasts), before, after_append, after_dedupe), xbmc.LOGDEBUG)

    def getInprogressTVShows(self):
        query = json_call('VideoLibrary.GetTVShows',
            properties=[],
            limit=25,
            sort={"method": "lastplayed", "order": "descending"},
            query_filter={'field': 'inprogress', 'operator': 'true', 'value': ''}
        )
        try:
            return query['result']['tvshows']
        except Exception:
            log('getNextEpisodes: No Inprogress TVShows found.')
            return []

    def getLastPlayedEpisode(self, tvshowid):
        query = json_call('VideoLibrary.GetEpisodes',
            properties=['season'],
            limit=1,
            sort={"method": "lastplayed", "order": "descending"},
            query_filter={"field": "playcount", "operator": "isnot", "value": "0"},
            params={'tvshowid': tvshowid}
        )
        try:
            return query['result']['episodes'][0]
        except Exception:
            log('getLastPlayedEpisode: No Last Played Episode found.')
            return 0

    def getNextEpisode(self, tvshowid, last_played_episode):
        season = last_played_episode['season'] - 1
        query = json_call('VideoLibrary.GetEpisodes',
            properties=[],
            sort={"method": "episode"},
            query_filter={"field": "season", "operator": "greaterthan", "value": "%s" % season},
            params={'tvshowid': tvshowid}
        )
        try:
            episodes = query['result']['episodes']
        except Exception:
            return 0

        found = False
        for episode in episodes:
            if found:
                return episode['episodeid']
            if episode['episodeid'] == last_played_episode['episodeid']:
                found = True
        return 0

    def getEpisode(self, episodeid):
        query = json_call('VideoLibrary.GetEpisodeDetails',
            properties=episode_properties,
            params={'episodeid': episodeid}
        )
        try:
            return query['result']['episodedetails']
        except Exception:
            return {}