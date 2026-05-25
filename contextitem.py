# -*- coding: utf-8 -*-
import sys
import xbmcgui
from resources.lib.addon_paths_manager import AddonPathManager


def _safe_call(obj, method_name, default=''):
    """Safely call a ListItem method and always return a stripped string."""
    try:
        method = getattr(obj, method_name, None)
        if callable(method):
            value = method()
            if value is not None:
                return str(value).strip()
    except Exception:
        pass
    return default


def _get_listitem_path(li):
    """Kodi 21 ListItem does not have getfilename(); use getPath() instead."""
    path = _safe_call(li, 'getPath')
    if path:
        return path

    # Fallbacks for older/custom listitems where the path may be stored as a property.
    for prop in ('path', 'folderpath', 'FolderPath', 'filename', 'filenameandpath', 'FileNameAndPath'):
        try:
            value = li.getProperty(prop)
            if value:
                return str(value).strip()
        except Exception:
            pass

    return ''


if __name__ == '__main__':
    try:
        li = sys.listitem
    except Exception:
        xbmcgui.Dialog().notification('Unfussy Helper', 'Nie je dostupná položka zo zoznamu.', xbmcgui.NOTIFICATION_ERROR, 4000)
        sys.exit(1)

    widget_path = _get_listitem_path(li)
    path_label = _safe_call(li, 'getLabel')

    if not widget_path:
        xbmcgui.Dialog().notification('Unfussy Helper', 'Nepodarilo sa zistiť cestu položky.', xbmcgui.NOTIFICATION_ERROR, 4000)
        sys.exit(1)

    apm = AddonPathManager()
    apm.addPath(widget_path, path_label)
