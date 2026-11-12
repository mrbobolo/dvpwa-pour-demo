import asyncio
import unittest
from unittest import mock

from aiohttp.test_utils import make_mocked_request
from aiohttp.web import Application
from aiohttp_jinja2 import setup as setup_jinja
from jinja2.loaders import PackageLoader

from sqli import views
from sqli.dao.course import Course

PAYLOAD = '<script>alert(1)</script>'


class _FakeAcquire:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


class _FakeDb:
    def acquire(self):
        return _FakeAcquire()


def _make_request(method='GET', post_data=None):
    app = Application()
    app['db'] = _FakeDb()
    setup_jinja(
        app,
        loader=PackageLoader('sqli', 'templates'),
        context_processors=[_context],
        autoescape=False,  # same as production configuration
    )
    request = make_mocked_request(
        method, '/courses/1/review',
        match_info={'course_id': '1'}, app=app,
    )
    if post_data is not None:
        async def post():
            return post_data
        request.post = post
    return request


async def _context(request):
    return {'csrf_token': lambda: 'token', 'auth_user': None}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class ReviewStoredXssTest(unittest.TestCase):
    def _render(self, course, method='GET', post_data=None):
        request = _make_request(method, post_data)
        with mock.patch.object(Course, 'get',
                               mock.AsyncMock(return_value=course)):
            response = _run(views.review(request))
        return response.text

    def test_title_is_html_encoded(self):
        course = Course(1, PAYLOAD, 'desc')
        body = self._render(course)
        self.assertNotIn(PAYLOAD, body)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', body)

    def test_title_is_html_encoded_on_validation_error(self):
        course = Course(1, PAYLOAD, None)
        body = self._render(course, 'POST', {'review_text': ''})
        self.assertNotIn(PAYLOAD, body)
        self.assertIn('&lt;script&gt;', body)

    def test_plain_title_is_unchanged(self):
        course = Course(1, 'Algebra 101', None)
        body = self._render(course)
        self.assertIn('Algebra 101', body)
