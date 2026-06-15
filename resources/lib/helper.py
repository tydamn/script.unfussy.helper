import xbmc
import xbmcaddon
import xbmcgui
import json
import time
from datetime import datetime, timezone

########################

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

LOG_ENABLED = ADDON.getSettingBool('log')
DEBUGLOG_ENABLED = ADDON.getSettingBool('debuglog')

########################

def log(txt, loglevel=xbmc.LOGINFO, force=False):
    if ((loglevel in [xbmc.LOGINFO, xbmc.LOGWARNING] and LOG_ENABLED) or
        (loglevel == xbmc.LOGDEBUG and DEBUGLOG_ENABLED) or force):
        message = '[ %s ] %s' % (ADDON_ID, txt)
        xbmc.log(message, level=loglevel)

def json_call(method, properties=None, sort=None, query_filter=None, limit=None, params=None, item=None):
    json_string = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': {}}

    if properties is not None:
        json_string['params']['properties'] = properties
    if limit is not None:
        json_string['params']['limits'] = {'start': 0, 'end': limit}
    if sort is not None:
        json_string['params']['sort'] = sort
    if query_filter is not None:
        json_string['params']['filter'] = query_filter
    if item is not None:
        json_string['params']['item'] = item
    if params is not None:
        json_string['params'].update(params)

    json_string = json.dumps(json_string)
    result = xbmc.executeJSONRPC(json_string)
    result = json.loads(result)

    log('json-string: %s' % json_string, xbmc.LOGDEBUG)
    log('json-result: %s' % result, xbmc.LOGDEBUG)

    return result

def visible(condition):
    return xbmc.getCondVisibility(condition)

def pvrAvailable():
    retries = 0
    num_retries = 50
    while retries < num_retries:
        channels = json_call('PVR.GetChannels', limit=1, params={'channelgroupid': 'alltv'})
        try:
            channel_id = channels['result']['channels'][0]['channelid']
            broadcast = json_call('PVR.GetBroadcasts', params={'channelid': channel_id}, limit=1)
            if 'broadcasts' in broadcast['result']:
                xbmc.sleep(200)
                log("pvrAvailable: success...continue")
                return True
        except Exception:
            retries += 1
            log("pvrAvailable: retrying...", xbmc.LOGWARNING)
            xbmc.sleep(500)
    return False

def getTimeFromString(str_time, time_format=None, utc_offset=None):
    if not str_time:
        return None

    str_time = str(str_time).strip()

    formats = [
        time_format,
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%S.%f%z',
    ]

    for fmt in formats:
        if not fmt:
            continue
        try:
            parsed_time = datetime.strptime(str_time, fmt)
            if utc_offset and parsed_time.tzinfo is None:
                parsed_time += utc_offset
            return parsed_time
        except Exception:
            pass

    log('getTimeFromString: unsupported time format: %s' % str_time, xbmc.LOGWARNING)
    return None

# Vráti rozdiel medzi lokálnym časom a UTC (napr. CEST = +2h, CET = +1h).
# Jedno volanie — atomické, žiadny drift medzi dvoma volaniami.
def getUtcOffset():
    now = datetime.now(timezone.utc)
    return now.astimezone().replace(tzinfo=None) - now.replace(tzinfo=None)

def _to_int(value, default=0):
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except Exception:
        return default

def _to_float(value, default=0.0):
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default

def _to_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    value = str(value).strip()
    if not value:
        return []
    return [v.strip() for v in value.split(',') if v.strip()]

def _safe_tag_call(tag, method, *args):
    try:
        fn = getattr(tag, method, None)
        if fn:
            fn(*args)
            return True
    except Exception as e:
        log('InfoTagVideo.%s failed: %s' % (method, e), xbmc.LOGDEBUG)
    return False

