"""HID++ 0x8060 report intervals with confirmation and restoration."""
RATE_INTERVALS = {round(1000 / ms): ms for ms in range(1, 9)}

class PollingControl:
    def __init__(self, request, index):
        self.request, self.index = request, index
        self.intervals = {}
        self.original = self.current = None
        self.dirty = False

    def read(self):
        reply = self.request(self.index, 1)
        if not reply or reply[0] not in self.intervals.values():
            raise OSError('El mouse comunicó una frecuencia de respuesta inválida.')
        return reply[0]

    def load(self):
        reply = self.request(self.index, 0)
        if not reply or not reply[0]:
            raise OSError('El mouse no comunicó frecuencias disponibles.')
        self.intervals = {hz: ms for hz, ms in RATE_INTERVALS.items() if reply[0] & (1 << (ms - 1))}
        self.original = self.current = self.read()
        return self.state()

    def state(self):
        return dict(values=sorted(self.intervals, reverse=True), current=round(1000 / self.current))

    def validate(self, hz):
        if type(hz) is not int or hz not in self.intervals:
            raise ValueError('El mouse no admite esa frecuencia de respuesta.')

    def apply(self, hz):
        self.validate(hz)
        interval = self.intervals[hz]
        self.dirty = True
        self.request(self.index, 2, [interval])
        self.current = self.read()
        if self.current != interval:
            raise OSError('El mouse no confirmó la frecuencia solicitada.')
        return self.state()

    def restore(self, after_mode_change=False):
        if self.original is None or not (self.dirty or after_mode_change):
            return
        if self.read() != self.original:
            self.request(self.index, 2, [self.original])
        if self.read() != self.original:
            raise OSError('El mouse no confirmó su frecuencia anterior.')
        self.current = self.original
        self.dirty = False
