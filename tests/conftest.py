"""Root conftest for the test suite.

pytest configuration:
  - asyncio_mode = auto is set in pytest.ini (no @pytest.mark.asyncio needed)
  - Shared fixtures live in tests/fixtures/ and are imported explicitly
  - In-memory SQLite is used for all DB tests via create_test_session_factory()
"""
