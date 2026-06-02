"""Unit tests for DeviceCard widget.

Strategy (from RESEARCH Validation Architecture):
  - NEVER call widget.show() in headless tests — Qt show() requires a display.
  - Instantiate DeviceCard and call methods directly.
  - pytest-qt's qapp fixture provides the QApplication singleton.
"""
import pytest
from PySide6.QtWidgets import QFrame

from monitor.state import DeviceState, DeviceStatus
from ui.settings_manager import battery_color


def _make_state(
    percent: int | None,
    status: DeviceStatus,
    charging: bool = False,
    device_name: str = "G Pro X Wireless",
) -> DeviceState:
    return DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0,
        device_name=device_name,
        percent=percent,
        charging=charging,
        status=status,
    )


class TestDeviceCardConstruction:
    def test_is_qframe_subclass(self, qapp):
        """DeviceCard must subclass QFrame (not QWidget) for QSS background."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert isinstance(card, QFrame)

    def test_constructs_with_state(self, qapp):
        """DeviceCard(state) constructs without raising."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert card is not None

    def test_constructs_without_state(self, qapp):
        """DeviceCard() constructs without raising (no state provided)."""
        from ui.device_card import DeviceCard
        card = DeviceCard()
        assert card is not None

    def test_has_object_name(self, qapp):
        """DeviceCard must have an objectName set for QSS targeting."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert card.objectName() != ""


class TestDeviceCardNameLabel:
    def test_name_label_shows_device_name(self, qapp):
        """name label must show state.device_name."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE, device_name="G Pro X Wireless")
        card = DeviceCard(state)
        assert card._name.text() == "G Pro X Wireless"

    def test_name_label_updates_on_update_state(self, qapp):
        """update_state must update the name label."""
        from ui.device_card import DeviceCard
        state1 = _make_state(80, DeviceStatus.ONLINE, device_name="Device A")
        state2 = _make_state(50, DeviceStatus.ONLINE, device_name="Device B")
        card = DeviceCard(state1)
        card.update_state(state2)
        assert card._name.text() == "Device B"


class TestDeviceCardPercentLabel:
    def test_normal_percent_shows_value(self, qapp):
        """Percent label must show '<n>%' for normal battery (80%)."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert card._percent.text() == "80%"

    def test_warning_percent_shows_value(self, qapp):
        """Percent label must show value at warning threshold (30%)."""
        from ui.device_card import DeviceCard
        state = _make_state(30, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert card._percent.text() == "30%"

    def test_critical_percent_shows_value(self, qapp):
        """Percent label must show value at critical threshold (5%)."""
        from ui.device_card import DeviceCard
        state = _make_state(5, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert card._percent.text() == "5%"

    def test_none_percent_shows_placeholder(self, qapp):
        """Percent label must show a placeholder (not 'None%') when percent is None."""
        from ui.device_card import DeviceCard
        state = _make_state(None, DeviceStatus.OFFLINE)
        card = DeviceCard(state)
        text = card._percent.text()
        assert "None" not in text
        assert text in ("--", "Offline", "N/A")

    def test_percent_label_color_normal(self, qapp):
        """Percent label stylesheet must contain battery_color for normal percent."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        expected_color = battery_color(80)  # "#4FC3F7"
        assert expected_color in card._percent.styleSheet()

    def test_percent_label_color_warning(self, qapp):
        """Percent label stylesheet must contain battery_color for warning percent."""
        from ui.device_card import DeviceCard
        state = _make_state(30, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        expected_color = battery_color(30)  # "#E5A300"
        assert expected_color in card._percent.styleSheet()

    def test_percent_label_color_critical(self, qapp):
        """Percent label stylesheet must contain battery_color for critical percent."""
        from ui.device_card import DeviceCard
        state = _make_state(5, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        expected_color = battery_color(5)  # "#E50000"
        assert expected_color in card._percent.styleSheet()

    def test_percent_label_color_offline_none(self, qapp):
        """Percent label stylesheet must contain battery_color(None) when offline."""
        from ui.device_card import DeviceCard
        state = _make_state(None, DeviceStatus.OFFLINE)
        card = DeviceCard(state)
        expected_color = battery_color(None)  # "#888888"
        assert expected_color in card._percent.styleSheet()


class TestDeviceCardStatusLabel:
    def test_status_label_online(self, qapp):
        """Status label must show 'ONLINE' for ONLINE status."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert card._status.text() == "ONLINE"

    def test_status_label_offline(self, qapp):
        """Status label must show 'OFFLINE' for OFFLINE status."""
        from ui.device_card import DeviceCard
        state = _make_state(None, DeviceStatus.OFFLINE)
        card = DeviceCard(state)
        assert card._status.text() == "OFFLINE"

    def test_status_label_charging(self, qapp):
        """Status label must show 'CHARGING' for CHARGING status."""
        from ui.device_card import DeviceCard
        state = _make_state(75, DeviceStatus.CHARGING, charging=True)
        card = DeviceCard(state)
        assert card._status.text() == "CHARGING"


class TestDeviceCardOfflineMuting:
    def test_offline_sets_muted_property(self, qapp):
        """OFFLINE state must set an assertable 'offline' property to True."""
        from ui.device_card import DeviceCard
        state = _make_state(None, DeviceStatus.OFFLINE)
        card = DeviceCard(state)
        assert card.property("offline") is True

    def test_online_clears_muted_property(self, qapp):
        """ONLINE state must set 'offline' property to False."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state)
        assert card.property("offline") is False

    def test_update_state_toggles_muted_property(self, qapp):
        """update_state from OFFLINE to ONLINE must clear the 'offline' property."""
        from ui.device_card import DeviceCard
        state_offline = _make_state(None, DeviceStatus.OFFLINE)
        state_online = _make_state(80, DeviceStatus.ONLINE)
        card = DeviceCard(state_offline)
        assert card.property("offline") is True
        card.update_state(state_online)
        assert card.property("offline") is False


class TestDeviceCardChargingIndicator:
    def test_charging_true_shows_indicator(self, qapp):
        """Charging indicator must be visible when charging is True."""
        from ui.device_card import DeviceCard
        state = _make_state(75, DeviceStatus.CHARGING, charging=True)
        card = DeviceCard(state)
        assert card._charging_indicator.isVisible()

    def test_charging_false_hides_indicator(self, qapp):
        """Charging indicator must be hidden when charging is False."""
        from ui.device_card import DeviceCard
        state = _make_state(80, DeviceStatus.ONLINE, charging=False)
        card = DeviceCard(state)
        assert not card._charging_indicator.isVisible()

    def test_update_state_toggles_charging_indicator(self, qapp):
        """update_state must show/hide charging indicator per state.charging."""
        from ui.device_card import DeviceCard
        state_not_charging = _make_state(80, DeviceStatus.ONLINE, charging=False)
        state_charging = _make_state(75, DeviceStatus.CHARGING, charging=True)
        card = DeviceCard(state_not_charging)
        assert not card._charging_indicator.isVisible()
        card.update_state(state_charging)
        assert card._charging_indicator.isVisible()


class TestDeviceCardUpdateState:
    def test_update_state_refreshes_all_fields(self, qapp):
        """update_state must update name, percent, status, and color together."""
        from ui.device_card import DeviceCard
        state1 = _make_state(80, DeviceStatus.ONLINE)
        state2 = _make_state(5, DeviceStatus.ONLINE)
        card = DeviceCard(state1)
        card.update_state(state2)
        assert card._percent.text() == "5%"
        assert battery_color(5) in card._percent.styleSheet()
