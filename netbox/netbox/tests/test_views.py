import tempfile
import urllib.parse
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from dcim.choices import DeviceStatusChoices, InterfaceTypeChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site, VirtualChassis
from extras.events import enqueue_event
from extras.models import ImageAttachment
from extras.validators import CustomValidator
from ipam.choices import VLANStatusChoices
from ipam.models import VLAN, VLANGroup
from netbox.constants import EMPTY_TABLE_TEXT
from netbox.search.backends import search_backend
from users.models import User
from utilities.testing import TestCase
from utilities.views import get_action_url


class HomeViewTestCase(TestCase):

    def test_home(self):
        url = reverse('home')
        response = self.client.get(url)
        self.assertHttpStatus(response, 200)


class SearchViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        sites = (
            Site(name='Site Alpha', slug='alpha', description='Red'),
            Site(name='Site Bravo', slug='bravo', description='Red'),
            Site(name='Site Charlie', slug='charlie', description='Green'),
            Site(name='Site Delta', slug='delta', description='Green'),
            Site(name='Site Echo', slug='echo', description='Blue'),
            Site(name='Site Foxtrot', slug='foxtrot', description='Blue'),
        )
        Site.objects.bulk_create(sites)
        search_backend.cache(sites)

    def test_search(self):
        url = reverse('search')
        response = self.client.get(url)
        self.assertHttpStatus(response, 200)

    def test_search_query(self):
        url = reverse('search')
        params = {
            'q': 'red',
        }
        query = urllib.parse.urlencode(params)

        # Test without view permission
        response = self.client.get(f'{url}?{query}')
        self.assertHttpStatus(response, 200)
        content = str(response.content)
        self.assertIn(EMPTY_TABLE_TEXT, content)

        # Add view permissions & query again. Only matching objects should be listed
        self.add_permissions('dcim.view_site')
        response = self.client.get(f'{url}?{query}')
        self.assertHttpStatus(response, 200)
        content = str(response.content)
        self.assertIn('Site Alpha', content)
        self.assertIn('Site Bravo', content)
        self.assertNotIn('Site Charlie', content)
        self.assertNotIn('Site Delta', content)
        self.assertNotIn('Site Echo', content)
        self.assertNotIn('Site Foxtrot', content)

    def test_search_no_results(self):
        self.add_permissions('dcim.view_site')
        url = reverse('search')
        params = {
            'q': 'xxxxxxxxx',  # Matches nothing
        }
        query = urllib.parse.urlencode(params)

        response = self.client.get(f'{url}?{query}')
        self.assertHttpStatus(response, 200)
        content = str(response.content)
        self.assertIn(EMPTY_TABLE_TEXT, content)


class MediaViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        site = Site.objects.create(name='Site 1', slug='site-1')
        ct = ContentType.objects.get_for_model(Site)
        cls.image_attachment = ImageAttachment.objects.create(
            object_type=ct,
            object_id=site.pk,
            name='Test Image',
            image='image-attachments/site_1_test.jpg',
            image_height=100,
            image_width=100,
        )

        manufacturer = Manufacturer.objects.create(name='Manufacturer 1', slug='manufacturer-1')
        cls.device_type = DeviceType.objects.create(
            model='Device Type 1',
            slug='device-type-1',
            manufacturer=manufacturer,
            front_image='devicetype-images/front.jpg',
        )

    def test_media_login_required(self):
        url = reverse('media', kwargs={'path': 'foo.txt'})
        response = Client().get(url)

        # Unauthenticated request should redirect to login page
        self.assertHttpStatus(response, 302)

    @override_settings(LOGIN_REQUIRED=False)
    def test_media_login_not_required(self):
        url = reverse('media', kwargs={'path': 'foo.txt'})
        response = Client().get(url)

        # Unauthenticated request should return a 404 (not found)
        self.assertHttpStatus(response, 404)


class ServeStaticInAppTestCase(TestCase):

    def test_static_served_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'probe.txt').write_text('ok', encoding='utf-8')
            with override_settings(SERVE_STATIC_IN_APP=True, STATIC_ROOT=tmp):
                response = Client().get('/static/probe.txt')
        self.assertHttpStatus(response, 200)
        self.assertEqual(response.content, b'ok')

    def test_static_not_served_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'probe.txt').write_text('ok', encoding='utf-8')
            with override_settings(SERVE_STATIC_IN_APP=False, STATIC_ROOT=tmp):
                response = Client().get('/static/probe.txt')
        self.assertHttpStatus(response, 404)
