"""Shared helper so a service can roll an object back if saving to disk fails."""


class Record:
    def to_dict(self):
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data):
        raise NotImplementedError

    def snapshot(self):
        return self.to_dict()

    def restore(self, snap):
        self.__dict__.update(type(self).from_dict(snap).__dict__)
