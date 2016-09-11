"""
Test suite for the config.views module
"""
import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import Http404
from django.test import RequestFactory
from mixer.backend.django import mixer
from app.config import views
from app.config.models import NotificationMessage
from app.config import utils

pytestmark = pytest.mark.django_db
APP_SETTING_CISCO_API_ENABLED = True
MOCK_WORKER_STATE = True


class AppSettingsMock:
    def read_file(self):
        pass

    def load_client_credentials(self):
        pass

    def is_cisco_api_enabled(self):
        return APP_SETTING_CISCO_API_ENABLED

    def get_cisco_api_client_id(self):
        return "client_id"

    def get_cisco_api_client_secret(self):
        return "client_secret"

    def is_login_only_mode(self):
        return True

    def is_cisco_eox_api_auto_sync_enabled(self):
        return True

    def get_cisco_eox_api_queries(self):
        return ""

    def get_product_blacklist_regex(self):
        return ""

    def is_auto_create_new_products(self):
        return True

    def set_login_only_mode(self, *args, **kwargs):
        pass

    def set_cisco_api_enabled(self, *args, **kwargs):
        pass

    def set_cisco_api_client_id(self, *args, **kwargs):
        pass

    def set_cisco_api_client_secret(self, *args, **kwargs):
        pass

    def set_cisco_eox_api_auto_sync_enabled(self, *args, **kwargs):
        pass

    def set_auto_create_new_products(self, *args, **kwargs):
        pass

    def set_cisco_eox_api_queries(self, *args, **kwargs):
        pass

    def set_product_blacklist_regex(self, *args, **kwargs):
        pass

    def write_file(self):
        pass


class MockWorker:
    """Mock for the Worker data object from django celery"""
    def count(self):
        return 1

    def is_alive(self):
        return MOCK_WORKER_STATE

    def __iter__(self):
        yield self

    def __getitem__(self, item):
        return self


def patch_contrib_messages(request):
    setattr(request, 'session', 'session')
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    return messages


@pytest.fixture
def mock_cisco_eox_api_access_available(monkeypatch):
    monkeypatch.setattr(views, "AppSettings", AppSettingsMock)
    monkeypatch.setattr(utils, "check_cisco_eox_api_access",
                        lambda client_id, client_secret, drop_credentials=False: True)


@pytest.fixture
def mock_cisco_eox_api_access_broken(monkeypatch):
    monkeypatch.setattr(views, "AppSettings", AppSettingsMock)
    monkeypatch.setattr(utils, "check_cisco_eox_api_access",
                        lambda client_id, client_secret, drop_credentials=False: False)


@pytest.fixture
def mock_cisco_eox_api_access_exception(monkeypatch):
    def raise_exception():
        raise Exception("totally broken")

    monkeypatch.setattr(views, "AppSettings", AppSettingsMock)
    monkeypatch.setattr(utils, "check_cisco_eox_api_access",
                        lambda client_id, client_secret, drop_credentials: raise_exception())


