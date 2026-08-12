import pytest

from radar.models import Company


@pytest.fixture
def make_company(db):
    def _make(**overrides):
        defaults = dict(
            name="Exemplo Co",
            slug="exemplo-co",
            tier=Company.Tier.A,
            ats_provider=Company.AtsProvider.GREENHOUSE,
            ats_board_url="https://boards.greenhouse.io/exemploco",
            careers_url="https://exemploco.com/careers",
        )
        defaults.update(overrides)
        return Company.objects.create(**defaults)

    return _make
