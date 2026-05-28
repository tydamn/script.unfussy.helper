import xbmc
import xbmcaddon
import xbmcgui
import json
import time
from datetime import datetime, timedelta

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

def getUtcOffset():
    return datetime.now() - datetime.utcnow()

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
    Kodi 20+ nahrada za ListItem.setInfo('video', ...).
    Ak by bezal starsi Kodi bez getVideoInfoTag(), pouzije sa stary fallback.
    """
    try:
        tag = li_item.getVideoInfoTag()
    except Exception:
        li_item.setInfo('video', info)
        return

    title = info.get('Title', '')
    if title:
        _safe_tag_call(tag, 'setTitle', str(title))

    originaltitle = info.get('OriginalTitle', '')
    if originaltitle:
        _safe_tag_call(tag, 'setOriginalTitle', str(originaltitle))

    tvshowtitle = info.get('TVShowTitle', '')
    if tvshowtitle:
        _safe_tag_call(tag, 'setTvShowTitle', str(tvshowtitle))

    year = info.get('Year', '')
    if year not in [None, '']:
        _safe_tag_call(tag, 'setYear', _to_int(year))

    genres = _to_list(info.get('Genre', ''))
    if genres:
        _safe_tag_call(tag, 'setGenres', genres)

    studios = _to_list(info.get('Studio', ''))
    if studios:
        _safe_tag_call(tag, 'setStudios', studios)

    countries = _to_list(info.get('Country', ''))
    if countries:
        _safe_tag_call(tag, 'setCountries', countries)

    plot = info.get('Plot', '')
    if plot:
        _safe_tag_call(tag, 'setPlot', str(plot))

    plotoutline = info.get('PlotOutline', '')
    if plotoutline:
        _safe_tag_call(tag, 'setPlotOutline', str(plotoutline))

    mpaa = info.get('MPAA', '')
    if mpaa:
        _safe_tag_call(tag, 'setMpaa', str(mpaa))

    playcount = info.get('Playcount', None)
    if playcount is not None:
        _safe_tag_call(tag, 'setPlaycount', _to_int(playcount))

    season = info.get('Season', None)
    if season is not None:
        _safe_tag_call(tag, 'setSeason', _to_int(season))

    episode = info.get('Episode', None)
    if episode is not None:
        _safe_tag_call(tag, 'setEpisode', _to_int(episode))

    duration = info.get('Duration', None)
    if duration is not None:
        _safe_tag_call(tag, 'setDuration', _to_int(duration))

    trailer = info.get('Trailer', '')
    if trailer:
        _safe_tag_call(tag, 'setTrailer', str(trailer))

    lastplayed = info.get('LastPlayed', '')
    if lastplayed:
        _safe_tag_call(tag, 'setLastPlayed', str(lastplayed))

    premiered = info.get('Premiered', '')
    if premiered:
        _safe_tag_call(tag, 'setPremiered', str(premiered))
        _safe_tag_call(tag, 'setFirstAired', str(premiered))

    dateadded = info.get('DateAdded', '')
    if dateadded:
        _safe_tag_call(tag, 'setDateAdded', str(dateadded))

    imdbnumber = info.get('IMDBNumber', '')
    if imdbnumber:
        _safe_tag_call(tag, 'setIMDBNumber', str(imdbnumber))

    rating = info.get('Rating', '')
    votes = _to_int(info.get('Votes', 0))
    if rating not in [None, '']:
        _safe_tag_call(tag, 'setRating', _to_float(rating), votes, '', True)

    cast = info.get('Cast', [])
    if cast:
        # Kodi 20+ ocakava zoznam actor objektov; ak sa nepodari, preskocime len cast.
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
                if name and hasattr(xbmc, 'Actor'):
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

########################
# Parser dispatcher
########################

def append_items(li, json_query, type):
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

    if type in parsers:
        for item in json_query:
            if item:
                parsers[type](li, item)

########################
# Parsers
########################

def parse_movies(li, item):
    cast = [c.get('name', '') for c in item.get('cast', [])]

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
        'Cast': cast,
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

    tvshowid = item.get('tvshowid', '')
    season = item.get('season', '')
    path = 'videodb://tvshows/titles/%s/%s/' % (tvshowid, season)

    li.append((path, li_item, True))

def parse_episodes(li, item):
    title = item.get('title') or item.get('label') or ''
    showtitle = item.get('showtitle', '')

    li_item = xbmcgui.ListItem(label=title)
    set_video_info(li_item, {
        'Title': title,
        'TVShowTitle': showtitle,
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
        art = {
            'thumb': item.get('thumbnail', ''),
            'fanart': item.get('fanart', ''),
        }

    li_item.setArt(art)

    resume = item.get('resume', {})
    if isinstance(resume, dict):
        position = resume.get('position', 0)
        total = resume.get('total', 0)
        if position and total:
            li_item.setProperty('ResumeTime', str(position))
            li_item.setProperty('TotalTime', str(total))

    path = item.get('file', '')
    li.append((path, li_item, False))

def _first_non_empty(*values):
    for value in values:
        if value is None:
            continue
        value = str(value).strip()
        if value:
            return value
    return ''

def _get_art_value(art, *keys):
    if not isinstance(art, dict):
        return ''
    for key in keys:
        value = art.get(key, '')
        if value:
            return str(value).strip()
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

    item_art = item.get('art', {})
    if not isinstance(item_art, dict):
        item_art = {}

    # Skusame viac moznych zdrojov obrazkov.
    # Niektori PVR provideri posielaju iba "thumbnail",
    # ini mozu mat obrazky ulozene v "art" ako poster/thumb/fanart/icon.
    epg_image = _first_non_empty(
        item.get('thumbnail', ''),
        item.get('epgeventicon', ''),
        item.get('icon', ''),
        _get_art_value(item_art, 'thumb', 'thumbnail', 'poster', 'landscape', 'fanart', 'icon')
    )

    poster_image = _first_non_empty(
        _get_art_value(item_art, 'poster'),
        epg_image
    )

    thumb_image = _first_non_empty(
        _get_art_value(item_art, 'thumb', 'thumbnail'),
        epg_image
    )

    fanart_image = _first_non_empty(
        _get_art_value(item_art, 'fanart', 'landscape'),
        epg_image
    )

    channel_icon = _first_non_empty(
        item.get('channelicon', ''),
        item.get('channel_icon', ''),
        item.get('channelthumbnail', ''),
        _get_art_value(item_art, 'icon')
    )

    li_item.setProperty('broadcastid', str(item.get('broadcastid', item.get('id', ''))))
    li_item.setProperty('channelid', str(item.get('channelid', item.get('channel_id', ''))))
    li_item.setProperty('episodename', str(item.get('episodename', '')))
    li_item.setProperty('runtime', str(item.get('runtime', '')))
    li_item.setProperty('date', str(item.get('date', '')))
    li_item.setProperty('starttime', str(item.get('starttime', '')))
    li_item.setProperty('endtime', str(item.get('endtime', '')))
    li_item.setProperty('channelname', str(item.get('channelname', '')))

    # Properties pre custom XML okno.
    li_item.setProperty('thumbnail', thumb_image)
    li_item.setProperty('epgeventicon', epg_image)
    li_item.setProperty('poster', poster_image)
    li_item.setProperty('fanart', fanart_image)
    li_item.setProperty('channelicon', channel_icon)

    art = dict(item_art)
    if thumb_image:
        art['thumb'] = thumb_image
    if poster_image:
        art['poster'] = poster_image
    if fanart_image:
        art['fanart'] = fanart_image
        art['landscape'] = fanart_image
    if epg_image:
        art['icon'] = epg_image

    # Ikonka kanala ma mat prednost pre ListItem.Icon.
    if channel_icon:
        art['icon'] = channel_icon

    li_item.setArt(art)

    log(
        'parse_broadcast art: title="%s", epgeventicon="%s", thumbnail="%s", poster="%s", fanart="%s", channelicon="%s"'
        % (title, epg_image, thumb_image, poster_image, fanart_image, channel_icon),
        xbmc.LOGDEBUG
    )

    li.append(('', li_item, False))

def parse_timer(li, item):
    title = item.get('title') or item.get('label') or ''

    li_item = xbmcgui.ListItem(label=title)
    set_video_info(li_item, {
        'Title': title,
        'Plot': item.get('plot', ''),
    })

    li_item.setArt({
        'icon': item.get('channelicon', ''),
        'thumb': item.get('channelicon', ''),
    })

    li.append(('', li_item, False))

def parse_cast(li, item):
    name = item.get('name', '')
    li_item = xbmcgui.ListItem(label=name)

    set_video_info(li_item, {
        'Title': name,
    })

    li_item.setArt({
        'thumb': item.get('thumbnail', ''),
        'icon': item.get('thumbnail', ''),
    })

    li.append(('', li_item, False))

########################
# Main Execution Block
########################

if __name__ == "__main__":
    log("Script for Kodi 21 initialized", xbmc.LOGINFO)