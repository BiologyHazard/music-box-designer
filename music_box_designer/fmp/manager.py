from pathlib import Path
from typing import Any, Self
from .fmp_v0 import FmpFile as FmpFileV0
from .fmp_v1 import FmpFile as FmpFileV1
from .fmp_v2 import FmpFile as FmpFileV2

format_to_class = {
    0: FmpFileV0,
    1: FmpFileV1,
    2: FmpFileV2,
}

FmpFile: type[FmpFileV2] = format_to_class[2]
