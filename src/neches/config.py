"""Settings for one generator run: how big the fleet is and what time window it covers."""

# dataclass turns a list of fields into a class; datetime/UTC define the window start.
from dataclasses import dataclass
from datetime import UTC, datetime


# frozen=True means the settings cannot be changed after creation.
# That keeps every run predictable (no one can tweak a value halfway through).
@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 20261116  # the one number that makes all randomness repeatable
    olts: int = 5  # number of OLTs (the neighborhood boxes)
    ports_per_olt: int = 5  # PON ports on each OLT
    devices_per_port: int = 20  # customer devices (ONTs) sharing one port
    days: int = 14  # how many days of data to produce
    interval_minutes: int = 5  # one reading every 5 minutes
    start: datetime = datetime(2026, 11, 1, tzinfo=UTC)  # first moment of the window

    @property
    def n_devices(self) -> int:
        # Total devices = OLTs x ports per OLT x devices per port.
        return self.olts * self.ports_per_olt * self.devices_per_port

    @property
    def readings_per_device(self) -> int:
        # Minutes in the window divided by minutes between readings.
        # 14 days x 24 hours x 60 minutes / 5 = 4,032.
        return self.days * 24 * 60 // self.interval_minutes

    @classmethod
    def dev(cls) -> "GeneratorConfig":
        # Everyday development size: 5 x 5 x 20 = 500 devices.
        return cls()

    @classmethod
    def full(cls) -> "GeneratorConfig":
        # Full portfolio run: 25 x 4 x 20 = 2,000 devices.
        return cls(olts=25, ports_per_olt=4)

    @classmethod
    def tiny(cls) -> "GeneratorConfig":
        # Fast test size: 1 x 5 x 10 = 50 devices for 1 day.
        return cls(olts=1, ports_per_olt=5, devices_per_port=10, days=1)
