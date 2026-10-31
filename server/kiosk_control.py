"""Persist the explicit mute latch across Wi-Fi reconnects and host restarts."""
import json
from pathlib import Path
import threading

from server.experiences import atomic_json
from server.profiles import private_path


class MuteLatch:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else private_path('kiosk-control.json')
        self._lock = threading.RLock()
        self.error = None
        try:
            saved = json.loads(self.path.read_text())
            if (not isinstance(saved, dict) or set(saved) != {'version', 'muted'}
                    or type(saved['version']) is not int or saved['version'] != 1
                    or type(saved['muted']) is not bool):
                raise ValueError('Invalid kiosk mute state')
            self._value = saved['muted']
        except FileNotFoundError:
            self._value = False
        except (OSError, ValueError, TypeError):
            self._value = True
            self.error = 'Mute settings need repair; kiosk stays muted.'

    @property
    def value(self):
        with self._lock:
            return self._value

    def set_muted(self, muted):
        """Return effective state. Failed persistence never permits unmuting."""
        if type(muted) is not bool:
            raise ValueError('Mute must be a boolean')
        with self._lock:
            try:
                atomic_json(self.path, {'version': 1, 'muted': muted})
            except OSError:
                self._value = True
                self.error = 'Mute settings could not be saved; kiosk stays muted.'
            else:
                self._value = muted
                self.error = None
            return self._value
