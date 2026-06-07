import pytest


@pytest.fixture
def mock_hid(mocker):
    """Factory fixture: returns a mock hid.device with configurable read() behavior."""
    device = mocker.MagicMock()
    device.write.return_value = None
    return device