def set_video_info(li_item, info):
    """
    Kodi 20+ náhrada za ListItem.setInfo('video', ...).
    """
    try:
        tag = li_item.getVideoInfoTag()
    except Exception:
        li_item.setInfo('video', info)
        return

    # Textové hodnoty
    for key, method in [
        ('Title', 'setTitle'),
        ('OriginalTitle', 'setOriginalTitle'),
        ('TVShowTitle', 'setTvShowTitle'),
        ('Plot', 'setPlot'),
        ('PlotOutline', 'setPlotOutline'),
        ('MPAA', 'setMpaa'),
        ('Trailer', 'setTrailer'),
        ('LastPlayed', 'setLastPlayed'),
        ('Premiered', 'setPremiered'),
        ('DateAdded', 'setDateAdded'),
        ('IMDBNumber', 'setIMDBNumber')
    ]:
        val = info.get(key, '')
        if val:
            _safe_tag_call(tag, method, str(val))

    # FIX: Odstránený duplicitný blok setFirstAired — neexistuje v Kodi 20+
    # a Premiered je už nastavený cez setPremiered vyššie.

    # Int hodnoty
    for key, method in [
        ('Year', 'setYear'),
        ('Playcount', 'setPlaycount'),
        ('Season', 'setSeason'),
        ('Episode', 'setEpisode'),
        ('Duration', 'setDuration')
    ]:
        val = info.get(key)
        if val not in [None, '']:
            _safe_tag_call(tag, method, _to_int(val))

    # List hodnoty
    for key, method in [
        ('Genre', 'setGenres'),
        ('Studio', 'setStudios'),
        ('Country', 'setCountries')
    ]:
        val = _to_list(info.get(key, ''))
        if val:
            _safe_tag_call(tag, method, val)

    # Hodnotenie (Rating)
    rating = info.get('Rating')
    if rating not in [None, '']:
        votes = _to_int(info.get('Votes', 0))
        _safe_tag_call(tag, 'setRating', _to_float(rating), votes, '', True)

    # Herecké obsadenie (Cast)
    cast = info.get('Cast', [])
    if cast and hasattr(xbmc, 'Actor'):
        actors = []
        for idx, actor in enumerate(cast):
            try:
                if isinstance(actor, dict):
                    name = actor.get('name', '')
                    role = actor.get('role', '')
                    thumb = actor.get('thumbnail', '')
                else:
                    name = str(actor)
                    role = ''
                    thumb = ''
                if name:
                    actors.append(xbmc.Actor(name, role, idx, thumb))
            except Exception:
                pass
        if actors:
            _safe_tag_call(tag, 'setCast', actors)

########################
# Properties
########################

movie_properties = [
    'title', 'originaltitle', 'votes', 'playcount', 'year', 'genre', 'studio',
    'country', 'tagline', 'plot', 'runtime', 'file', 'plotoutline', 'lastplayed',
    'trailer', 'rating', 'resume', 'art', 'streamdetails', 'mpaa', 'director',
    'writer', 'cast', 'dateadded', 'imdbnumber'
]

channel_properties = [
    'thumbnail',
    'channelnumber',
    'channeltype',
    'hidden',
    'locked',
    'icon',
    'isrecording'
]

timer_properties = [
    'title', 'starttime', 'endtime', 'runtime', 'channelid',
    'summary', 'state', 'timertype', 'fulltextepgsearch',
    'startmargin', 'endmargin', 'priority', 'lifetime', 'firstday',
    'weekdays', 'epgsearchstring', 'directory', 'maxrecordings',
    'preventduplicates', 'epguid', 'broadcastid', 'serieslink'
]

########################
# Parser dispatcher
########################

