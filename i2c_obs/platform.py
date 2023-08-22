from abc import ABCMeta
from typing import Any, ClassVar, Self, Type

from amaranth.build import Platform as AmaranthPlatform
from amaranth_boards.icebreaker import ICEBreakerPlatform
from amaranth_boards.orangecrab_r0_2 import OrangeCrabR0_2_85FPlatform

__all__ = ["Platform"]


class PlatformRegistry(ABCMeta):
    _registry: ClassVar[dict[str, Type[Self]]] = {}
    _build_targets: ClassVar[set[str]] = set()

    def __new__(mcls, name: str, bases: tuple[type, ...], *args: Any, **kwargs: Any):
        cls = super().__new__(mcls, name, bases, *args, **kwargs)
        if bases:
            mcls._registry[cls.__name__] = cls
            if issubclass(cls, AmaranthPlatform) and cls is not AmaranthPlatform:
                mcls._build_targets.add(cls.__name__)
        return cls

    def __getitem__(cls, key: str) -> "Platform":
        return cls._registry[key]()

    @property
    def build_targets(cls) -> set[str]:
        return cls._build_targets


class Platform(metaclass=PlatformRegistry):
    simulation = False


class icebreaker(ICEBreakerPlatform, Platform):
    pass


class orangecrab(OrangeCrabR0_2_85FPlatform, Platform):
    pass


class cxxsim(Platform):
    simulation = True

    @property
    def default_clk_frequency(self):
        return 3_000_000


class test(Platform):
    simulation = True

    @property
    def default_clk_frequency(self):
        from .sim import clock

        return int(1 / clock())
