from enum import Enum


class OrbitType(str, Enum):
    CIRCULAR_LEO = "CIRCULAR_LEO"
    CIRCULAR_SSO = "CIRCULAR_SSO"


class ReferenceFrame(str, Enum):
    J2000 = "J2000"
    TEME = "TEME"


class OrbitSourceType(str, Enum):
    MODEL = "MODEL"
    PUBLIC_DATA = "PUBLIC_DATA"
    TLE = "TLE"
    EXTERNAL = "EXTERNAL"