# FIX: 'type' premenovaný na 'item_type' aby neskrýval vstavaný built-in.
# Pre spätnú kompatibilitu akceptujeme aj starý keyword argument 'type'.
def append_items(li, json_query, item_type=None, **kwargs):
    if item_type is None:
        item_type = kwargs.get('type')
    parsers = {
        'movies': parse_movies,
        'tvshows': parse_tvshows,
        'seasons': parse_seasons,
        'episodes': parse_episodes,
        'broadcasts': parse_broadcast,
        'broadcasts_short': parse_broadcast,
        'timers': parse_timer,
        'cast': parse_cast,
    }

    parser = parsers.get(item_type)
    if parser:
        for item in json_query:
            if item:
                parser(li, item)

########################
# Parsers
########################

def parse_movies(li, item):
    # FIX: posielame celý dict herca (nie len meno) aby set_video_info
    # mohlo nastaviť aj rolu a thumbnail
    li_item = xbmcgui.ListItem(label=item.get('title', ''))
    set_video_info(li_item, {
        'Title': item.get('title', ''),
        'OriginalTitle': item.get('originaltitle', ''),
        'Year': item.get('year', ''),
        'Genre': ', '.join(item.get('genre', [])),
        'Studio': ', '.join(item.get('studio', [])),
        'Country': ', '.join(item.get('country', [])),
        'Plot': item.get('plot', ''),
        'Rating': str(item.get('rating', '')),
        'Votes': item.get('votes', ''),
        'MPAA': item.get('mpaa', ''),
        'Playcount': item.get('playcount', 0),
        'Cast': item.get('cast', []),
        'Trailer': item.get('trailer', ''),
    })
    li_item.setArt(item.get('art', {}))
    li.append((item.get('file', ''), li_item, False))

def parse_tvshows(li, item):
    li_item = xbmcgui.ListItem(label=item.get('title', ''))
    set_video_info(li_item, {
        'Title': item.get('title', ''),
        'Year': item.get('year', ''),
        'Genre': ', '.join(item.get('genre', [])),
        'Plot': item.get('plot', ''),
        'Rating': str(item.get('rating', '')),
        'Votes': item.get('votes', ''),
        'MPAA': item.get('mpaa', ''),
        'Playcount': item.get('playcount', 0),
        'Season': item.get('season', 0),
        'Episode': item.get('episode', 0),
    })
    li_item.setArt(item.get('art', {}))
    li.append(('videodb://tvshows/titles/%s/' % item.get('tvshowid', ''), li_item, True))

def parse_seasons(li, item):
    label = item.get('label') or item.get('title') or 'Season %s' % item.get('season', '')
    li_item = xbmcgui.ListItem(label=label)
    set_video_info(li_item, {
        'Title': label,
        'Season': item.get('season', 0),
        'Episode': item.get('episode', 0),
        'Plot': item.get('plot', ''),
        'Playcount': item.get('playcount', 0),
    })
    li_item.setArt(item.get('art', {}))
    path = 'videodb://tvshows/titles/%s/%s/' % (item.get('tvshowid', ''), item.get('season', ''))
    li.append((path, li_item, True))

def parse_episodes(li, item):
    title = item.get('title') or item.get('label') or ''
    li_item = xbmcgui.ListItem(label=title)
    set_video_info(li_item, {
        'Title': title,
        'TVShowTitle': item.get('showtitle', ''),
        'Season': item.get('season', 0),
        'Episode': item.get('episode', 0),
        'Plot': item.get('plot', ''),
        'PlotOutline': item.get('plotoutline', ''),
        'Rating': str(item.get('rating', '')),
        'Playcount': item.get('playcount', 0),
        'LastPlayed': item.get('lastplayed', ''),
        'Premiered': item.get('firstaired', ''),
        'DateAdded': item.get('dateadded', ''),
        'Duration': item.get('runtime', 0),
    })

    art = item.get('art', {})
    if not art:
        art = {'thumb': item.get('thumbnail', ''), 'fanart': item.get('fanart', '')}
    li_item.setArt(art)

    resume = item.get('resume', {})
    if isinstance(resume, dict):
        position = resume.get('position', 0)
        total = resume.get('total', 0)
        if position and total:
            li_item.setProperty('ResumeTime', str(position))
            li_item.setProperty('TotalTime', str(total))

    li.append((item.get('file', ''), li_item, False))

