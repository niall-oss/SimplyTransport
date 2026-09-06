from enum import StrEnum


class StaticStopMapTypes(StrEnum):
    ALL_STOPS = "ALL_STOPS"
    REALTIME_DISPLAYS = "REALTIME_DISPLAYS"
    SHELTERED_STOPS = "SHELTERED_STOPS"
    UNSURVEYED = "UNSURVEYED"

    @property
    def label(self) -> str:
        return {
            StaticStopMapTypes.ALL_STOPS: "All stops",
            StaticStopMapTypes.REALTIME_DISPLAYS: "Realtime displays",
            StaticStopMapTypes.SHELTERED_STOPS: "Sheltered stops",
            StaticStopMapTypes.UNSURVEYED: "Unsurveyed",
        }[self]
