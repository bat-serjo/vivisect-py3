
from envi.archs.arm import *


class Thumb16Module(ArmModule):
    def __init__(self):
        ArmModule.__init__(self, name='thumb16')
        self._arch_dis = self._arch_thumb_dis


class ThumbModule(Thumb16Module):

    def __init__(self):
        ArmModule.__init__(self, name='thumb')
        self._arch_dis = self._arch_thumb_dis
