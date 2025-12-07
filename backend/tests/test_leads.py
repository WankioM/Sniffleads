import pytest
from apps.leads.models import Lead
from apps.leads.services import upsert_lead, merge_lead_tags, bulk_upsert_leads
from apps.leads.selectors import get_leads_by_source, get_leads_by_tag, search_leads


@pytest.mark.django_db
class TestLeadModel:
    def test_create_lead(self):
        lead = Lead.objects.create(
            name="John Doe",
            role="Audio Engineer",
            company="SoundStudio",
            profile_url="https://medium.com/@johndoe",
            source_domain="medium.com",
            email="john@example.com",
            tags=["audio-engineering", "music-production"],
        )
        assert lead.id is not None
        assert str(lead) == "John Doe (medium.com)"

    def test_unique_constraint(self):
        Lead.objects.create(
            name="Jane Doe",
            profile_url="https://medium.com/@janedoe",
            source_domain="medium.com",
        )
        with pytest.raises(Exception):  # IntegrityError
            Lead.objects.create(
                name="Jane Duplicate",
                profile_url="https://medium.com/@janedoe",
                source_domain="medium.com",
            )


@pytest.mark.django_db
class TestLeadServices:
    def test_upsert_creates_new_lead(self):
        lead, created = upsert_lead(
            profile_url="https://medium.com/@newuser",
            source_domain="medium.com",
            name="New User",
            role="Producer",
        )
        assert created is True
        assert lead.name == "New User"

    def test_upsert_updates_existing_lead(self):
        # Create initial
        upsert_lead(
            profile_url="https://medium.com/@updateme",
            source_domain="medium.com",
            name="Original Name",
        )
        # Update
        lead, created = upsert_lead(
            profile_url="https://medium.com/@updateme",
            source_domain="medium.com",
            name="Updated Name",
            role="New Role",
        )
        assert created is False
        assert lead.name == "Updated Name"
        assert lead.role == "New Role"

    def test_merge_tags(self):
        lead, _ = upsert_lead(
            profile_url="https://medium.com/@tagtest",
            source_domain="medium.com",
            name="Tag Test",
            tags=["existing-tag"],
        )
        merge_lead_tags(lead, ["new-tag", "existing-tag"])
        lead.refresh_from_db()
        assert set(lead.tags) == {"existing-tag", "new-tag"}

    def test_bulk_upsert(self):
        leads_data = [
            {"profile_url": "https://m.com/@a", "source_domain": "m.com", "name": "A"},
            {"profile_url": "https://m.com/@b", "source_domain": "m.com", "name": "B"},
        ]
        result = bulk_upsert_leads(leads_data)
        assert result["created"] == 2
        assert result["updated"] == 0


@pytest.mark.django_db
class TestLeadSelectors:
    @pytest.fixture
    def sample_leads(self):
        Lead.objects.create(
            name="Alice", source_domain="medium.com",
            profile_url="https://medium.com/@alice",
            tags=["audio"], email="alice@test.com"
        )
        Lead.objects.create(
            name="Bob", source_domain="linkedin.com",
            profile_url="https://linkedin.com/in/bob",
            tags=["video"], email=""
        )

    def test_get_by_source(self, sample_leads):
        leads = get_leads_by_source("medium.com")
        assert leads.count() == 1
        assert leads.first().name == "Alice"

    def test_get_by_tag(self, sample_leads):
        leads = get_leads_by_tag("audio")
        assert leads.count() == 1

    def test_search_with_email_filter(self, sample_leads):
        with_email = search_leads(has_email=True)
        without_email = search_leads(has_email=False)
        assert with_email.count() == 1
        assert without_email.count() == 1