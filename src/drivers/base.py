import abc

class BaseDriver(abc.ABC):
    @property
    @abc.abstractmethod
    def supported_devices(self) -> dict[tuple[int, int], str]:
        """Return mapping of (VID, PID) -> Device Name."""
        pass

    @property
    @abc.abstractmethod
    def dev_idx(self) -> int:
        """The primary device index this driver uses."""
        pass

    @abc.abstractmethod
    def find_devices(self, verbose: bool = False) -> list[dict]:
        """Return list of hid.enumerate() dicts that this driver handles."""
        pass
        
    @abc.abstractmethod
    def open_device(self, info: dict) -> object:
        """Return an opened handle or info dict. Caller owns lifecycle."""
        pass
        
    @abc.abstractmethod
    def probe_battery(self, handle, dev_idx: int):
        """Probe and return BatteryResult or None."""
        pass

    def close_device(self, handle) -> None:
        """Close the handle if persistent."""
        try:
            handle.close()
        except Exception:
            pass
