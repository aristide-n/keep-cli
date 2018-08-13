import os
import urwid
import logging
import json
import gkeepapi
from .widget import status
from .widget import grid
from .widget import kanban
from .widget import search
from .widget import views
from .widget import help
from . import query

class Application(urwid.Frame):
    """
    Base application widget
    """
    def __init__(self, keep: gkeepapi.Keep, config: dict, config_dir: str, offline: bool=False):
        self.keep = keep
        self.config = config
        self.config_dir = config_dir
        self.offline = offline
        self.w_overlay = None
        self.stack = []

        self.w_status = status.Status(self)

        self.load()

        w_main = self.hydrateView('default')
        self.stack.append(w_main)

        super(Application, self).__init__(w_main, footer=self.w_status)
        self.refresh()

    def push(self, w: urwid.Widget):
        """
        Push a widget onto the rendering stack
        """
        self.stack.append(w)
        self.body = w
        self.body.refresh(self.keep)

    def pop(self):
        """
        Pop a widget off the rendering stack
        """
        if len(self.stack) <= 1:
            return

        self.stack.pop()
        self.body = self.stack[-1]
        self.body.refresh(self.keep)

    def replace(self, w: urwid.Widget):
        """
        Replace the active widget on the rendering stack
        """
        self.body = self.stack[-1] = w
        self.body.refresh(self.keep)

    def overlay(self, w: urwid.Widget=None):
        self.w_overlay = w
        w_top = self.stack[-1]

        if w is None:
            self.body = w_top
        else:
            self.body = urwid.Overlay(
                w, w_top,
                urwid.CENTER, (urwid.RELATIVE, 80),
                urwid.MIDDLE, urwid.PACK
            )

    def refresh(self):
        """
        Refresh keep and the active widget
        """
        if not self.offline:
            self.keep.sync()
        self.save()
        self.body.refresh(self.keep)

    def keypress(self, size, key):
        """
        Handle global keypresses
        """
        key = super(Application, self).keypress(size, key)
        if key == 'r':
            self.refresh()
            key = None
        elif key == '/':
            self.overlay(search.Search(self))
            key = None
        elif key == '?':
            self.overlay(help.Help(self))
            key = None
        elif key == 'g':
            self.overlay(views.Views(self))
            key = None
        elif key == 'esc':
            if self.w_overlay is not None:
                self.overlay(None)
            elif len(self.stack) <= 1:
                self.refresh()
                raise urwid.ExitMainLoop()
            else:
                self.pop()
        return key

    def load(self):
        username = self.config.get('username', 'user')
        cache_file = os.path.join(self.config_dir, '%s.json' % username)

        try:
            fh = open(cache_file, 'r')
        except FileNotFoundError:
            logging.warn('Unable to find state file: %s', cache_file)
            return

        try:
            state = json.load(fh)
        except json.decoder.JSONDecodeError:
            logging.warn('Unable to load state file: %s', cache_file)
            return

        fh.close()
        self.keep.restore(state)

    def save(self):
        username = self.config.get('username', 'user')
        cache_file = os.path.join(self.config_dir, '%s.json' % username)

        state = self.keep.dump()
        fh = open(cache_file, 'w')
        json.dump(state, fh)
        fh.close()

    def hydrateView(self, key: str) -> query.Query:
        views = self.config.get('views') or {}
        view = views.get(key) or {}
        _type = view.get('type', 'grid')

        if _type == 'kanban':
            raw_queries = view.get('queries') or []
            return kanban.KanBan(
                self,
                [query.Query.fromConfig(self.keep, raw_query) for raw_query in raw_queries]
            )

        raw_query = view.get('query') or {}
        q = query.Query.fromConfig(self.keep, raw_query)
        return grid.Grid(self, q)
