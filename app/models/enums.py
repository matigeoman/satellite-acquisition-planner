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


class SensorType(str, Enum):
    SAR = "SAR"
    OPTICAL = "OPTICAL"


class ModeCategory(str, Enum):
    SPOTLIGHT = "SPOTLIGHT"
    STRIPMAP = "STRIPMAP"
    SCANSAR = "SCANSAR"
    PUSHBROOM = "PUSHBROOM"
    FRAME = "FRAME"


class ProductType(str, Enum):
    SAR_IMAGE = "SAR_IMAGE"
    PANCHROMATIC = "PANCHROMATIC"
    MULTISPECTRAL = "MULTISPECTRAL"
    PANSHARPENED = "PANSHARPENED"


class FrequencyBand(str, Enum):
    X = "X"
    C = "C"
    L = "L"
    S = "S"
    OTHER = "OTHER"


class LookSideCapability(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    BOTH = "BOTH"
    NADIR_ONLY = "NADIR_ONLY"


class SensorSourceType(str, Enum):
    MODEL = "MODEL"
    PUBLIC_DATA = "PUBLIC_DATA"
    EXTERNAL = "EXTERNAL"


class SatelliteStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"


class SatelliteSourceType(str, Enum):
    MODEL = "MODEL"
    PUBLIC_DATA = "PUBLIC_DATA"
    EXTERNAL = "EXTERNAL"


class RequestMode(str, Enum):
    SINGLE = "SINGLE"
    DUAL_OPTIONAL = "DUAL_OPTIONAL"
    DUAL_REQUIRED = "DUAL_REQUIRED"


class RequestStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ObservationSide(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    NADIR = "NADIR"


class OpportunitySourceType(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    EXTERNAL = "EXTERNAL"
    STK = "STK"
    SAVOIR = "SAVOIR"