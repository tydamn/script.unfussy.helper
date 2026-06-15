#!/usr/bin/python
# coding: utf-8
import xbmc, xbmcgui, xbmcaddon, xbmcvfs
from resources.lib.helper import *

#######################################################################################

ADDON = xbmcaddon.Addon()

channeldetail_properties = [
    'thumbnail',
    'channel',
    'channelnumber',
    'hidden',
    'locked',
    'broadcastnow',
    'broadcastnext'
]

#######################################################################################

class Gui_ChannelGuide(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.channelgroups = None
        self.detail_active = False
        self.channels_loaded = self.loadChannels()

    def loadChannels(self):
        if not self.loadChannelGroups():
            return False

        for index, group in enumerate(self.channelgroups):
            group_id = group['channelgroupid']
            query = json_call('PVR.GetChannels',
                    properties=channeldetail_properties,
                    params={'channelgroupid': group_id})
            try:
                self.channelgroups[index]['channels'] = query['result']['channels']
                self.channelgroups[index]['channellistitems'] = None
            except Exception:
                log('error loading channels', xbmc.LOGWARNING)
                return False
        return True

    def loadChannelGroups(self):
        query = json_call('PVR.GetChannelGroups',
                    params={'channeltype': 'tv'})
        try:
            self.channelgroups = query['result']['channelgroups']
        except Exception:
            return False

        log("loaded groups: %s" % self.channelgroups, xbmc.LOGDEBUG)

        hide_all_channels = xbmc.getCondVisibility('Skin.HasSetting(hide_all_channels)')
        if hide_all_channels:
            allchannels = -1
            str_allchannels = xbmc.getLocalizedString(19287)
            for index, group in enumerate(self.channelgroups):
                if group['label'] == str_allchannels:
                    allchannels = index
                    break
            if allchannels > -1:
                del self.channelgroups[allchannels]

        log("groups after hide_all_channels: %s" % self.channelgroups, xbmc.LOGDEBUG)
        return True

    def onInit(self):
        self.hor_layout = xbmc.getCondVisibility('Skin.HasSetting(use_channelgroups_fullwidth)')
        if not self.channels_loaded:
            return

        self.list_channelgroups = self.getControl(12)
        self.list_channels = self.getControl(13)
        self.active_channel_number = self.getActiveChannelNumber()
        self.group_index, self.channel_index = self.getActiveChannelIndex()
        self.jump_to_next_group = xbmc.getCondVisibility('Skin.HasSetting(jump_to_next_channelgroup)')

        self.renderChannelGroups()
        self.list_channelgroups.selectItem(self.group_index)
        self.renderChannels()
        self.positionChannellist()
        self.list_channels.selectItem(self.channel_index)
        self.setFocusId(13)
        xbmc.executebuiltin('ClearProperty(loadingchannels,10608)')

    def onClick(self, control_id):
        if control_id != 13:
            return

        group_index = self.list_channelgroups.getSelectedPosition()
        channel_index = self.list_channels.getSelectedPosition()

        channel = self.channelgroups[group_index]['channels'][channel_index]
        broadcastnow = channel.get('broadcastnow', {})
        channel_uid = broadcastnow.get('channeluid', channel.get('channelid', ''))

        xbmc.executebuiltin('SetProperty(noslide,true,10608)')
        self.setProperty('noslide', 'true')
        xbmc.sleep(10)
        self._close()
        self.switchChannel(channel_uid)

    def onAction(self, action):
        if action.getId() == 92:
            self._close()
        elif action.getId() == 1:
            self.keyLeft()
        elif action.getId() == 2:
            self.keyRight()
        elif action.getId() == 3:
            self.keyUp()
        elif action.getId() == 4:
            self.keyDown()

    def _close(self):
        self.clearProperty('showdetail')
        self.close()
        xbmc.executebuiltin('Action(Close,10608)')

    def keyLeft(self):
        focus = self.getFocusId()
        if focus == 13 and not self.detail_active:
            self.setFocusId(12)
        elif focus == 13 and self.detail_active:
            self.clearProperty('showdetail')
            self.detail_active = False
        elif focus == 12:
            self._close()

    def keyRight(self):
        focus = self.getFocusId()
        if focus == 12:
            self.setFocusId(13)
        elif focus == 13:
            self.setProperty('showdetail', 'true')
            self.detail_active = True

    def keyUp(self):
        focus = self.getFocusId()
        if focus == 12:
            self.group_index = self.list_channelgroups.getSelectedPosition()
            self.channel_index = 0
            self.updateChannels()
        elif focus == 13:
            self.channel_index = self.list_channels.getSelectedPosition()
            if self.channel_index == len(self.channelgroups[self.group_index]['channels']) - 1 and self.jump_to_next_group:
                self.groupUp()

    def keyDown(self):
        focus = self.getFocusId()
        if focus == 12:
            self.group_index = self.list_channelgroups.getSelectedPosition()
            self.channel_index = 0
            self.updateChannels()
        elif focus == 13:
            self.channel_index = self.list_channels.getSelectedPosition()
            if self.channel_index == 0 and self.jump_to_next_group:
                self.groupDown()

    def groupUp(self):
        self.group_index -= 1
        if self.group_index == -1:
            self.group_index = len(self.channelgroups) - 1
        self.list_channelgroups.selectItem(self.group_index)
        self.channel_index = len(self.channelgroups[self.group_index]['channels']) - 1
        self.updateChannels()

    def groupDown(self):
        self.group_index += 1
        if self.group_index == len(self.channelgroups):
            self.group_index = 0
        self.list_channelgroups.selectItem(self.group_index)
        self.channel_index = 0
        self.updateChannels()

    def updateChannels(self):
        self.renderChannels()
        self.positionChannellist()
        self.list_channels.selectItem(self.channel_index)

    def renderChannels(self):
        if not self.channelgroups[self.group_index]['channellistitems']:
            self.setChannelListItems()

        self.list_channels.reset()

        for item in self.channelgroups[self.group_index]['channellistitems']:
            self.list_channels.addItem(item)

    def renderChannelGroups(self):
        for index, group in enumerate(self.channelgroups):
            listitem = xbmcgui.ListItem(group.get('label', ''))
            listitem.setProperty('numchannels', str(len(group.get('channels', []))))
            if index == self.group_index:
                listitem.setProperty('group_activechannel', 'true')
                listitem.select(True)
            self.list_channelgroups.addItem(listitem)

    def positionChannellist(self):
        if self.hor_layout:
            return

        x = 100
        y = 0
        height = 1080
        max_items = 11
        num_channels = len(self.channelgroups[self.group_index]['channels'])

        if num_channels < max_items:
            height = num_channels * 100
            y = int((1080 - height) / 2)

        self.list_channels.setHeight(height)
        self.list_channels.setPosition(x, y)

    def setChannelListItems(self):
        self.channelgroups[self.group_index]['channellistitems'] = []
        utc_offset = getUtcOffset()

        for channel in self.channelgroups[self.group_index]['channels']:
            try:
                broadcastnow = channel.get('broadcastnow', {})
                broadcastnext = channel.get('broadcastnext', {})

                listitem = xbmcgui.ListItem(channel.get('label', ''))

                channel_icon = channel.get('icon') or channel.get('thumbnail', '')
                listitem.setArt({'icon': channel_icon, 'thumb': channel_icon})

                listitem.setProperty('channelnumber', str(channel.get('channelnumber', '')))
                listitem.setProperty('isrecording', str(broadcastnow.get('hastimer', '')))
                listitem.setProperty('progress', str(int(broadcastnow.get('progresspercentage', 0))))

                listitem.setProperty('now_title', broadcastnow.get('title', ''))
                listitem.setProperty('now_episodename', broadcastnow.get('episodename', ''))
                listitem.setProperty('now_episodenum', str(broadcastnow.get('episodenum', '')))
                listitem.setProperty('now_year', str(broadcastnow.get('year', '')))
                listitem.setProperty('now_director', broadcastnow.get('director', ''))
                listitem.setProperty('now_genre', ', '.join(broadcastnow.get('genre', [])))
                listitem.setProperty('now_cast', str(broadcastnow.get('cast', '')))
                listitem.setProperty('now_plot', broadcastnow.get('plot', ''))

                starttime = getTimeFromString(broadcastnow.get('starttime', ''), '%Y-%m-%d %H:%M:%S', utc_offset)
                endtime = getTimeFromString(broadcastnow.get('endtime', ''), '%Y-%m-%d %H:%M:%S', utc_offset)

                if starttime:
                    listitem.setProperty('now_starttime', starttime.strftime('%H:%M'))
                else:
                    listitem.setProperty('now_starttime', '')

                if endtime:
                    listitem.setProperty('now_endtime', endtime.strftime('%H:%M'))
                else:
                    listitem.setProperty('now_endtime', '')

                listitem.setProperty('now_runtime', str(broadcastnow.get('runtime', '')))

                listitem.setProperty('next_title', broadcastnext.get('title', ''))
                listitem.setProperty('next_episodename', broadcastnext.get('episodename', ''))
                listitem.setProperty('next_episodenum', str(broadcastnext.get('episodenum', '')))
                listitem.setProperty('next_year', str(broadcastnext.get('year', '')))
                listitem.setProperty('next_director', broadcastnext.get('director', ''))
                listitem.setProperty('next_genre', ', '.join(broadcastnext.get('genre', [])))
                listitem.setProperty('next_cast', str(broadcastnext.get('cast', '')))
                listitem.setProperty('next_plot', broadcastnext.get('plot', ''))

                starttime_next = getTimeFromString(broadcastnext.get('starttime', ''), '%Y-%m-%d %H:%M:%S', utc_offset)
                endtime_next = getTimeFromString(broadcastnext.get('endtime', ''), '%Y-%m-%d %H:%M:%S', utc_offset)

                if starttime_next:
                    listitem.setProperty('next_starttime', starttime_next.strftime('%H:%M'))
                else:
                    listitem.setProperty('next_starttime', '')

                if endtime_next:
                    listitem.setProperty('next_endtime', endtime_next.strftime('%H:%M'))
                else:
                    listitem.setProperty('next_endtime', '')

                listitem.setProperty('next_runtime', str(broadcastnext.get('runtime', '')))

                if channel.get('channelnumber') == self.active_channel_number:
                    listitem.select(True)

                self.channelgroups[self.group_index]['channellistitems'].append(listitem)

            except Exception as e:
                log('no epg for channel: %s' % e, xbmc.LOGWARNING)

    def getActiveChannelNumber(self):
        channel_num = xbmc.getInfoLabel('VideoPlayer.ChannelNumberLabel')
        try:
            return int(channel_num)
        except Exception:
            return -1

    def getActiveChannelIndex(self):
        for index, group in enumerate(self.channelgroups):
            for index_channel, channel in enumerate(group.get('channels', [])):
                if channel.get('channelnumber') == self.active_channel_number:
                    return (index, index_channel)

        return (0, 0)

    def switchChannel(self, channel_uid):
        all_channels_loc = xbmc.getLocalizedString(19287)
        pvr_backend = self.pvrBackendAddonId()

        if not pvr_backend:
            return

        pvr_url = 'pvr://channels/tv/' + all_channels_loc + '/' + pvr_backend + '_' + str(channel_uid) + '.pvr'
        action = 'PlayMedia(' + pvr_url + ')'
        xbmc.executebuiltin(action)

    def pvrBackendAddonId(self):
        query_addons = json_call('Addons.GetAddons', params={'type': 'xbmc.pvrclient'}, properties=['enabled'])
        try:
            addons = query_addons['result']['addons']
            for addon in addons:
                if addon['enabled']:
                    return addon['addonid']
            return None
        except Exception as e:
            log('error querying pvr addon: %s' % e, xbmc.LOGWARNING)
            return None