def _first_non_empty(*values):
    for value in values:
        if value not in [None, '']:
            v_str = str(value).strip()
            if v_str:
                return v_str
    return ''

def parse_broadcast(li, item):
    title = item.get('title', '')
    li_item = xbmcgui.ListItem(label=title)

    set_video_info(li_item, {
        'Title': title,
        'Plot': item.get('plot', ''),
        'Genre': item.get('genre', ''),
        'Year': item.get('year', ''),
        'Duration': item.get('runtime', 0),
    })

    item_art = item.get('art') if isinstance(item.get('art'), dict) else {}

    epg_image = _first_non_empty(
        item.get('thumbnail'),
        item.get('epgeventicon'),
        item.get('icon'),
        item_art.get('thumb'),
        item_art.get('thumbnail'),
        item_art.get('poster'),
        item_art.get('landscape'),
        item_art.get('fanart'),
        item_art.get('icon')
    )

    poster_image = _first_non_empty(item_art.get('poster'), epg_image)
    thumb_image = _first_non_empty(item_art.get('thumb'), item_art.get('thumbnail'), epg_image)
    fanart_image = _first_non_empty(item_art.get('fanart'), item_art.get('landscape'), epg_image)

    channel_icon = _first_non_empty(
        item.get('channelicon'),
        item.get('channel_icon'),
        item.get('channelthumbnail'),
        item_art.get('icon')
    )

    # FIX: prehľadnejší fallback pre broadcastid a channelid
    li_item.setProperty('broadcastid', str(item.get('broadcastid') or item.get('id', '')))
    li_item.setProperty('channelid', str(item.get('channelid') or item.get('channel_id', '')))

    for prop, key in [
        ('episodename', 'episodename'),
        ('runtime', 'runtime'),
        ('date', 'date'),
        ('starttime', 'starttime'),
        ('endtime', 'endtime'),
        ('channelname', 'channelname')
    ]:
        li_item.setProperty(prop, str(item.get(key, '')))

    li_item.setProperty('thumbnail', thumb_image)
    li_item.setProperty('epgeventicon', epg_image)
    li_item.setProperty('poster', poster_image)
    li_item.setProperty('fanart', fanart_image)
    li_item.setProperty('channelicon', channel_icon)

    # FIX: icon má jasnú prioritu — channel_icon ak existuje, inak epg_image
    # (predtým sa epg_image nastavil a hneď prepísal channel_iconom)
    art = dict(item_art)
    if thumb_image:   art['thumb'] = thumb_image
    if poster_image:  art['poster'] = poster_image
    if fanart_image:
        art['fanart'] = fanart_image
        art['landscape'] = fanart_image
    art['icon'] = channel_icon or epg_image

    li_item.setArt(art)

    log('parse_broadcast art: title="%s", epgeventicon="%s", channelicon="%s"' % (title, epg_image, channel_icon), xbmc.LOGDEBUG)
    li.append(('', li_item, False))

def parse_timer(li, item):
    title = item.get('title') or item.get('label') or ''
    li_item = xbmcgui.ListItem(label=title)
    set_video_info(li_item, {'Title': title, 'Plot': item.get('plot', '')})

    icon = item.get('channelicon', '')
    li_item.setArt({'icon': icon, 'thumb': icon})
    li.append(('', li_item, False))

def parse_cast(li, item):
    name = item.get('name', '')
    li_item = xbmcgui.ListItem(label=name)
    set_video_info(li_item, {'Title': name})

    thumb = item.get('thumbnail', '')
    li_item.setArt({'thumb': thumb, 'icon': thumb})
    li.append(('', li_item, False))

########################
# Main Execution Block
########################

if __name__ == "__main__":
    log("Script for Kodi 21 initialized", xbmc.LOGINFO)