class TestAddNotificationView:
    URL_NAME = "productdb_config:notification-add"

    def test_anonymous_default(self):
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        response = views.add_notification(request)

        assert response.status_code == 302
        assert response.url.startswith("/productdb/login")

    def test_authenticated_user(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=False)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        with pytest.raises(PermissionDenied):
            views.add_notification(request)

    def test_superuser_access(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        response = views.add_notification(request)

        assert response.status_code == 200

    def test_post(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        data = {
            "title": "MyTitle",
            "type": "ERR",
            "summary_message": "This is a summary",
            "detailed_message": "This is the detail message"
        }
        request = RequestFactory().post(url, data=data)
        request.user = user

        response = views.add_notification(request)

        assert response.status_code == 302
        assert NotificationMessage.objects.count() == 1
        n = NotificationMessage.objects.filter(title="MyTitle").first()
        assert n.type == NotificationMessage.MESSAGE_ERROR

        # test with missing input
        data = {
            "title": "MyTitle",
            "type": "ERR",
            "detailed_message": "This is the detail message"
        }
        request = RequestFactory().post(url, data=data)
        request.user = user

        response = views.add_notification(request)

        assert response.status_code == 200


class TestStatusView:
    URL_NAME = "productdb_config:status"

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    def test_anonymous_default(self):
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        response = views.status(request)

        assert response.status_code == 302
        assert response.url.startswith("/productdb/login")

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    def test_authenticated_user(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=False)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        with pytest.raises(PermissionDenied):
            views.status(request)

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    def test_superuser_access(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        response = views.status(request)

        assert response.status_code == 200
        expected_content = [
            "All backend worker offline, asynchronous and scheduled tasks are not executed.",
            "successful connected to the Cisco EoX API"
        ]
        for line in expected_content:
            assert line in response.content.decode()

        assert cache.get("CISCO_EOX_API_TEST", None) is True

        # cleanup
        cache.delete("CISCO_EOX_API_TEST")

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    def test_with_active_workers(self, monkeypatch):
        monkeypatch.setattr(views.WorkerState.objects, "all", lambda: MockWorker())
        cache.delete("CISCO_EOX_API_TEST")  # ensure that cache is not set
        global MOCK_WORKER_STATE
        MOCK_WORKER_STATE = True

        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        response = views.status(request)

        assert response.status_code == 200
        assert cache.get("CISCO_EOX_API_TEST", None) is True
        expected_content = [
            "Backend worker found.",
            "successful connected to the Cisco EoX API"
        ]
        for line in expected_content:
            assert line in response.content.decode()

        # cleanup
        cache.delete("CISCO_EOX_API_TEST")

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    def test_with_inactive_workers(self, monkeypatch):
        monkeypatch.setattr(views.WorkerState.objects, "all", lambda: MockWorker())
        cache.delete("CISCO_EOX_API_TEST")  # ensure that cache is not set
        global MOCK_WORKER_STATE
        MOCK_WORKER_STATE = False

        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        response = views.status(request)

        assert response.status_code == 200
        assert cache.get("CISCO_EOX_API_TEST", None) is True
        expected_content = [
            "Only unregistered backend worker found",
            "successful connected to the Cisco EoX API"
        ]
        for line in expected_content:
            assert line in response.content.decode()

        # cleanup
        cache.delete("CISCO_EOX_API_TEST")

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_broken")
    def test_access_with_broken_api(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        response = views.status(request)

        assert response.status_code == 200
        assert cache.get("CISCO_EOX_API_TEST", None) is False

        # cleanup
        cache.delete("CISCO_EOX_API_TEST")

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_exception")
    def test_access_with_broken_api_by_exception(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        response = views.status(request)

        assert response.status_code == 200
        assert cache.get("CISCO_EOX_API_TEST", None) is None

        # cleanup
        cache.delete("CISCO_EOX_API_TEST")


class TestChangeConfiguration:
    URL_NAME = "productdb_config:change_settings"

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    def test_anonymous_default(self):
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        response = views.change_configuration(request)

        assert response.status_code == 302
        assert response.url.startswith("/productdb/login")

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    def test_authenticated_user(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=False)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user

        with pytest.raises(PermissionDenied):
            views.change_configuration(request)

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    @pytest.mark.usefixtures("import_default_text_blocks")
    def test_superuser_access(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = user
        patch_contrib_messages(request)

        response = views.change_configuration(request)

        assert response.status_code == 200

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    @pytest.mark.usefixtures("import_default_text_blocks")
    def test_post_with_active_api(self):
        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        data = {}
        request = RequestFactory().post(url, data=data)
        request.user = user
        patch_contrib_messages(request)

        response = views.change_configuration(request)

        assert response.status_code == 302
        assert response.url == "/productdb/config/change/"

        data = {
            "cisco_api_client_id": "my changed client ID",
            "cisco_api_client_secret": "my changed client secret",
        }
        request = RequestFactory().post(url, data=data)
        request.user = user
        patch_contrib_messages(request)

        response = views.change_configuration(request)

        assert response.status_code == 302
        assert response.url == "/productdb/config/change/"

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_available")
    @pytest.mark.usefixtures("import_default_text_blocks")
    def test_post_with_inactive_api(self):
        global APP_SETTING_CISCO_API_ENABLED
        APP_SETTING_CISCO_API_ENABLED = False

        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        data = {
            "cisco_api_enabled": "on",
        }
        request = RequestFactory().post(url, data=data)
        request.user = user
        msgs = patch_contrib_messages(request)

        response = views.change_configuration(request)

        assert response.status_code == 302
        assert response.url == "/productdb/config/change/"
        assert msgs.added_new

        data = {
            "cisco_api_enabled": "on",
            "cisco_api_client_id": "client_id"
        }
        request = RequestFactory().post(url, data=data)
        request.user = user
        msgs = patch_contrib_messages(request)

        response = views.change_configuration(request)

        assert response.status_code == 302
        assert response.url == "/productdb/config/change/"
        assert msgs.added_new

    @pytest.mark.usefixtures("mock_cisco_eox_api_access_broken")
    @pytest.mark.usefixtures("import_default_text_blocks")
    def test_post_with_broken_api(self):
        global APP_SETTING_CISCO_API_ENABLED
        APP_SETTING_CISCO_API_ENABLED = False

        # require super user permissions
        user = mixer.blend("auth.User", is_superuser=True)
        url = reverse(self.URL_NAME)
        data = {
            "cisco_api_enabled": "on",
            "cisco_api_client_id": "client_id"
        }
        request = RequestFactory().post(url, data=data)
        request.user = user
        msgs = patch_contrib_messages(request)

        response = views.change_configuration(request)

        assert response.status_code == 302
        assert response.url == "/productdb/config/change/"
        assert msgs.added_new


class TestServerMessagesList:
    URL_NAME = "productdb_config:notification-list"

    def test_anonymous_default(self):
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        response = views.server_messages_list(request)

        assert response.status_code == 200, "Should be callable"

    @pytest.mark.usefixtures("enable_login_only_mode")
    def test_anonymous_login_only_mode(self):
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        response = views.server_messages_list(request)

        assert response.status_code == 302, "Should redirect to login page"
        assert response.url == reverse("login") + "?next=" + url, \
            "Should contain a next parameter for redirect"

    def test_authenticated_user(self):
        mixer.blend("config.NotificationMessage")
        mixer.blend("config.NotificationMessage")
        mixer.blend("config.NotificationMessage")
        mixer.blend("config.NotificationMessage")
        mixer.blend("config.NotificationMessage")
        url = reverse(self.URL_NAME)
        request = RequestFactory().get(url)
        request.user = mixer.blend("auth.User", is_superuser=False, is_staff=False)
        response = views.server_messages_list(request)

        assert response.status_code == 200, "Should be callable"


class TestServerMessagesDetail:
    URL_NAME = "productdb_config:notification-detail"

    def test_anonymous_default(self):
        nm = mixer.blend("config.NotificationMessage")

        url = reverse(self.URL_NAME, kwargs={"message_id": nm.id})
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        response = views.server_message_detail(request, nm.id)

        assert response.status_code == 200, "Should be callable"

    @pytest.mark.usefixtures("enable_login_only_mode")
    def test_anonymous_login_only_mode(self):
        nm = mixer.blend("config.NotificationMessage")

        url = reverse(self.URL_NAME, kwargs={"message_id": nm.id})
        request = RequestFactory().get(url)
        request.user = AnonymousUser()
        response = views.server_message_detail(request, nm.id)

        assert response.status_code == 302, "Should redirect to login page"
        assert response.url == reverse("login") + "?next=" + url, \
            "Should contain a next parameter for redirect"

    def test_authenticated_user(self):
        nm = mixer.blend("config.NotificationMessage")

        url = reverse(self.URL_NAME, kwargs={"message_id": nm.id})
        request = RequestFactory().get(url)
        request.user = mixer.blend("auth.User", is_superuser=False, is_staff=False)
        response = views.server_message_detail(request, nm.id)

        assert response.status_code == 200, "Should be callable"

    def test_404(self):
        url = reverse(self.URL_NAME, kwargs={"message_id": 9999})
        request = RequestFactory().get(url)
        request.user = mixer.blend("auth.User", is_superuser=False, is_staff=False)

        with pytest.raises(Http404):
            response = views.server_message_detail(request, 9999)
